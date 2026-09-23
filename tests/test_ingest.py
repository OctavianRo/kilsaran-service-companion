import unittest
from unittest.mock import patch
import ingest
from backend.sources import trusted_source

URL = 'https://g13660.ideagenqpulse.com/QPulseDocumentService/Documents.svc/documents/active/attachment?number=DOC80'

class DocumentDiscoveryTests(unittest.TestCase):
    def test_extensionless_documents_and_product_context(self):
        html = f'''<title>Technical Library - Kilsaran</title><div class="td-files" data-plant="test"><div class="product-name">Mortar M4</div><a href="{URL}">TDS</a></div>'''
        with patch('ingest.fetch', return_value=html.encode()):
            _, links = ingest.html_doc('https://www.kilsaran.ie/technical-library/')
        self.assertIn(URL, links)
        self.assertIn('Mortar M4', links[URL][0]['label'])
        self.assertIn('TDS', links[URL][0]['label'])

    def test_live_redirect_is_same_document(self):
        self.assertEqual(ingest.canonical_document(URL.replace('Documents.svc/', 'documents.svc/Live/')), URL)

    def test_public_session_redirect_stays_on_document_endpoint(self):
        from urllib.parse import quote
        redirect='https://g13660.ideagenqpulse.com/QPulseDocumentService/Login.aspx?requesturl='
        self.assertTrue(ingest.public_document_redirect(redirect+quote('/QPulseDocumentService/documents.svc/Live/documents/active/attachment?number=DOC80')))
        self.assertFalse(ingest.public_document_redirect(redirect+quote('https://evil.example/')))

    def test_only_official_tenant_and_document_endpoint_allowed(self):
        self.assertTrue(trusted_source(URL))
        for bad in [URL.replace('g13660', 'other'), URL.replace('https:', 'http:'), URL.replace('attachment', 'admin'), URL.replace('DOC80', 'invalid'), URL.replace('g13660.', 'user@g13660.')]:
            self.assertFalse(trusted_source(bad), bad)
