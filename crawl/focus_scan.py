"""Independent, ephemeral Green monitoring. Never writes listings or crawl_tasks.

The restored Green crawler supplies URL construction and parsing only. Its
crawl/persist/queue entry points are never called. Source dates without time
use a persistent first-page identity boundary, not invented minute precision.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import signal
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, urlencode

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
from crawl.common import CrawlConfig, load_mysql_config, mysql_connect, now_kst, parse_site_date, parse_price_krw
from crawl.site.green_heavy import GreenHeavyCrawler, Category
from crawl import focus_mail

MAX_PAGES = 3
MAX_REQUESTS = 40
MAX_SECONDS = 150
STOP = False


def stamp():
    return now_kst().replace(tzinfo=None)


def plain_date(value):
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=None)
    parsed = parse_site_date(str(value or ''))
    return parsed.replace(tzinfo=None) if parsed else None


def decode(value):
    return json.loads(value) if isinstance(value, str) else value


def identity(row):
    pid = str(row.get('pid') or '')
    if not pid:
        pid = (parse_qs(urlsplit(row.get('detail_url') or '').query).get('pid') or [''])[0]
    return hashlib.sha256(('green:' + pid).encode()).hexdigest() if pid else None


def normalize(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(value or ''))).casefold()


def green_manufactured_year(value):
    """Parse Green list YY.MM or detail YYYY[.MM], without guessing unknowns.

    Fixed manufacturing-year window: 00-49 means 2000-2049; 50-99 means
    1950-1999. Unlike posting dates, old equipment can be from the 1900s.
    """
    text = unicodedata.normalize('NFKC', str(value or '')).strip()
    match = re.fullmatch(r'((?:19|20)\d{2}|\d{2})(?:\.(\d{1,2}))?', text)
    if not match:
        return None
    year_text, month_text = match.groups()
    if len(year_text) == 2 and month_text is None:
        return None
    if month_text is not None and not 1 <= int(month_text) <= 12:
        return None
    year = int(year_text)
    if len(year_text) == 2:
        year += 2000 if year < 50 else 1900
    return year


def matches(rule, row):
    if normalize(rule['model_contains']) not in normalize(row.get('model_name')):
        return False
    price = parse_price_krw(row.get('price'))
    for key, less in [('price_min_manwon', True), ('price_max_manwon', False)]:
        if rule.get(key) is not None:
            if price is None or price <= 0 or (price < rule[key] * 10000 if less else price > rule[key] * 10000):
                return False
    year = green_manufactured_year(row.get('manufactured_ym'))
    for key, less in [('year_min', True), ('year_max', False)]:
        if rule.get(key) is not None:
            if year is None or (year < rule[key] if less else year > rule[key]):
                return False
    return True


def in_window(row, cutoff, until):
    values = row.get('raw', {}).get('list_values', [])
    raw = str(values[10] if len(values) > 10 else row.get('posted_at') or row.get('posted_date') or '')
    parsed = plain_date(raw)
    if not parsed:
        return False
    if re.search(r'\d{1,2}:\d{2}', raw):
        return cutoff <= parsed <= until
    return cutoff.date() <= parsed.date() <= until.date()


def safe_path(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname not in ('4396200.com', 'www.4396200.com'):
        raise ValueError('unexpected source host')
    q = parse_qs(p.query)
    return (p.path + '?' + urlencode({k: q[k][0] for k in ('cate_code', 'page', 'limit', 'pid') if k in q}))[:180]


def response_fields(rows):
    """Keep only source model/year/price text; never persist the source body."""
    def text(value):
        return str(value) if isinstance(value, (str, int, float)) and not isinstance(value, bool) else None
    return [{key: text(row.get(key)) for key in ('model_name', 'manufactured_ym', 'price')}
            for row in rows if isinstance(row, dict)]


class BudgetExceeded(Exception):
    pass


class SourceResponseError(Exception):
    pass


class Store:
    def __init__(self, mysql):
        self.mysql = mysql

    def query(self, sql, params=(), one=False):
        with mysql_connect(self.mysql, self.mysql.database) as conn:
            with conn.cursor() as c:
                c.execute(sql, params)
                return c.fetchone() if one else c.fetchall()

    def execute(self, sql, params=()):
        with mysql_connect(self.mysql, self.mysql.database) as conn:
            with conn.cursor() as c:
                c.execute(sql, params)
                return c.rowcount

    def log(self, rule, category, kind, status, summary='', **fields):
        with mysql_connect(self.mysql, self.mysql.database) as conn:
            with conn.cursor() as c:
                c.execute('''INSERT INTO focus_logs
                    (rule_id,category_code,kind,status,summary,method,request_path,http_status,response_bytes,duration_ms)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (rule, category, kind, status, summary[:240], fields.get('method'), fields.get('request_path'),
                     fields.get('http_status'), fields.get('response_bytes'), fields.get('duration_ms')))
                if 'response_rows' in fields:
                    # The existing JSON column also holds historical string-only samples.
                    payload = response_fields(fields['response_rows'])
                    c.execute('INSERT INTO focus_log_samples(log_id,names_json) VALUES(%s,%s)',
                              (c.lastrowid, json.dumps(payload, ensure_ascii=False)))
        self.execute('UPDATE focus_service_state SET heartbeat_at=NOW() WHERE id=1')

    def current(self, rule):
        table = 'focus_scan_config' if rule.get('_scan') else 'focus_rules'
        row = self.query(f'SELECT enabled,revision FROM {table} WHERE id=%s', (rule['id'],), one=True)
        return bool(row and row['enabled'] and row['revision'] == rule['revision'] and not STOP)

    def cursor(self, rule, category):
        return self.query('SELECT * FROM focus_shared_cursors WHERE scan_id=%s AND revision=%s AND category_code=%s',
                          (rule['id'], rule['revision'], category), one=True)

    def save_cursor(self, rule, category, started, keys):
        self.execute('''INSERT INTO focus_shared_cursors (scan_id,revision,category_code,last_success_at,boundary_json)
            VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE last_success_at=VALUES(last_success_at),
            boundary_json=VALUES(boundary_json)''',
            (rule['id'], rule['revision'], category, started, json.dumps(keys)))

    def claim(self, rule, key):
        return self.execute("INSERT IGNORE INTO focus_seen(rule_id,identity_hash,status) VALUES (%s,%s,'sending')",
                            (rule['id'], key)) == 1

    def known(self, rule, key):
        return bool(self.query('SELECT status FROM focus_mail_history WHERE rule_id=%s AND identity_hash=%s',
                               (rule['id'], key), one=True) or
                    self.query('SELECT status FROM focus_seen WHERE rule_id=%s AND identity_hash=%s',
                               (rule['id'], key), one=True))

    def prepare_mail(self, rule, key, row):
        condition = {k:rule.get(k) for k in ('model_contains','price_min_manwon','price_max_manwon','year_min','year_max')}
        url = row.get('detail_url') or ''
        if url:
            safe_path(url)
        return self.execute('''INSERT IGNORE INTO focus_mail_history
            (rule_id,identity_hash,recipient,listing_name,price_text,manufactured_ym,detail_url,category_code,condition_json)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (rule['id'],key,rule['email'],str(row.get('listing_name') or row.get('model_name') or '')[:240],
             str(row.get('price') or '')[:120],str(row.get('manufactured_ym') or '')[:40],url[:500],
             row.get('category_code'),json.dumps(condition,ensure_ascii=False))) == 1

    def delivery(self, rule, key, status):
        # Durable receipt first: even if the expendable dedupe update fails, a sent
        # record remains and future runs cannot send this rule/listing again.
        self.execute("UPDATE focus_mail_history SET status=%s,sent_at=IF(%s='sent',NOW(),sent_at) WHERE rule_id=%s AND identity_hash=%s",
                     (status,status,rule['id'],key))
        self.execute('UPDATE focus_seen SET status=%s WHERE rule_id=%s AND identity_hash=%s', (status, rule['id'], key))

    def cleanup(self):
        # Only this feature's expendable history. Never touches legacy tables.
        for table in ('focus_log_samples', 'focus_logs', 'focus_seen'):
            self.execute(f'DELETE FROM {table} WHERE created_at < NOW() - INTERVAL 7 DAY LIMIT 10000')
        self.execute('''DELETE c FROM focus_shared_cursors c JOIN focus_scan_config r ON r.id=c.scan_id
            WHERE c.revision<>r.revision''')
        self.execute("DELETE FROM focus_mail_history WHERE status NOT IN ('sent','sending','uncertain') AND created_at<NOW()-INTERVAL 7 DAY LIMIT 10000")


class FocusCrawler(GreenHeavyCrawler):
    def __init__(self, config, store, rule, category):
        self.store, self.rule, self.category = store, rule, category
        self.requests_count = 0
        self.started = time.monotonic()
        self.last_request = 0.0
        super().__init__(config)
        original = self.session.send

        def send(request, **kwargs):
            path = safe_path(request.url)
            if not self.store.current(self.rule):
                raise InterruptedError('rule paused or changed')
            if self.rule.get('_requests', 0) >= MAX_REQUESTS or time.monotonic() > self.rule.get('_deadline', self.started + MAX_SECONDS):
                raise BudgetExceeded()
            delay = self.rule.get('request_delay_seconds', 2)
            time.sleep(max(0, delay - (time.monotonic() - self.rule.get('_last_request', 0))))
            if not self.store.current(self.rule):
                raise InterruptedError('common scanner paused or changed')
            if time.monotonic() > self.rule.get('_deadline', self.started + MAX_SECONDS):
                raise BudgetExceeded()
            self.last_request = time.monotonic()
            self.rule['_last_request'] = self.last_request
            self.requests_count += 1
            self.rule['_requests'] = self.rule.get('_requests', 0) + 1
            began = time.monotonic()
            response = None
            try:
                response = original(request, **kwargs)
                return response
            finally:
                self.store.log(None, self.category, 'http',
                    'response' if response is not None else 'network_error',
                    '원문 미저장 · 파싱된 목록은 모델명·연식·가격만 별도 기록', method=request.method, request_path=path,
                    http_status=response.status_code if response is not None else None,
                    response_bytes=len(response.content) if response is not None else None,
                    duration_ms=round((time.monotonic() - began) * 1000))
        self.session.send = send

    # Explicit tripwires: accidental inherited collection must fail closed.
    def crawl(self):
        raise RuntimeError('focus scanner cannot call full collection')

    def persist_chunk(self, *args, **kwargs):
        raise RuntimeError('focus scanner cannot persist listings')

    def persist_record_batch(self, *args, **kwargs):
        raise RuntimeError('focus scanner cannot persist listings')


def deliver(store, rule, row, mail, scan=None):
    key = identity(row)
    if scan is not None and not store.current(scan):
        raise InterruptedError('common scanner paused or changed')
    if not key or store.known(rule, key) or not store.current(rule) or not store.claim(rule, key):
        return False
    if not store.prepare_mail(rule, key, row):
        return False
    try:
        # Durable pre-send claim: a crash or SMTP uncertainty is never auto-replayed.
        for attempt in range(3):
            if scan is not None and not store.current(scan):
                store.delivery(rule, key, 'cancelled')
                raise InterruptedError('common scanner paused or changed')
            if not store.current(rule):
                store.delivery(rule, key, 'cancelled')
                return False
            try:
                focus_mail.send(mail, {'id': f"focus-{rule['id']}-{key[:24]}", 'email': rule['email']}, row)
                store.delivery(rule, key, 'sent')
                store.log(rule['id'], row.get('category_code'), 'mail', 'sent', '조건 일치 신규 매물 메일 발송')
                return True
            except focus_mail.DeliveryFailure as error:
                if not error.safe_retry:
                    store.delivery(rule, key, 'uncertain')
                    store.log(rule['id'], row.get('category_code'), 'mail', 'uncertain', 'SMTP 결과 불명확 · 중복 방지를 위해 재발송 중지')
                    return False
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        store.delivery(rule, key, 'failed')
        store.log(rule['id'], row.get('category_code'), 'mail', 'failed', '메일 3회 실패 · 매물 본문은 보관하지 않으므로 자동 복구 없음')
        return False
    except BaseException:
        # The claim remains ambiguous on process death; no full payload is stored.
        raise


def scan_category(store, rule, category, config, mail, factory=FocusCrawler, rules=()):
    started = stamp()
    cursor = store.cursor(rule, category)
    if cursor and plain_date(cursor['last_success_at']) < started - dt.timedelta(minutes=rule['interval_minutes'] * 2):
        cursor = None  # A long interruption is not evidence of minute-level freshness.
    boundary = set(decode(cursor['boundary_json'])) if cursor else set()
    cutoff = started - dt.timedelta(minutes=rule['interval_minutes'])
    if cursor:
        cutoff = max(cutoff, plain_date(cursor['last_success_at']))
    crawler = factory(config, store, rule, category)
    head, sent, checked, exhausted = [], 0, 0, False
    try:
        for page in range(1, MAX_PAGES + 1):
            url = crawler.list_url(category, page)
            soup = crawler.get_soup(url)
            if crawler.listing_table(soup) is None:
                raise SourceResponseError('listing table missing')
            rows = crawler.parse_listing_page(soup, url, Category(category, category))
            # Record the fetched page, including old/nonmatching rows, before filtering.
            # Persist immediately so later page/mail failures do not lose this response.
            store.log(None, category, 'response', 'parsed',
                      f'목록 응답 {len(rows)}건 · 모델명·연식·가격만 저장',
                      method='GET', request_path=safe_path(url),
                      response_rows=response_fields(rows))
            if page == 1:
                head = [identity(row) for row in rows if identity(row)]
            hit_boundary = False
            recent_count = 0
            for row in rows:
                key = identity(row)
                if key in boundary:
                    hit_boundary = True
                    break
                if not key or not in_window(row, cutoff, started):
                    continue
                recent_count += 1
                checked += 1
                # Date-only first pass establishes a baseline, without historical mail.
                if not cursor or key in boundary:
                    continue
                for alert in rules:
                    if not store.current(rule):
                        raise InterruptedError('common scanner paused or changed')
                    if not alert['enabled'] or not store.current(alert) or not matches(alert, row):
                        continue
                    try:
                        sent += int(deliver(store, alert, row, mail, scan=rule))
                    except InterruptedError:
                        raise
                    except Exception as error:
                        # One broken recipient must not prevent other matching rules.
                        store.log(alert['id'], category, 'mail', 'failed', type(error).__name__)
            if not cursor or hit_boundary or not rows or recent_count == 0 or not crawler.has_next_page(soup, page + 1):
                exhausted = True
                break
        if not exhausted:
            raise BudgetExceeded('page budget reached before boundary')
        if not store.current(rule):
            raise InterruptedError('common scanner paused or changed')
        store.save_cursor(rule, category, started, head)
        store.log(None, category, 'scan', 'complete' if cursor else 'baseline',
                  f'공통 목록 {checked}건 · 알림 조건 {len(rules)}개 · 발송 {sent}건' if cursor else '공통 최초 기준점 등록 · 기존 매물 메일 미발송')
        return sent
    finally:
        crawler.session.close()


def tick(store, config, mail):
    ready = bool(focus_mail.mail_ready(mail))
    store.execute('''INSERT INTO focus_service_state(id,heartbeat_at,mail_ready,status) VALUES(1,NOW(),%s,'online')
        ON DUPLICATE KEY UPDATE heartbeat_at=NOW(),mail_ready=VALUES(mail_ready),status='online' ''', (ready,))
    scans = store.query('SELECT * FROM focus_scan_config WHERE id=1 AND enabled=1 AND (next_run_at IS NULL OR next_run_at<=NOW())')
    for rule in scans:
        if STOP:
            break
        # Claim a slot before network I/O. No replay/backlog after restart.
        claimed = store.execute('''UPDATE focus_scan_config SET last_started_at=NOW(),next_run_at=DATE_ADD(NOW(),INTERVAL interval_minutes MINUTE),
            last_status='running' WHERE id=%s AND revision=%s AND enabled=1 AND (next_run_at IS NULL OR next_run_at<=NOW())''', (rule['id'], rule['revision']))
        if not claimed:
            continue
        rule['_scan'] = True
        rules = store.query('SELECT * FROM focus_rules WHERE enabled=1 ORDER BY id LIMIT 100')
        status, summary = 'complete', '선택한 카테고리의 최신 구간 확인 완료'
        rule['_requests'], rule['_deadline'] = 0, time.monotonic() + MAX_SECONDS
        try:
            if rules and not ready:
                status, summary = 'mail_missing', '메일 설정 미완료 · 사이트 요청을 보내지 않았습니다'
            else:
                for category in decode(rule['categories_json']):
                    if not store.current(rule):
                        raise InterruptedError()
                    scan_category(store, rule, str(category), config, mail, rules=rules)
        except InterruptedError:
            status, summary = 'cancelled', '설정 변경 또는 중지로 종료'
        except BudgetExceeded:
            status, summary = 'partial', '부하 보호 한도 도달 · 기준점 미갱신 · 일부 미확인 가능'
        except Exception as error:
            status = 'failed'
            code = getattr(getattr(error, 'response', None), 'status_code', None)
            summary = f'HTTP {code}' if code else type(error).__name__
            store.log(None, None, 'scan', status, summary)
            if code in (400, 401, 403, 407, 429):
                store.execute('UPDATE focus_scan_config SET next_run_at=GREATEST(next_run_at,DATE_ADD(NOW(),INTERVAL 15 MINUTE)) WHERE id=%s', (rule['id'],))
        store.execute('''UPDATE focus_scan_config SET last_finished_at=NOW(),last_status=%s,last_summary=%s,
            next_run_at=GREATEST(next_run_at,NOW()) WHERE id=%s AND revision=%s''',
            (status, summary, rule['id'], rule['revision']))


def main():
    global STOP
    def stop(*_):
        global STOP
        STOP = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    mysql = load_mysql_config()
    store = Store(mysql)
    for sql in Path(__file__).with_name('focus_schema.sql').read_text().split(';'):
        if sql.strip():
            store.execute(sql)
    env = focus_mail.runtime_env()
    # Reuse only the existing account, never a direct fallback on proxy failure.
    proxy = env.get('GREEN_PROXY_URL') or env.get('HTTPS_PROXY') or env.get('HTTP_PROXY')
    config = CrawlConfig(mysql=mysql, proxy=proxy, write_db=False, sleep_seconds=2)
    mail = focus_mail.mail_config(env)
    with mysql_connect(mysql, mysql.database) as guard:
        with guard.cursor() as c:
            c.execute("SELECT GET_LOCK('heavyequip-focus-scan',0) locked")
            if c.fetchone()['locked'] != 1:
                raise RuntimeError('another focus scanner is running')
        last_cleanup = 0
        while not STOP:
            try:
                if time.monotonic() - last_cleanup > 3600:
                    store.cleanup()
                    last_cleanup = time.monotonic()
                # Loss of the singleton connection must stop the process, not reconnect.
                guard.ping(reconnect=False)
                tick(store, config, mail)
            except Exception as error:
                print(json.dumps({'service': 'focus', 'error': type(error).__name__}), flush=True)
                guard.ping(reconnect=False)
            for _ in range(10):
                if STOP:
                    break
                time.sleep(1)


if __name__ == '__main__':
    main()
