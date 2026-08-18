#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def signature(path):
    with open(path,'rb') as f: return f.read(16).hex()

def inspect_stat(path, fmt):
    import pyreadstat
    if fmt=='dta': df, meta = pyreadstat.read_dta(path, metadataonly=True)
    elif fmt=='sav': df, meta = pyreadstat.read_sav(path, metadataonly=True)
    else: raise ValueError(fmt)
    names=list(meta.column_names); labels=list(meta.column_labels or [])
    cat={}
    for i,n in enumerate(names):
        cat[n]={'label':labels[i] if i<len(labels) else None,'value_labels':meta.variable_value_labels.get(n,{}) if getattr(meta,'variable_value_labels',None) else {}}
    return {'columns':len(names),'rows':getattr(meta,'number_rows',None),'variables':cat}

def inspect_xlsx(path):
    from openpyxl import load_workbook
    wb=load_workbook(path,read_only=True,data_only=True); out={}
    for ws in wb.worksheets:
        rows=ws.iter_rows(values_only=True); first=[]
        for _ in range(5):
            try:first.append(next(rows))
            except StopIteration:break
        out[ws.title]={'max_row':ws.max_row,'max_column':ws.max_column,'first_rows':[[None if v is None else str(v) for v in r] for r in first]}
    return {'sheets':out}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',required=True); ap.add_argument('--rawdir',required=True); ap.add_argument('--outdir',required=True); a=ap.parse_args()
    mani=json.load(open(a.manifest,encoding='utf-8')); raw=pathlib.Path(a.rawdir); out=pathlib.Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    audit=[]; catalog={}
    for s in mani['sources']:
        p=raw/(s['id']+'.bin'); rec={'id':s['id'],'url':s['url'],'role':s['role'],'exists':p.exists()}
        if not p.exists(): rec['status']='MISSING'; audit.append(rec); continue
        rec.update({'size_bytes':p.stat().st_size,'sha256':sha256(p),'signature_hex':signature(p)})
        try:
            if s['format'] in ('dta','sav'): ins=inspect_stat(str(p),s['format'])
            elif s['format']=='xlsx': ins=inspect_xlsx(str(p))
            else: ins={'note':'raw metadata/unknown format retained for manual/codebook parsing'}
            catalog[s['id']]=ins; rec['status']='PARSED'
            if 'columns' in ins: rec['columns']=ins['columns']; rec['rows']=ins.get('rows')
        except Exception as e:
            rec['status']='FETCHED_PARSE_FAILED'; rec['parse_error']=type(e).__name__+': '+str(e)
        audit.append(rec)
    counts={k:(catalog.get(k,{}).get('columns',0) or 0) for k in ['rgph2014_individual_dta','rgph2014_household_dta','encdm2014_household_sav','encdm2014_individual_sav','afrobarometer_morocco_r6','afrobarometer_morocco_r8']}
    parsed=[x['id'] for x in audit if x['status']=='PARSED']
    feasibility={'status':'SOURCE_CATALOG_READY' if counts['rgph2014_individual_dta'] and counts['rgph2014_household_dta'] and counts['afrobarometer_morocco_r6'] and counts['afrobarometer_morocco_r8'] else 'SOURCE_CATALOG_INCOMPLETE','raw_column_counts':counts,'parsed_source_count':len(parsed),'parsed_sources':parsed,'target_rich_dimensions_min':60,'important_note':'Raw column count is only a feasibility ceiling. Later scientific feature selection must exclude leakage, redundancy, unjustified sensitive features and post-cutoff variables.'}
    json.dump({'manifest_id':mani['manifest_id'],'sources':audit},open(out/'source_fetch_audit.json','w'),ensure_ascii=False,indent=2)
    json.dump(catalog,open(out/'variable_catalog.json','w'),ensure_ascii=False,indent=2)
    json.dump(feasibility,open(out/'richness_feasibility.json','w'),ensure_ascii=False,indent=2)
    print(json.dumps(feasibility,indent=2))
if __name__=='__main__': main()
