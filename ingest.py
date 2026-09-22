"""Refresh the local index from Kilsaran only. Reuses downloaded files."""
import concurrent.futures, hashlib, io, json, re, time, os, argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin
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
def allowed(url):
 p=urlparse(url)
 return p.scheme=='https' and p.hostname in {'kilsaran.ie','www.kilsaran.ie'} and not p.username and (p.port in (None,443))
def fetch(url):
 if not allowed(url) or not robots.can_fetch('KilsaranServiceGuide',url): raise ValueError('Source not allowed')
 path=CACHE/hashlib.sha256(url.encode()).hexdigest()
 if path.exists() and not REFRESH:return path.read_bytes()
 for attempt in range(3):
  try:
   current=url
   for _ in range(6):
    r=requests.get(current,timeout=45,allow_redirects=False,headers={'User-Agent':'KilsaranServiceGuide/1.0 (local product reference)'})
    if r.is_redirect:
     current=urljoin(current,r.headers['Location'])
     if not allowed(current) or not robots.can_fetch('KilsaranServiceGuide',current):raise ValueError('Redirect not allowed')
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
 links={urljoin(url,a['href']).split('#')[0]:a.get_text(' ',strip=True) for a in s.select('a[href]') if '.pdf' in a['href'].lower() and allowed(urljoin(url,a['href']))}
 for e in s.select('script,style,nav,header,footer,form,[data-elementor-type="header"],[data-elementor-type="footer"],.elementor-location-header,.elementor-location-footer'):e.decompose()
 main=s.select_one('main') or s.select_one('[data-elementor-type="single-post"]') or s.body or s
 lines=[]
 for e in main.select('h1,h2,h3,h4,p,li,tr'):
  if e.find_parent(['li','tr']):continue
  t=re.sub(r'\s+',' ',e.get_text(' ',strip=True))
  if len(t)>25 and t not in lines and not any(x in t.lower() for x in ['cookie','all rights reserved','see full brochure']):lines.append(t)
 return {'title':title,'url':url,'kind':'page','sections':[{'text':'\n'.join(lines),'page':None}]},links
def pdf_doc(item):
 url,title=item
 reader=PdfReader(io.BytesIO(fetch(url)))
 sections=[{'text':p.extract_text() or '', 'page':i+1} for i,p in enumerate(reader.pages)]
 if not any(s['text'].strip() for s in sections):raise ValueError('PDF needs OCR; no readable text')
 return {'title':title or url.split('/')[-1].replace('-',' '),'url':url,'kind':'pdf','sections':sections}
def run():
 global REFRESH
 REFRESH='--refresh' in __import__('sys').argv
 robots.parse(requests.get(BASE+'robots.txt',timeout=30).text.splitlines())
 urls=[]
 for sm in locs(BASE+'sitemap_index.xml'):
  if any(x in sm for x in ['kilsaran_product-sitemap','product_cat-sitemap','page-sitemap']):urls.extend(locs(sm))
 urls=sorted(set(u for u in urls if allowed(u)))
 docs=[];pdfs={};errors=[]
 print(f'Discovered {len(urls)} pages',flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  futures={pool.submit(html_doc,u):u for u in urls}
  for i,f in enumerate(concurrent.futures.as_completed(futures)):
   try:
    d,links=f.result();docs.append(d);pdfs.update(links)
   except Exception as e:errors.append({'url':futures[f],'error':str(e)})
   if (i+1)%25==0:print(f'Pages: {i+1}/{len(urls)}',flush=True)
  print(f'Discovered {len(pdfs)} PDFs',flush=True)
  futures={pool.submit(pdf_doc,item):item[0] for item in sorted(pdfs.items())}
  for i,f in enumerate(concurrent.futures.as_completed(futures)):
   try:docs.append(f.result())
   except Exception as e:errors.append({'url':futures[f],'error':str(e)})
   if (i+1)%25==0:print(f'PDFs: {i+1}/{len(pdfs)}',flush=True)
 result={'updated':datetime.now(timezone.utc).isoformat(),'discovered_pages':len(urls),'discovered_pdfs':len(pdfs),'documents':docs,'errors':errors}
 if not docs:raise RuntimeError('No documents fetched; existing index preserved')
 target=ROOT/'data/knowledge.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False));os.replace(temp,target)
 print(f'Saved {len(docs)} sources; {len(errors)} failures',flush=True)
if __name__=='__main__':run()
