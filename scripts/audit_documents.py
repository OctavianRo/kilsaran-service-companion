"""Reconcile every discovered download with extraction outcomes."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def audit():
    data=json.loads((ROOT/'data/knowledge.json').read_text())
    documents={d['url']:d for d in data['documents'] if d['kind']=='pdf'}
    failures={e['url']:e['error'] for e in data['errors']}
    rows=[]
    for item in data['document_inventory']:
        doc=documents.get(item['url'])
        rows.append({
            'url':item['url'], 'references':item['references'],
            'technical_datasheet':any(' | TDS' in r['label'] for r in item['references']),
            'status':'read' if doc else 'unavailable',
            'pages':len(doc['sections']) if doc else 0,
            'ocr_pages':[s['page'] for s in doc['sections'] if s.get('extraction')=='ocr'] if doc else [],
            'weak_pages':doc.get('unreadable_pages',[]) if doc else [],
            'error':failures.get(item['url'],'') if not doc else '',
        })
    summary={
        'updated':data['updated'],
        'discovered_documents':len(rows),
        'read_documents':sum(r['status']=='read' for r in rows),
        'unavailable_documents':sum(r['status']!='read' for r in rows),
        'technical_datasheets':sum(r['technical_datasheet'] for r in rows),
        'read_technical_datasheets':sum(r['technical_datasheet'] and r['status']=='read' for r in rows),
        'pdf_pages':sum(r['pages'] for r in rows),
        'ocr_pages':sum(len(r['ocr_pages']) for r in rows),
        'weak_pages':sum(len(r['weak_pages']) for r in rows),
    }
    (ROOT/'data/document-audit.json').write_text(json.dumps({'summary':summary,'documents':rows},ensure_ascii=False,indent=2))
    lines=['# Kilsaran document coverage audit','',f"Snapshot: {data['updated']}",'',
        f"- Discovered downloads: {summary['discovered_documents']}",
        f"- Successfully read: {summary['read_documents']}",
        f"- Technical datasheets read: {summary['read_technical_datasheets']} / {summary['technical_datasheets']}",
        f"- PDF pages: {summary['pdf_pages']}; OCR pages: {summary['ocr_pages']}",
        f"- Unavailable documents: {summary['unavailable_documents']}; blank or weak pages: {summary['weak_pages']}",'',
        'Coverage means text was extracted, not that every diagram or table was manually verified. Sources are public Kilsaran pages and the exact document-service tenant linked by Kilsaran. Shared links count once. Plant and product references are preserved in the JSON audit.','',
        '## Exceptions','']
    for row in rows:
        if row['status']!='read' or row['weak_pages']:
            title=row['references'][0]['label'].replace('|','—')
            lines.append(f"- [{title}]({row['url']}): {row['error'] or 'Blank/weak pages: '+str(row['weak_pages'])}")
    lines+=['','## Technical datasheets','', '| Datasheet | Status | Pages |','|---|---|---|']
    for row in rows:
        if row['technical_datasheet']:
            title=next(r['label'] for r in row['references'] if ' | TDS' in r['label']).replace('|','—')
            lines.append(f"| [{title}]({row['url']}) | {row['status']} | {row['pages']} |")
    (ROOT/'data/document-audit.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':audit()
