"""Build the self-contained GitHub Pages site without credentials or local files."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs';OUT.mkdir(exist_ok=True)
html=(ROOT/'static/index.html').read_text().replace('href="/"','href="./"').replace('href="/style.css"','href="./style.css"').replace('src="/app.js"','src="./app.js"').replace('<script src="./app.js">','<script src="./search.js"></script><script src="./rag-client.js"></script><script src="./app.js">').replace('Local workspace','Browser workspace').replace('Independent internal reference tool','Independent reference · Not affiliated with Kilsaran')
(OUT/'index.html').write_text(html)
css=(ROOT/'static/style.css').read_text()
# Avoid third-party font requests on the public site.
css='\n'.join(line for line in css.splitlines() if not line.startswith('@import'))
(OUT/'style.css').write_text(css)
(OUT/'search.js').write_text((ROOT/'static/search.js').read_text())
js=(ROOT/'static/app.js').read_text()
js="let enginePromise;\nfunction getEngine(){if(!enginePromise)enginePromise=fetch('./knowledge.json').then(r=>{if(!r.ok)throw Error('Source library failed to load. Please reload.');return r.json()}).then(data=>wrapRagEngine(new KilsaranSearch(data))).catch(e=>{enginePromise=null;throw e});return enginePromise;}\n"+js
js=js.replace("status=await(await fetch('/api/status')).json()","status=(await getEngine()).status()")
js=js.replace('Source library unavailable. Check the local server.','Source library unavailable. Check your connection and reload.')
start="const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,previous,category})});const data=await res.json();if(!res.ok)throw Error(data.error);"
assert start in js
js=js.replace(start,"const data=await (await getEngine()).answer(q,previous,category);")
js=js.replace("previous=data.query.slice(-2500)||q","previous=(data.query||q).slice(-2500)")
js=js.replace("if(index===0)","if(index===0 && data.mode!=='rag')")
(OUT/'app.js').write_text(js)
(OUT/'rag-client.js').write_text((ROOT/'static/rag-client.js').read_text())
if not (OUT/'config.json').exists():(OUT/'config.json').write_text(json.dumps({'ragApiUrl':''}))
data=json.loads((ROOT/'data/knowledge.json').read_text())
# Publish only known public-source fields. Never include filesystem paths or secrets.
for d in data['documents']:
 assert d['url'].startswith(('https://www.kilsaran.ie/','https://kilsaran.ie/'))
data['errors']=[{'url':e['url'],'error':'Source unavailable or PDF has no readable text. See original source.'} for e in data['errors']]
(OUT/'knowledge.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
(OUT/'.nojekyll').touch()
print(f'Built {len(data["documents"])} sources into docs/')
