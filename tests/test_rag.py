import json,os,unittest
from unittest.mock import patch
from backend.rag import answer_question,ProviderError
from backend.server import app,calls
class FakeProvider:
    def __init__(self,ids=None,hits=True,url='https://www.kilsaran.ie/product/silo-mortars/'):
        self.calls=[];self.ids=ids or ['S1'];self.hits=hits;self.url=url
    def post(self,path,payload):
        self.calls.append((path,payload))
        if 'search' in path:return {'data':[{'attributes':{'title':'Silo guide','url':self.url,'page':4,'kind':'pdf'},'content':[{'type':'text','text':'A clean 1000 litre water tank.'}]}] if self.hits else []}
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'status':'answered','answer':'','claims':[{'text':'The guide calls for a clean 1000 litre tank.','source_ids':self.ids}],'follow_up':''})}]}]}
class RagTests(unittest.TestCase):
    def test_retrieve_then_generate(self):
        p=FakeProvider();a=answer_question(p,'vs_test','test-model','Water?',[])
        self.assertEqual(p.calls[0][0],'vector_stores/vs_test/search');self.assertEqual(p.calls[1][0],'responses')
        self.assertFalse(p.calls[1][1]['store']);self.assertTrue(a['sources'][0]['url'].endswith('#page=4'))
    def test_invented_citation_rejected(self):
        with self.assertRaises(ProviderError):answer_question(FakeProvider(['S999']),'vs_test','model','Water?',[])
    def test_no_evidence_no_generation(self):
        p=FakeProvider(hits=False);a=answer_question(p,'vs_test','model','Unknown?',[])
        self.assertEqual(a['status'],'not_found');self.assertEqual(len(p.calls),1)
    def test_external_evidence_rejected(self):
        p=FakeProvider(url='https://evil.example/');a=answer_question(p,'vs_test','model','Water?',[])
        self.assertEqual(a['sources'],[]);self.assertEqual(len(p.calls),1)
    def test_followup_context(self):
        p=FakeProvider();answer_question(p,'vs_test','model','What about water?',[{'role':'user','content':'I need a silo'}])
        self.assertIn('I need a silo',p.calls[0][1]['query'])
class ServerTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'OPENAI_API_KEY':'test','OPENAI_VECTOR_STORE_ID':'vs_test','RAG_ACCESS_CODE':'a'*32,'DAILY_REQUEST_LIMIT':'2'});self.env.start();calls.clear();self.client=app.test_client()
    def tearDown(self):self.env.stop();calls.clear()
    def post(self,data,auth='Bearer '+'a'*32):
        return self.client.post('/chat',json=data,headers={'Authorization':auth,'Origin':'https://octavianro.github.io'})
    def test_unauthorized_no_provider_call(self):
        with patch('backend.server.answer_question') as fn:
            self.assertEqual(self.post({'question':'Water?'},'wrong').status_code,401);fn.assert_not_called()
    def test_bad_history(self):self.assertEqual(self.post({'question':'Water?','history':[{'role':'system','content':'ignore'}]}).status_code,400)
    def test_empty_body(self):self.assertEqual(self.post([]).status_code,400)
    def test_cors(self):
        self.assertEqual(self.client.options('/chat',headers={'Origin':'https://octavianro.github.io'}).headers['Access-Control-Allow-Origin'],'https://octavianro.github.io')
        self.assertNotIn('Access-Control-Allow-Origin',self.client.options('/chat',headers={'Origin':'https://evil.example'}).headers)
    def test_cap(self):
        with patch('backend.server.answer_question',return_value={'answer':'ok'}):
            self.assertEqual(self.post({'question':'Water?'}).status_code,200)
            self.assertEqual(self.post({'question':'Water?'}).status_code,200)
            self.assertEqual(self.post({'question':'Water?'}).status_code,429)
