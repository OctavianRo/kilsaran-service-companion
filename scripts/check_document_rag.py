"""Verify expanded document retrieval and grounded answers before activation."""
import concurrent.futures
import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.check_live_rag import load_config
from backend.rag import OpenAI,answer_question

CASES=[
    ('How much water should I mix with a 25kg bag of KPRO Masonry Cladding Mortar?','DOC100'),
    ('What laying depths and bag size are specified for KPRO LevelEase 225?','DOC1346'),
    ('What is the 28-day compressive strength and final setting time of KPRO Crete Post 10?','DOC106'),
    ('How much water does a 25kg bag of Ceresit CT136 Dry Dash Receiver need?','DOC364'),
    ('What is KPRO Repair CRM-201 used for?',None),
    ('What water supply and hose does a mortar silo require?',None),
    ('The silo mixer is blocked. How do I fix it?',None),
    ('Does Kilsaran sell Quantum Unicorn Mortar 9000?',None),
]

if __name__=='__main__':
    load_config()
    state=json.loads((ROOT/'data/cache/replacement-vector-manifest.json').read_text())
    if not state.get('ready'):raise SystemExit('Replacement is not ready.')
    def check(case):
        question,doc=case
        p=OpenAI(os.environ['OPENAI_API_KEY'])
        if doc:
            hits=p.post(f'vector_stores/{state["vector_store_id"]}/search',{'query':question,'max_num_results':12,'rewrite_query':True})
            assert any('number='+doc==h.get('attributes',{}).get('url','').split('?')[-1] for h in hits['data']),f'Missing datasheet retrieval: {doc}'
        answer=answer_question(p,state['vector_store_id'],os.getenv('OPENAI_MODEL','gpt-4.1-mini'),question,[])
        if doc:assert answer['status']=='answered',question
        if 'Quantum Unicorn' in question:assert answer['status']=='not_found',question
        return {'question':question,'status':answer['status'],'answer':answer['answer'],'claims':answer['claims'],'sources':[{'url':s['url'],'title':s['title']} for s in answer['sources']]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(check,CASES))
    (ROOT/'data/cache/document-rag-evaluation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    for result in results:print(json.dumps(result,ensure_ascii=False),flush=True)
