"""Run a small live evaluation without printing credentials."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.rag import OpenAI,answer_question

def load_config():
    for line in (ROOT/'.env').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key,value=line.split('=',1);os.environ[key.strip()]=value.strip().strip('\"').strip("'")
if __name__=='__main__':
    load_config();state=json.loads((ROOT/'data/vector-manifest.json').read_text())
    if not state.get('ready'):raise SystemExit('Indexing must complete before evaluation.')
    provider=OpenAI(os.environ['OPENAI_API_KEY'])
    for q in ['What water supply and hose does a mortar silo require?','How many bags are on a pallet?','What is the price of mortar and can it arrive tomorrow?','Does Kilsaran sell a product called Quantum Unicorn Mortar 9000?']:
        a=answer_question(provider,state['vector_store_id'],os.getenv('OPENAI_MODEL','gpt-4.1-mini'),q,[])
        print(json.dumps({'question':q,'status':a['status'],'answer':a['answer'],'claims':a['claims'],'follow_up':a['follow_up'],'sources':[{'id':s['id'],'title':s['title'],'url':s['url']} for s in a['sources']]},ensure_ascii=False),flush=True)
