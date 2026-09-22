"""Local, source-grounded customer service assistant. No cloud account needed."""
import json, re, sqlite3, threading, os
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
ROOT=Path(__file__).parent
STOP=set('a an the and or to of for in on with is are was be do does can could would should i me my you your customer wants want know about please tell what which how much many any it that this they need have has get use using thanks thank'.split())
ALIASES={'mortart':'mortar','hoses':'hose','bags':'bag','silos':'silo','electricity':'power electrical','electric':'electrical','water':'water pressure','setup':'site requirements','blocked':'blockage','blockages':'blockage','cleaning':'clean maintenance','paving':'paving paving','tonnes':'tonne','power':'power electrical','supply':'supply requirements','require':'requirements','weight':'weight kg','cost':'price','prices':'price','stock':'availability','refill':'delivery','mixing':'mix mixer','cement':'cement','pallets':'pallet','size':'size diameter','hosepipe':'hose'}
def terms(q):
 out=[]
 for w in re.findall(r'[a-z0-9]+',q.lower()):
  if w not in STOP:
   for t in ALIASES.get(w,w).split():
    if t not in out:out.append(t)
 return out[:32]
class Knowledge:
 def __init__(self,path=ROOT/'data/knowledge.json'):
  self.path=path;self.stamp=None;self.lock=threading.Lock();self.db=None;self.load()
 def load(self):
  stamp=self.path.stat().st_mtime if self.path.exists() else None
  if self.db is not None and stamp==self.stamp:return
  self.stamp=stamp
  self.data=json.loads(self.path.read_text()) if stamp else {'documents':[],'errors':[],'updated':None}
  if self.db:self.db.close()
  self.db=sqlite3.connect(':memory:',check_same_thread=False)
  self.db.execute('CREATE VIRTUAL TABLE chunks USING fts5(title, text, url UNINDEXED, page UNINDEXED, kind UNINDEXED, tokenize="porter unicode61")')
  for d in self.data['documents']:
   for section in d['sections']:
    # Overlapping paragraphs retain context; PDF page stays attached to every passage.
    lines=[x.strip() for x in section['text'].splitlines() if x.strip()]
    blocks=[];part=''
    for line in lines:
     if len(part)>1200 and d['kind']!='pdf':blocks.append(part);part=''
     part+='\n'+line
    if part.strip():blocks.append(part.strip())
    for b in blocks:self.db.execute('INSERT INTO chunks VALUES (?,?,?,?,?)',(d['title'],b,d['url'],section['page'],d['kind']))
  self.db.commit()
 def status(self):
  with self.lock:
   self.load();d=self.data
   return {'updated':d['updated'],'pages':sum(x['kind']=='page' for x in d['documents']),'pdfs':sum(x['kind']=='pdf' for x in d['documents']),'failures':len(d['errors']),'errors':d['errors'],'discovered_pages':d.get('discovered_pages',0),'discovered_pdfs':d.get('discovered_pdfs',0)}
 def answer(self,question,previous='',category='All products'):
  original=terms(question)
  if not original:return {'message':'Ask about a Kilsaran product or a specific customer question.','sources':[]}
  q=question
  if previous and (len(original)<5 or re.search(r'\b(it|that|those|they|its)\b',question.lower())):q=previous+' '+question
  if category!='All products':q+=' '+category
  ts=terms(q)
  expr=' OR '.join('"'+t+'"' for t in ts)
  with self.lock:
   self.load()
   rows=self.db.execute('SELECT title,text,url,page,kind,bm25(chunks,3,1) FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks,3,1) LIMIT 100',(expr,)).fetchall()
  scored=[]
  for title,body,url,page,kind,rank in rows:
   normalized=' '.join(terms(title+' '+body))
   matches=sum(bool(re.search(r'\b'+re.escape(t),normalized)) for t in ts)
   direct=sum(bool(re.search(r'\b'+re.escape(t),normalized)) for t in original)
   score=(-rank)*(0.3+matches/max(len(ts),1)) + 2*direct
   if 'silo' in ts and ('silo' in title.lower()):score+=7
   if 'hose' in ts and 'hose' in body.lower():score+=3
   if 'silo' in ts and kind=='pdf' and 'silo user guide' in title.lower():
    score+=5
    if set(ts)&{'water','electrical','power','hose','requirements'} and 'Electrical Requirements' in body and 'Water Requirements' in body:score+=20
    if set(ts)&{'clean','maintenance'} and 'Daily Cleaning' in body:score+=18
   if 'bag' in ts and 'mortar' in ts and 'masonry' in title.lower():score+=5
   scored.append((score,direct,{'title':title,'text':body,'url':url+(f'#page={page}' if page else ''),'page':page,'kind':kind,'table':bool(re.search(r'FAULT/ISSUE\s+CAUSE\s+SOLUTION',body))}))
  scored.sort(key=lambda x:x[0],reverse=True)
  sources=[];seen=set()
  for score,direct,s in scored:
   if direct==0:continue
   key=s['url']
   if key in seen:continue
   seen.add(key);sources.append(s)
   if len(sources)==4:break
  dynamic=bool(set(original)&{'price','availability','discount','quote'})
  message='Here are the closest passages from Kilsaran’s published information. Check the linked document for the full instructions and product suitability.'
  if not sources:message='I couldn’t find supporting information in the indexed Kilsaran sources. Please confirm with Kilsaran; I don’t have a verified answer.'
  elif dynamic:message='Current prices, stock and delivery commitments need confirmation from Kilsaran. These published references may help identify the product.'
  elif scored and scored[0][1]<max(1,len(original)*.55):message='I found related information, but not a verified answer to every part of this question. Please confirm missing details with Kilsaran.'
  caution=None
  if re.search(r'hose|silo|electri|blockage|blocked|pressure|repair',q,re.I):
   caution='For equipment work, follow the complete current silo guide and its isolation and safety instructions. Confirm unlisted hose sizes, fittings or replacement parts with Kilsaran support.'
  return {'message':message,'sources':sources,'caution':caution,'query':q}
knowledge=Knowledge()
class Handler(BaseHTTPRequestHandler):
 def send(self,code,data,ctype='application/json'):
  if not isinstance(data,bytes):data=json.dumps(data).encode()
  self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/api/status':return self.send(200,knowledge.status())
  files={'/':('index.html','text/html; charset=utf-8'),'/style.css':('style.css','text/css'),'/app.js':('app.js','text/javascript')}
  if path not in files:return self.send(404,{'error':'Not found'})
  name,ctype=files[path];self.send(200,(ROOT/'static'/name).read_bytes(),ctype)
 def do_POST(self):
  if self.path!='/api/chat':return self.send(404,{'error':'Not found'})
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<1 or n>16000:return self.send(400,{'error':'Message too large or empty'})
   d=json.loads(self.rfile.read(n));q=d.get('question','');previous=d.get('previous','');category=d.get('category','All products')
   if not all(isinstance(x,str) for x in [q,previous,category]) or not q.strip() or len(q)>1500 or len(previous)>3000:return self.send(400,{'error':'Enter a question of up to 1,500 characters.'})
   self.send(200,knowledge.answer(q,previous,category))
  except (ValueError,TypeError):self.send(400,{'error':'Invalid request'})
if __name__=='__main__':
 port=int(os.environ.get('PORT','8765'));print(f'Kilsaran guide ready at http://localhost:{port}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
