"""Build a separate, resumable replacement index. Never activates it automatically."""
import concurrent.futures
import hashlib
import json
import os
import sys
import time
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.index_vectors import export
from scripts.check_live_rag import load_config

def run():
    load_config()
    items=export()
    digest=hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()
    path=ROOT/'data/cache/replacement-vector-manifest.json'
    state=json.loads(path.read_text()) if path.exists() else {}
    if state and state['corpus_hash']!=digest:
        raise SystemExit('Corpus changed since this replacement started; preserve the manifest before rebuilding.')
    headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY']}
    def api(method,endpoint,**kwargs):
        for attempt in range(5):
            r=requests.request(method,'https://api.openai.com/v1/'+endpoint,headers=headers,timeout=(15,120),**kwargs)
            if r.status_code not in (429,500,502,503):break
            time.sleep(2**attempt)
        if not r.ok:raise RuntimeError(f'Index request failed: HTTP {r.status_code}; progress preserved.')
        return r.json()
    def save():
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2));tmp.replace(path)
    if not state:
        store=api('POST','vector_stores',json={'name':'Build complete technical library '+digest[:10]})
        state={'corpus_hash':digest,'vector_store_id':store['id'],'files':{},'batches':[],'ready':False};save()
    store=state['vector_store_id']
    pending=[i for i in items if i['filename'] not in state['files']]
    print(f'Replacement: {len(items)} source pages, {len(pending)} uploads remaining.',flush=True)
    def upload(item):
        r=api('POST','files',data={'purpose':'assistants'},files={'file':(item['filename'],item['content'].encode(),'text/plain')})
        return item['filename'],r['id']
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for n,(name,fid) in enumerate(pool.map(upload,pending),1):
            state['files'][name]={'id':fid};save()
            if n%100==0:print(f'Uploaded {n}/{len(pending)}',flush=True)
    # Reconcile attachments before resuming an interrupted batch submission.
    attached=set();after=None
    while True:
        params={'limit':100}
        if after:params['after']=after
        page=api('GET',f'vector_stores/{store}/files',params=params)
        attached.update(f['id'] for f in page['data'])
        if not page.get('has_more'):break
        after=page['last_id']
    pending=[i for i in items if state['files'][i['filename']]['id'] not in attached]
    for start in range(0,len(pending),100):
        group=pending[start:start+100]
        batch=api('POST',f'vector_stores/{store}/file_batches',json={'files':[{'file_id':state['files'][i['filename']]['id'],'attributes':i['attributes']} for i in group],'chunking_strategy':{'type':'static','static':{'max_chunk_size_tokens':800,'chunk_overlap_tokens':200}}})
        state['batches'].append(batch['id']);save()
        print(f'Attached {min(start+100,len(pending))}/{len(pending)}',flush=True)
    for _ in range(180):
        counts=api('GET','vector_stores/'+store)['file_counts']
        print('Index status: '+json.dumps(counts),flush=True)
        if not counts['in_progress']:
            if counts['failed'] or counts['cancelled'] or counts['completed']!=len(items):raise RuntimeError('Index incomplete. Do not activate.')
            state['ready']=True
            for entry in state['files'].values():entry['attached']=True
            save();print('Replacement ready for verification.',flush=True);return
        time.sleep(10)
    raise RuntimeError('Index still processing; rerun later.')

if __name__=='__main__':run()
