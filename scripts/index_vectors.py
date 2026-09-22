"""Export page-aware corpus; --upload provisions an OpenAI managed vector store."""
import argparse,hashlib,json,os,time
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]

def export():
    data=json.loads((ROOT/'data/knowledge.json').read_text());items=[]
    for doc in data['documents']:
        for section in doc['sections']:
            text=section['text'].strip()
            if not text:continue
            page=section['page'] or 0
            # Scrambled fault/cause/solution columns must never become model evidence.
            if 'FAULT/ISSUE' in text and 'SOLUTION' in text:
                text='This page is a troubleshooting table. Refer the user to the original PDF page and Kilsaran support; extracted column relationships are not reliable.'
            identity=doc['url']+'#'+str(page)
            filename=hashlib.sha256(identity.encode()).hexdigest()[:24]+'.txt'
            content=f"Title: {doc['title']}\nSource: {doc['url']}\nPDF page: {page or 'n/a'}\nIndexed: {data['updated']}\n\n{text}"
            attrs={'url':doc['url'],'title':doc['title'][:250],'page':page,'kind':doc['kind']}
            if len(attrs['url'])>512:raise ValueError('Source URL exceeds metadata limit')
            items.append({'filename':filename,'content':content,'attributes':attrs})
    return items

def run():
    parser=argparse.ArgumentParser();parser.add_argument('--upload',action='store_true');args=parser.parse_args()
    items=export();out=ROOT/'data/rag-export';out.mkdir(exist_ok=True)
    for item in items:(out/item['filename']).write_text(item['content'])
    print(f'Prepared {len(items)} page-aware source files.',flush=True)
    if not args.upload:return
    key=os.getenv('OPENAI_API_KEY')
    if not key:raise SystemExit('Set OPENAI_API_KEY in the environment; do not put it in the website.')
    path=ROOT/'data/vector-manifest.json';digest=hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()
    state=json.loads(path.read_text()) if path.exists() else {}
    if state and state.get('corpus_hash')!=digest:raise SystemExit('Corpus changed. Archive data/vector-manifest.json and rerun to create a replacement store. Switch the backend only after indexing completes; remove old cloud files manually after verification.')
    session=requests.Session();session.headers['Authorization']='Bearer '+key
    def api(method,endpoint,**kwargs):
        r=session.request(method,'https://api.openai.com/v1/'+endpoint,timeout=(10,90),**kwargs)
        if not r.ok:raise RuntimeError(f'OpenAI indexing request failed ({r.status_code}); progress is saved. Check account access and retry.')
        return r.json()
    def save():
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2));temp.replace(path)
    if not state:
        store=api('POST','vector_stores',json={'name':'Kilsaran customer service '+digest[:10]})
        state={'corpus_hash':digest,'vector_store_id':store['id'],'files':{},'ready':False};save()
    store=state['vector_store_id']
    for i,item in enumerate(items):
        entry=state['files'].setdefault(item['filename'],{})
        if not entry.get('id'):
            f=api('POST','files',data={'purpose':'assistants'},files={'file':(item['filename'],item['content'].encode(),'text/plain')});entry['id']=f['id'];save()
        if not entry.get('attached'):
            # GET first makes an interrupted attach resumable without a second attachment.
            existing=session.get(f'https://api.openai.com/v1/vector_stores/{store}/files/{entry["id"]}',timeout=30)
            if existing.status_code==404:
                api('POST',f'vector_stores/{store}/files',json={'file_id':entry['id'],'attributes':item['attributes'],'chunking_strategy':{'type':'static','static':{'max_chunk_size_tokens':800,'chunk_overlap_tokens':200}}})
            elif not existing.ok:raise RuntimeError('Unable to check file attachment; retry later.')
            entry['attached']=True;save()
        if (i+1)%20==0:print(f'Attached {i+1}/{len(items)}',flush=True)
    for _ in range(120):
        status=api('GET','vector_stores/'+store);counts=status['file_counts']
        if not counts['in_progress']:
            if counts['failed'] or counts['cancelled'] or counts['completed']!=len(items):raise RuntimeError('Some files did not index; inspect the vector store before activating it.')
            state['ready']=True;save();print('Ready. Set OPENAI_VECTOR_STORE_ID='+store);return
        time.sleep(5)
    raise RuntimeError('Indexing still in progress; rerun to check completion.')
if __name__=='__main__':run()
