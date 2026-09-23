"""Refresh the local index from Kilsaran only. Reuses downloaded files."""
import concurrent.futures, hashlib, io, json, re, time, os, argparse, subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin, parse_qs
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
ROOT=Path(__file__).parent
CACHE=ROOT/'data/cache'; CACHE.mkdir(parents=True,exist_ok=True)
BASE='https://www.kilsaran.ie/'
REFRESH=False
robots=RobotFileParser()
DOCUMENT_HOST='g13660.ideagenqpulse.com'
def canonical_document(url):
 p=urlparse(url)
 if p.hostname==DOCUMENT_HOST and re.fullmatch(r'/qpulsedocumentservice/documents.svc/(live/)?documents/active/attachment',p.path,re.I):
  number=parse_qs(p.query).get('number',[''])[0].upper()
  if re.fullmatch(r'DOC\d+',number):return f'https://{DOCUMENT_HOST}/QPulseDocumentService/Documents.svc/documents/active/attachment?number={number}'
 return url.split('#')[0]
def allowed(url):
 p=urlparse(url)
 return p.scheme=='https' and not p.username and (p.port in (None,443)) and (p.hostname in {'kilsaran.ie','www.kilsaran.ie'} or (p.hostname==DOCUMENT_HOST and re.fullmatch(r'/qpulsedocumentservice/documents.svc/(live/)?documents/active/attachment',p.path,re.I) and re.fullmatch(r'DOC\d+',parse_qs(p.query).get('number',[''])[0],re.I)))
def permitted(url):
 return allowed(url) and (urlparse(url).hostname==DOCUMENT_HOST or robots.can_fetch('KilsaranServiceGuide',url))
def public_document_redirect(url):
 p=urlparse(url)
 target=parse_qs(p.query).get('requesturl',[''])[0]
 return (p.scheme=='https' and p.hostname==DOCUMENT_HOST and not p.username and p.port in (None,443)
         and p.path.lower() in {'/qpulsedocumentservice/databaseselection.aspx','/qpulsedocumentservice/login.aspx'}
         and target.startswith('/') and not target.startswith('//') and allowed(urljoin(url,target)))
def fetch(url):
 if not permitted(url): raise ValueError('Source not allowed')
 path=CACHE/hashlib.sha256(url.encode()).hexdigest()
 if path.exists() and not REFRESH:return path.read_bytes()
 for attempt in range(3):
  try:
   current=url
   session=requests.Session()
   for _ in range(6):
    r=session.get(current,timeout=45,allow_redirects=False,headers={'User-Agent':'KilsaranServiceGuide/1.0 (local product reference)'})
    if r.is_redirect:
     current=urljoin(current,r.headers['Location'])
     if not permitted(current) and not (urlparse(url).hostname==DOCUMENT_HOST and public_document_redirect(current)):raise ValueError('Redirect not allowed')
     continue
    r.raise_for_status()
    if len(r.content)>40_000_000: raise ValueError('Document too large')
    path.write_bytes(r.content);time.sleep(.15);return r.content
   raise ValueError('Too many redirects')
  except requests.RequestException:
   if attempt==2:raise
   time.sleep(1+attempt)
def locs(url):
 root=ET.fromstring(fetch(url))
 return [n.text for n in root.findall('{*}url/{*}loc')+root.findall('{*}sitemap/{*}loc')]
def html_doc(url):
 s=BeautifulSoup(fetch(url),'html.parser')
 title=s.title.get_text(' ',strip=True).split(' - Kilsaran')[0] if s.title else url.rstrip('/').split('/')[-1]
 links={}
 for a in s.select('a[href]'):
  link=canonical_document(urljoin(url,a['href']))
  if not allowed(link) or not ('.pdf' in urlparse(link).path.lower() or urlparse(link).hostname==DOCUMENT_HOST):continue
  row=a.find_parent(class_='td-files')
  product=row.select_one('.product-name') if row else None
  label=' | '.join(filter(None,[product.get_text(' ',strip=True) if product else title,a.get_text(' ',strip=True),('Plant: '+row.get('data-plant','')) if row and row.get('data-plant') else '']))
  links.setdefault(link,[]).append({'label':label,'source_page':url})
 for e in s.select('script,style,nav,header,footer,form,[data-elementor-type="header"],[data-elementor-type="footer"],.elementor-location-header,.elementor-location-footer'):e.decompose()
 main=s.select_one('main') or s.select_one('[data-elementor-type="single-post"]') or s.body or s
 lines=[]
 for e in main.select('h1,h2,h3,h4,p,li,tr'):
  if e.find_parent(['li','tr']):continue
  t=re.sub(r'\s+',' ',e.get_text(' ',strip=True))
  if len(t)>25 and t not in lines and not any(x in t.lower() for x in ['cookie','all rights reserved','see full brochure']):lines.append(t)
 return {'title':title,'url':url,'kind':'page','sections':[{'text':'\n'.join(lines),'page':None}]},links
def pdf_doc(item):
 url,refs=item
 refs=sorted(refs,key=lambda r:(not r['source_page'].endswith('/technical-library/'),r['label'],r['source_page']))
 title=refs[0]['label']
 raw=fetch(url)
 if not raw.lstrip().startswith(b'%PDF'):
  if b'does not have direct access to this file' in raw:raise ValueError('Kilsaran document service says its server does not have direct access to this file (HTML returned instead of PDF).')
  raise ValueError('Download returned a non-PDF response; document unavailable')
 reader=PdfReader(io.BytesIO(raw))
 sections=[{'text':p.extract_text() or '', 'page':i+1} for i,p in enumerate(reader.pages)]
 weak=[s['page'] for s in sections if len(s['text'].strip())<30]
 if weak and os.getenv('PDF_OCR_COMMAND'):
  ocr_cache=CACHE/(hashlib.sha256(raw).hexdigest()+'.ocr.json')
  if ocr_cache.exists():ocr=json.loads(ocr_cache.read_text())
  else:
   result=subprocess.run([os.environ['PDF_OCR_COMMAND'],str(CACHE/hashlib.sha256(url.encode()).hexdigest()),','.join(map(str,weak))],capture_output=True,text=True,check=True,timeout=300)
   ocr=json.loads(result.stdout);ocr_cache.write_text(json.dumps(ocr))
  for part in ocr:
   if len(part['text'].strip())>len(sections[part['page']-1]['text'].strip()):sections[part['page']-1].update(text=part['text'],extraction='ocr')
 if not any(s['text'].strip() for s in sections):raise ValueError('PDF needs OCR; no readable text')
 return {'title':title or url.split('/')[-1].replace('-',' '),'url':url,'kind':'pdf','sections':sections,'references':refs,'unreadable_pages':[s['page'] for s in sections if len(s['text'].strip())<30]}
def run():
 global REFRESH
 REFRESH='--refresh' in __import__('sys').argv
 robots.parse(requests.get(BASE+'robots.txt',timeout=30).text.splitlines())
 urls=[]
 for sm in locs(BASE+'sitemap_index.xml'):
  if any(x in sm for x in ['kilsaran_product-sitemap','product_cat-sitemap','page-sitemap']):urls.extend(locs(sm))
 urls=sorted(set(u for u in urls if allowed(u))|{BASE+'technical-library/'})
 docs=[];pdfs={};errors=[]
 print(f'Discovered {len(urls)} pages',flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  futures={pool.submit(html_doc,u):u for u in urls}
  for i,f in enumerate(concurrent.futures.as_completed(futures)):
   try:
    d,links=f.result();docs.append(d)
    for link,refs in links.items():
     pdfs.setdefault(link,[]).extend(ref for ref in refs if ref not in pdfs.get(link,[]))
   except Exception as e:errors.append({'url':futures[f],'error':str(e)})
   if (i+1)%25==0:print(f'Pages: {i+1}/{len(urls)}',flush=True)
  print(f'Discovered {len(pdfs)} PDFs',flush=True)
  futures={pool.submit(pdf_doc,item):item[0] for item in sorted(pdfs.items())}
  for i,f in enumerate(concurrent.futures.as_completed(futures)):
   try:docs.append(f.result())
   except Exception as e:errors.append({'url':futures[f],'error':str(e)})
   if (i+1)%25==0:print(f'PDFs: {i+1}/{len(pdfs)}',flush=True)
 result={'updated':datetime.now(timezone.utc).isoformat(),'discovered_pages':len(urls),'discovered_pdfs':len(pdfs),'documents':sorted(docs,key=lambda d:d['url']),'errors':errors,'document_inventory':[{'url':url,'references':refs} for url,refs in sorted(pdfs.items())]}
 if not docs:raise RuntimeError('No documents fetched; existing index preserved')
 if len(pdfs)>50 and sum(d['kind']=='pdf' for d in docs)<len(pdfs)*.9:raise RuntimeError('More than 10% of PDF downloads failed; existing index preserved. Inspect access and retry.')
 target=ROOT/'data/knowledge.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False));os.replace(temp,target)
 print(f'Saved {len(docs)} sources; {len(errors)} failures',flush=True)
if __name__=='__main__':run()
