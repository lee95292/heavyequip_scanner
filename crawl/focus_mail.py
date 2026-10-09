"""Focus-only SMTP delivery; adapted from the existing CourtWatch-style mail helper."""
import os
import smtplib
import socket
import ssl
from contextlib import suppress
from email.message import EmailMessage
from email.utils import formataddr, formatdate, parseaddr
from html import escape
from pathlib import Path


def read_env(path):
    """Read literal dotenv values without interpolation or shell execution."""
    if not path or not Path(path).is_file():
        return {}
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.removeprefix('export ').split('=', 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '\"\'':
            value = value[1:-1]
        values[key.strip()] = value
    return values


def runtime_env():
    default = Path(__file__).resolve().parents[1] / 'crawl' / 'focus_private.env'
    return {**read_env(os.environ.get('FOCUS_ENV_PATH', str(default))), **os.environ}


def mail_config(env=None):
    env = runtime_env() if env is None else env
    values = {**read_env(env.get('MAIL_ENV_PATH')), **env}
    def get(name, fallback=''):
        return values.get('MAIL_' + name) or values.get('SMTP_' + name) or fallback
    port = int(get('PORT', '587'))
    return dict(enabled=get('ENABLED', 'true').lower() != 'false', host=get('HOST'),
                port=port, family=int(get('FAMILY', '4')),
                secure=get('SECURE', str(port == 465)).lower() == 'true',
                user=get('USER'), password=get('PASSWORD'), sender=get('FROM'))


def mail_ready(config):
    return config['enabled'] and all(config[k] for k in ('host', 'user', 'password', 'sender'))


class DeliveryFailure(Exception):
    def __init__(self, safe_retry):
        super().__init__('메일 전송 실패' if safe_retry else '전송 결과 불명확: 자동 재발송 중지')
        self.safe_retry = safe_retry


class SMTPConnection(smtplib.SMTP):
    def __init__(self, config):
        self.config = config
        super().__init__(config['host'], config['port'], timeout=10, local_hostname='scanner.local')

    def _get_socket(self, host, port, timeout):
        family = {4: socket.AF_INET, 6: socket.AF_INET6}.get(self.config['family'], socket.AF_UNSPEC)
        last_error = None
        for af, socktype, proto, _, address in socket.getaddrinfo(host, port, family, socket.SOCK_STREAM):
            sock = socket.socket(af, socktype, proto)
            try:
                sock.settimeout(timeout)
                sock.connect(address)
                if self.config['secure']:
                    sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
                return sock
            except OSError as error:
                sock.close()
                last_error = error
        raise last_error or OSError('SMTP connection failed')


def connect(config):
    connection = SMTPConnection(config)
    try:
        connection.ehlo()
        if not config['secure']:
            if not connection.has_extn('starttls'):
                raise smtplib.SMTPNotSupportedError('TLS required')
            connection.starttls(context=ssl.create_default_context())
            connection.ehlo()
        connection.login(config['user'], config['password'])
        connection.sock.settimeout(20)
        return connection
    except BaseException:
        connection.close()
        raise


def close(connection):
    with suppress(Exception):
        connection.quit()
    with suppress(Exception):
        connection.close()


def message(config, delivery, listing):
    msg = EmailMessage()
    msg['From'] = formataddr(('중장비 매물 알림', parseaddr(config['sender'])[1]))
    msg['To'] = delivery['email']
    msg['Subject'] = '[그린중기 신규 매물] ' + str(listing.get('model_name') or listing.get('listing_name') or '조건 일치')[:100].replace('\n', ' ').replace('\r', ' ')
    msg['Message-ID'] = f"<green-listing-{delivery['id']}@scan.mglee.dev>"
    msg['Date'] = formatdate(usegmt=True)
    lines = [str(listing.get('listing_name') or listing.get('model_name') or ''),
             f"가격: {listing.get('price') or '미상'}", f"연식: {listing.get('manufactured_ym') or '미상'}",
             str(listing.get('detail_url') or ''),
             '등록한 조건에 맞는 신규 수집 매물입니다. 가격 및 판매 여부는 판매자에게 확인하세요.',
             '알림 설정: https://scan.mglee.dev/ (집중탐색 탭에서 중지 가능)']
    text = '\n'.join(lines)
    msg.set_content(text)
    msg.add_alternative('<div style="font-family:sans-serif;line-height:1.7">' + '<br>'.join(escape(line) for line in lines) + '</div>', subtype='html')
    return msg


def send(config, delivery, listing):
    try:
        msg = message(config, delivery, listing)
        connection = connect(config)
    except Exception as error:
        raise DeliveryFailure(True) from error
    try:
        rejected = connection.send_message(msg)
        if rejected:
            raise DeliveryFailure(True)
    except Exception as error:
        safe = isinstance(error, smtplib.SMTPRecipientsRefused) or (
            isinstance(error, smtplib.SMTPResponseException) and 400 <= error.smtp_code < 600
        ) or isinstance(error, DeliveryFailure) and error.safe_retry
        raise DeliveryFailure(safe) from error
    finally:
        close(connection)
    return msg['Message-ID']
