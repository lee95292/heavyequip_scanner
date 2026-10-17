import json
import datetime as dt
import unittest
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
from crawl import focus_scan as f
from test_focus_scan import FakeStore, NOW, factory, row, rule


class MailSnapshotTests(unittest.TestCase):
    def test_allowlist_and_contact_snapshot_saved_before_smtp(self):
        store = f.Store(None)
        store.execute = Mock(return_value=1)
        listing = row(contact='010-0000-0000', seller='광고 판매자', raw={'secret':'excluded'})
        self.assertTrue(store.prepare_mail(rule(), f.identity(listing), listing))
        sql, args = store.execute.call_args.args
        self.assertIn('listing_snapshot_json', sql)
        snapshot = json.loads(args[-1])
        self.assertEqual(snapshot['contact'], '010-0000-0000')
        self.assertEqual(snapshot['seller'], '광고 판매자')
        self.assertEqual(snapshot['version'], 1)
        self.assertEqual(snapshot['contact_status'], 'available')
        self.assertTrue(snapshot['captured_at'].endswith('+09:00'))
        self.assertNotIn('raw', snapshot)
        self.assertNotIn('secret', str(snapshot))

    def test_scalar_whitelist_and_field_limits(self):
        snapshot = f.listing_snapshot(row(contact={'invalid':1}, seller='x'*500, description='x'*5000))
        self.assertIsNone(snapshot['contact'])
        self.assertEqual(len(snapshot['seller']), 240)
        self.assertEqual(len(snapshot['description']), 4000)

    def test_detail_contact_only_and_list_values_preserved(self):
        crawler = Mock()
        crawler.parse_detail.return_value = {'contact':'010-0000-0000','price':'999만원','model_name':None,'location':'서울'}
        listing = row(location='경기', seller='판매자')
        enriched = f.mail_listing(crawler, listing, FakeStore(), '100105')
        self.assertEqual(enriched['contact'], '010-0000-0000')
        self.assertEqual(enriched['price'], listing['price'])
        self.assertEqual(enriched['model_name'], listing['model_name'])
        self.assertEqual(enriched['location'], '경기')
        self.assertNotIn('contact', listing)

    def test_contact_is_from_labeled_detail_not_footer(self):
        crawler = object.__new__(f.GreenHeavyCrawler)
        crawler.get_soup = Mock(return_value=BeautifulSoup('<table><tr><th>연락처</th><td>010-0000-0000</td></tr></table><footer>고객센터 02-9999-9999</footer>', 'html.parser'))
        self.assertEqual(crawler.parse_detail(row()['detail_url'])['contact'], '010-0000-0000')
        crawler.get_soup.return_value = BeautifulSoup('<footer>고객센터 02-9999-9999</footer>', 'html.parser')
        self.assertIsNone(crawler.parse_detail(row()['detail_url'])['contact'])

    def test_contact_missing_and_failure_are_explicit(self):
        for detail, status in [({'model_name':'EW145B'}, 'missing'), ({}, 'fetch_failed'), ({'detail_title':None,'model_name':None,'manufacturer':None,'manufactured_ym':None,'contact':None}, 'fetch_failed'), (RuntimeError('private data'), 'fetch_failed')]:
            crawler = Mock()
            if isinstance(detail, Exception): crawler.parse_detail.side_effect = detail
            else: crawler.parse_detail.return_value = detail
            store = FakeStore()
            enriched = f.mail_listing(crawler, row(), store, '100105')
            self.assertEqual(enriched['_contact_status'], status)
            self.assertEqual(enriched['price'], row()['price'])
            self.assertNotIn('private data', str(store.logs))

    def test_budget_and_pause_are_not_swallowed(self):
        for error in [f.BudgetExceeded(), InterruptedError()]:
            crawler = Mock(); crawler.parse_detail.side_effect = error
            with self.assertRaises(type(error)): f.mail_listing(crawler, row(), FakeStore(), '100105')

    def test_access_and_rate_limit_errors_are_not_swallowed(self):
        for status in (400, 401, 403, 407, 429):
            error = f.requests.HTTPError('blocked', response=Mock(status_code=status))
            crawler = Mock(); crawler.parse_detail.side_effect = error
            with self.assertRaises(f.requests.HTTPError):
                f.mail_listing(crawler, row(), FakeStore(), '100105')

    @patch.object(f, 'stamp', return_value=NOW)
    def test_one_detail_for_fifty_recipients_and_none_on_replay(self, _):
        alerts = [dict(rule(), id=i) for i in range(1, 51)]
        store = FakeStore({'boundary_json':[f.identity(row('old'))], 'last_success_at':NOW-dt.timedelta(minutes=10)})
        create, crawler = factory([[row('new'), row('old')], [row('new'), row('old')]])
        crawler.parse_detail.return_value = {'contact':'010-0000-0000'}
        with patch.object(f.focus_mail, 'send') as send:
            self.assertEqual(f.scan_category(store, dict(rule(), _scan=True), '100105', None, {}, factory=create, rules=alerts), 50)
            self.assertEqual(f.scan_category(store, dict(rule(), _scan=True), '100105', None, {}, factory=create, rules=alerts), 0)
        crawler.parse_detail.assert_called_once()
        self.assertEqual(send.call_count, 50)
        self.assertTrue(all(call.args[2]['contact']=='010-0000-0000' for call in send.call_args_list))

    @patch.object(f, 'stamp', return_value=NOW)
    def test_no_detail_for_baseline_or_nonmatching(self, _):
        for cursor, alerts in [(None, [rule()]), ({'boundary_json':['old'], 'last_success_at':NOW-dt.timedelta(minutes=10)}, [dict(rule(), model_contains='NO_MATCH')])]:
            create, crawler = factory([[row()]])
            f.scan_category(FakeStore(cursor), dict(rule(), _scan=True), '100105', None, {}, factory=create, rules=alerts)
            crawler.parse_detail.assert_not_called()

    def test_snapshot_save_failure_never_sends_or_replays(self):
        store = FakeStore(); store.prepare_mail = Mock(side_effect=RuntimeError('db failure'))
        with patch.object(f.focus_mail, 'send') as send:
            with self.assertRaises(RuntimeError): f.deliver(store, rule(), row(), {})
            self.assertFalse(f.deliver(store, rule(), row(), {}))
            send.assert_not_called()

    def test_uncertain_has_snapshot_before_send_and_no_replay(self):
        store = FakeStore(); snapshots = []
        store.prepare_mail = lambda r,k,v: snapshots.append(f.listing_snapshot(v)) or True
        def uncertain(*args):
            self.assertEqual(snapshots[0]['contact'], '010-0000-0000')
            raise f.focus_mail.DeliveryFailure(False)
        with patch.object(f.focus_mail, 'send', side_effect=uncertain) as send:
            self.assertFalse(f.deliver(store, rule(), row(contact='010-0000-0000'), {}))
            self.assertFalse(f.deliver(store, rule(), row(), {}))
            send.assert_called_once()

    def test_retention_same_history_row(self):
        store = f.Store(None); store.execute = Mock(); store.cleanup()
        statements = [call.args[0] for call in store.execute.call_args_list]
        mail_deletes = [s for s in statements if 'DELETE FROM focus_mail_history' in s]
        self.assertEqual(len(mail_deletes), 1)
        self.assertIn("status NOT IN ('sent','sending','uncertain')", mail_deletes[0])
        self.assertIn('INTERVAL 7 DAY', mail_deletes[0])

    def test_schema_additive_idempotent_and_race_safe(self):
        for existing, error in [(True,None),(False,None),(False,Exception(1060,'duplicate'))]:
            store = f.Store(None); store.query = Mock(return_value=[{}] if existing else [])
            def execute(sql):
                if sql.startswith('ALTER') and error: raise error
            store.execute = Mock(side_effect=execute)
            store.ensure_schema()
            alters = [c for c in store.execute.call_args_list if c.args[0].startswith('ALTER')]
            self.assertEqual(len(alters), 0 if existing else 1)
        store = f.Store(None); store.query = Mock(return_value=[])
        store.execute = Mock(side_effect=lambda sql: (_ for _ in ()).throw(Exception(1142,'denied')) if sql.startswith('ALTER') else None)
        with self.assertRaises(Exception): store.ensure_schema()


if __name__ == '__main__': unittest.main()
