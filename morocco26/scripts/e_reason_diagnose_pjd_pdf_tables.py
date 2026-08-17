#!/usr/bin/env python3
"""Diagnose table geometry of the recovered 2016 PJD official-party PDFs.

No evidence promotion and no forecast effect. This only checks whether the
Excel-generated PDFs preserve enough table geometry to recover ordered candidate
names deterministically rather than splitting concatenated extracted text.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
LATEST=ER/'pjd_2016_documents_latest.json'
AUDIT=ER/'evidence/pjd_2016_provenance_audit/audit.json'
OUT=ER/'evidence/pjd_2016_pdf_table_diagnostic'


def clean(v):
    if v is None: return None
    return ' '.join(str(v).replace('\n',' ').split())


def main():
    audit=json.loads(AUDIT.read_text(encoding='utf-8'))
    if not audit.get('all_mechanical_checks_pass'):
        raise RuntimeError('PJD provenance audit is not 3/3 PASS')
    latest=json.loads(LATEST.read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/latest['latest_manifest']).read_text(encoding='utf-8'))
    docs=[x for x in manifest['documents'] if x.get('transport')=='CURRENT_STATIC_MIRROR_DISCOVERY_ONLY']
    rows=[]
    for doc in docs:
        p=ROOT/doc['raw_path']
        d={'article_id':doc['article_id'],'pdf_sha256':doc['sha256'],'path':doc['raw_path'],'pages':[]}
        with pdfplumber.open(str(p)) as pdf:
            for pi,page in enumerate(pdf.pages,1):
                page_rec={'page':pi,'width':page.width,'height':page.height,'tables':[],'word_lines':[]}
                # Excel PDFs usually preserve ruled table lines; test multiple
                # deterministic strategies without selecting one post hoc.
                strategies=[
                    ('lines', {'vertical_strategy':'lines','horizontal_strategy':'lines','intersection_tolerance':5,'snap_tolerance':3,'join_tolerance':3}),
                    ('lines_strict', {'vertical_strategy':'lines_strict','horizontal_strategy':'lines_strict','intersection_tolerance':5,'snap_tolerance':3,'join_tolerance':3}),
                    ('text', {'vertical_strategy':'text','horizontal_strategy':'text','min_words_vertical':2,'min_words_horizontal':1,'intersection_tolerance':5}),
                ]
                for label,settings in strategies:
                    try:
                        tables=page.extract_tables(settings) or []
                        compact=[]
                        for ti,t in enumerate(tables):
                            cleaned=[[clean(c) for c in r] for r in t]
                            nonempty=sum(any(c for c in r) for r in cleaned)
                            compact.append({'table_index':ti,'rows':len(cleaned),'cols_max':max((len(r) for r in cleaned),default=0),'nonempty_rows':nonempty,'sample_rows':cleaned[:12]})
                        page_rec['tables'].append({'strategy':label,'table_count':len(compact),'tables':compact})
                    except Exception as exc:
                        page_rec['tables'].append({'strategy':label,'error':f'{type(exc).__name__}: {exc}'})
                # Always preserve a coordinate-based fallback sample. We cluster
                # words by top coordinate, then sort by x descending for Arabic.
                words=page.extract_words(use_text_flow=False,keep_blank_chars=False,x_tolerance=2,y_tolerance=2) or []
                clusters=[]
                for w in sorted(words,key=lambda x:(round(float(x['top']),1),-float(x['x0']))):
                    top=float(w['top'])
                    target=None
                    for c in clusters:
                        if abs(c['top']-top)<=2.0:
                            target=c; break
                    if target is None:
                        target={'top':top,'words':[]}; clusters.append(target)
                    target['words'].append({'text':w['text'],'x0':round(float(w['x0']),2),'x1':round(float(w['x1']),2),'top':round(top,2)})
                for c in sorted(clusters,key=lambda x:x['top'])[:45]:
                    ws=sorted(c['words'],key=lambda x:-x['x0'])
                    page_rec['word_lines'].append({'top':round(c['top'],2),'text_rtl_order':' | '.join(x['text'] for x in ws),'words':ws})
                d['pages'].append(page_rec)
        rows.append(d)
    payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'documents':rows,'invariants':{'evidence_promoted':False,'predictive_judgments_generated':False,'outcomes_unsealed':False,'F1_created':False}}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'diagnostic.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary=[]
    for d in rows:
        s={'article_id':d['article_id'],'pages':len(d['pages']),'strategies':[]}
        for p in d['pages']:
            s['strategies'].append({'page':p['page'],'table_counts':{x['strategy']:x.get('table_count') for x in p['tables'] if 'table_count' in x}})
        summary.append(s)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
