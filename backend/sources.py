"""Public Kilsaran sources, including its explicitly linked document tenant."""
import re
from urllib.parse import urlparse, parse_qs

def trusted_source(url):
    try:
        p = urlparse(url)
        if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
            return False
        if p.hostname in {'kilsaran.ie', 'www.kilsaran.ie'}:
            return True
        return bool(
            p.hostname == 'g13660.ideagenqpulse.com'
            and re.fullmatch(r'/qpulsedocumentservice/documents.svc/(live/)?documents/active/attachment', p.path, re.I)
            and re.fullmatch(r'DOC\d+', parse_qs(p.query).get('number', [''])[0], re.I)
        )
    except (ValueError, TypeError):
        return False
