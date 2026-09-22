import unittest
from urllib.parse import urlparse
from app import knowledge,terms
from ingest import allowed
class SearchTests(unittest.TestCase):
 def test_silo_water(self):
  a=knowledge.answer('What water supply and hose does a mortar silo require?')
  self.assertEqual(a['sources'][0]['page'],4)
  self.assertIn('1000',a['sources'][0]['text'])
  self.assertIn('hose sizes',a['caution'])
 def test_power(self):
  a=knowledge.answer('What power does a silo need?')
  self.assertIn('Electrical Requirements',a['sources'][0]['text'])
 def test_unknown(self):
  self.assertEqual(knowledge.answer('xyzzyplugh')['sources'],[])
 def test_price_not_promised(self):
  self.assertIn('need confirmation',knowledge.answer('Current mortar prices')['message'])
 def test_typo(self):self.assertIn('mortar',terms('mortart bags'))
 def test_followup(self):
  a=knowledge.answer('What about power?','silo water requirements')
  self.assertIn('silo',a['query']);self.assertEqual(a['sources'][0]['page'],4)
 def test_sources_only(self):
  for s in knowledge.answer('paving flags')['sources']:
   self.assertIn(urlparse(s['url']).hostname,{'www.kilsaran.ie','kilsaran.ie'})
 def test_domain_boundaries(self):
  self.assertFalse(allowed('https://www.kilsaran.ie.evil.com/x'))
  self.assertFalse(allowed('http://localhost/x'))
  self.assertFalse(allowed('https://kilsaran.ie@evil.com/x'))
  self.assertTrue(allowed('https://www.kilsaran.ie/product/silo-mortars/'))
if __name__=='__main__':unittest.main()
