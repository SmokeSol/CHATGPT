#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json, math, re, unicodedata
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
HROOT=ROOT/'data'/'goal100'/'historical'
RAWROOT=ROOT/'data'/'goal100'/'older_history_probe'/'raw'
ACCESS_DATE='2026-08-19'
ALLOWED_XW={'EXACT','RENAMED','SPLIT','MERGED','PARTIAL','AMBIGUOUS','UNRESOLVED'}
META={'idRegion','idWilaya','idPrefProv','idSousPref','idCirconscription','region','wilaya','prefProv','sousPref','circonscription','typeListe','nSieges','nInscrits','txParticipation','pctNuls'}

CONFIG={
  2002:{
    'raw':'parlement-elections-2002-1-0.xlsx','expected':91,'local_seats':295,'threshold':0.03,
    'source_origin':'TAFRA_COMPOSITE_PARTIAL','matrix_status':'PARTIAL_MAJOR_PARTIES_ONLY',
    'source_url':'https://open.africa/dataset/863697f2-bffa-4607-afe7-2c38d6b78adf/resource/19018416-2921-4abf-87a2-463160892f07/download/parlement-elections-2002-1-0.xlsx',
    'source_note':'TAFRA: primary Le Matin coverage incomplete; secondary source contains errors; small-party results unavailable.',
    'official_result_url':'https://lematin.ma/journal/2002/Resultats--du-scrutin-legislatif-du-27-septembre-portant-sur-64-circonscriptions/21192.html',
    'final_result_url':'https://data.ipu.org/election-summary/HTML/2221_02.htm',
    'local_seats_by_party':{'USFP':45,'PI':43,'RNI':38,'PJD':38,'MP':25,'MNP':16,'UC':14,'PND':10,'FFD':10,'PPS':9,'UD':9,'MDS':7,'PSD':6,'ALAHD':5,'ADL':4,'PSU':3,'PRD':3,'PML':3,'PFC':2,'PED':2,'PDI':2,'CNI':1},
    'total_seats_by_party':{'USFP':50,'PI':48,'PJD':42,'RNI':41,'MP':27,'MNP':18,'UC':16,'PND':12,'FFD':12,'PPS':11,'UD':10,'MDS':7,'PSD':6,'ALAHD':5,'ADL':4,'PSU':3,'PRD':3,'PML':3,'PDI':2,'PED':2,'PFC':2,'CNI':1},
  },
  2007:{
    'raw':'parlement-elections-2007-1-0.xlsx','expected':95,'local_seats':295,'threshold':0.06,
    'source_origin':'TAFRA_ARCHIVE_OF_OFFICIAL_ELECTIONS2007_GOV_MA','matrix_status':'OFFICIAL_ARCHIVE_FULL_LOCAL_PARTY_MATRIX',
    'source_url':'https://open.africa/dataset/1f48eeec-ff94-46a2-ae8e-ed56b66dd529/resource/0ec47fad-4f8a-4753-b107-82b0cc76d94c/download/parlement-elections-2007-1-0.xlsx',
    'source_note':'TAFRA archived copy of official elections2007.gov.ma results.',
    'official_result_url':'https://assahraa.ma/journal/2007/47193',
    'final_result_url':'https://data.ipu.org/election-summary/HTML/1221_07.htm',
    'local_seats_by_party':{'PI':46,'PJD':40,'MP':36,'RNI':34,'USFP':33,'UC':27,'PPS':14,'FFD':9,'MDS':9,'PNDALAHD':8,'ALAHD':3,'PND':3,'PADSCNIPSU':5,'CNI':1,'PT':5,'PED':5,'SAP_GROUP':5,'PRE':4,'PS':2,'UMD':2,'PFC':1,'ADL':1,'ICD':1,'PRV':1},
    'total_seats_by_party':{'PI':52,'PJD':46,'MP':41,'RNI':39,'USFP':38,'UC':27,'PPS':17,'FFD':9,'MDS':9,'PNDALAHD_GROUP':14,'PADSCNIPSU_GROUP':6,'PT':5,'PED':5,'SAP_GROUP':5,'PRE':4,'PS':2,'UMD':2,'PFC':1,'ADL':1,'ICD':1,'PRV':1},
  }
}

def sha_file(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def dump(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def clean(v):
    if pd.isna(v): return None
    if hasattr(v,'item'):
        try: v=v.item()
        except Exception: pass
    if isinstance(v,float) and v.is_integer(): return int(v)
    return v

def norm(s):
    s=unicodedata.normalize('NFKD',str(s or ''))
    s=''.join(c for c in s if not unicodedata.combining(c)).lower()
    s=s.replace('’',"'").replace('–','-')
    s=re.sub(r'[^a-z0-9]+',' ',s)
    return ' '.join(s.split())

def read_modern():
    p=ROOT/'data'/'constituencies_goal75.csv'
    with p.open(encoding='utf-8') as f: rows=list(csv.DictReader(f))
    return p,rows

# Only mappings backed by transparent naming/known administrative continuity; no fuzzy matching.
EXPLICIT={
  2002:{
    norm("Aïn Chock-Hay Hassani"):("SPLIT",['ain-chock','hay-hassani'],'Explicit 2007 split and modern separate districts.'),
    norm("Ben M'sick-Médiouna"):("SPLIT",['ben-m-sick','mediouna'],'Modern map separates Ben M\'sick and Médiouna.'),
    norm('Taroudannt Al Janoubia'):("RENAMED",['taroudant-sud'],'Directional name normalized to modern Sud.'),
    norm('Taroudannt Achamalia'):("RENAMED",['taroudant-nord'],'Directional name normalized to modern Nord.'),
    norm('Safi Chamalia'):("MERGED",['safi'],'Historical north component now part of single Safi district.'),
    norm('Safi Al Janoubia'):("MERGED",['safi'],'Historical south component now part of single Safi district.'),
    norm('Khouribga-Ouled Lbher Kbar et Sghar'):("MERGED",['khouribga'],'Historical Khouribga component now in single modern Khouribga district.'),
    norm('Oued Zem-Abi Jaâd'):("MERGED",['khouribga'],'Historical Khouribga provincial component now in single modern Khouribga district; not treated exact.'),
  },
  2007:{
    norm('Aïn Chock'):("EXACT",['ain-chock'],'Name identity.'),
    norm('Hay Hassani'):("EXACT",['hay-hassani'],'Name identity.'),
  }
}

def crosswalk(year,native_rows):
    modern_path,modern=read_modern(); byn={norm(r['name']):r for r in modern}
    rows=[]
    for r in native_rows:
        n=norm(r['constituency'])
        if n in EXPLICIT.get(year,{}):
            typ,ids,note=EXPLICIT[year][n]
            targets=[m for m in modern if m['constituency_id'] in ids]
        elif n in byn:
            typ='EXACT'; targets=[byn[n]]; note='Normalized exact constituency-name identity only.'
        else:
            typ='UNRESOLVED'; targets=[]; note='No exact-name or explicitly documented mapping; intentionally unresolved.'
        assert typ in ALLOWED_XW
        rows.append({'year':year,'native_id':r['native_id'],'native_constituency':r['constituency'],
                     'mapping_type':typ,'modern_targets':[{'constituency_id':x['constituency_id'],'name':x['name']} for x in targets],
                     'note':note})
    return modern_path,rows

def allocate_largest_remainder(votes,seats,threshold):
    vals={k:float(v) for k,v in votes.items() if v is not None and float(v)>=0}
    total=sum(vals.values())
    eligible={k:v for k,v in vals.items() if total>0 and v/total>=threshold}
    if not eligible or seats<=0: return None
    useful=sum(eligible.values())
    q=useful/seats
    alloc={k:int(math.floor(v/q+1e-12)) for k,v in eligible.items()}
    used=sum(alloc.values())
    if used>seats: return None
    rema={k:v-alloc[k]*q for k,v in eligible.items()}
    for k in sorted(eligible,key=lambda x:(rema[x],eligible[x],x),reverse=True)[:seats-used]: alloc[k]+=1
    return {'threshold_denominator_vote_sum':total,'useful_vote_sum':useful,'quotient':q,'seats':alloc,'excluded_below_threshold':sorted(set(vals)-set(eligible))}

def grouped_2007_seats(d):
    out=dict(d)
    out['SAP_GROUP']=sum(out.pop(k,0) for k in ['SAP','SAP2','SAP3'])
    return {k:v for k,v in out.items() if v}

def build(year):
    cfg=CONFIG[year]; raw=RAWROOT/cfg['raw']; outdir=HROOT/str(year)
    if not raw.exists(): raise SystemExit(f'MISSING_RAW:{raw}')
    df=pd.read_excel(raw,sheet_name='données')
    if len(df)!=cfg['expected']: raise SystemExit(f'ROW_COUNT_FAIL:{year}:{len(df)}')
    party_cols=[c for c in df.columns if c not in META and not str(c).startswith('Unnamed')]
    rows=[]; reconstructed_ok=True
    recon_agg={}
    for i,rr in df.iterrows():
        votes={str(c):clean(rr[c]) for c in party_cols}
        row={'year':year,'native_id':f'M26-{year}-{i+1:03d}','id_region':clean(rr.get('idRegion')),'id_wilaya':clean(rr.get('idWilaya')),
             'id_prefprov':clean(rr.get('idPrefProv')),'id_souspref':clean(rr.get('idSousPref')),'id_constituency':clean(rr.get('idCirconscription')),
             'region':clean(rr.get('region')),'wilaya':clean(rr.get('wilaya')),'prefprov':clean(rr.get('prefProv')),
             'souspref':clean(rr.get('sousPref')),'constituency':clean(rr.get('circonscription')),'list_type':clean(rr.get('typeListe')),
             'magnitude':clean(rr.get('nSieges')),'registered_reported':clean(rr.get('nInscrits')),
             'turnout_rate_reported':clean(rr.get('txParticipation')),'invalid_rate_reported':clean(rr.get('pctNuls')),
             'votes':votes,'vote_matrix_status':cfg['matrix_status'],'source_origin':cfg['source_origin']}
        if year==2007:
            al=allocate_largest_remainder(votes,int(row['magnitude']),cfg['threshold'])
            row['local_seat_allocation_reconstructed']=al['seats'] if al else None
            if al:
                for k,v in al['seats'].items(): recon_agg[k]=recon_agg.get(k,0)+v
            else: reconstructed_ok=False
        else:
            row['local_seat_allocation_reconstructed']=None
            row['local_seat_allocation_status']='MISSING_INCOMPLETE_PARTY_VOTE_MATRIX_DO_NOT_INFER'
        rows.append(row)
    seat_sum=sum(int(r['magnitude']) for r in rows)
    seat_arith={'sum_native_magnitudes':seat_sum,'expected':cfg['local_seats'],'status':'PASS' if seat_sum==cfg['local_seats'] else 'FAIL'}
    if seat_arith['status']=='FAIL': raise SystemExit(f'SEAT_ARITH_FAIL:{year}:{seat_sum}')
    allocation_diag={'status':'NOT_RUN_INCOMPLETE_MATRIX' if year==2002 else 'AMBIGUOUS','computed_local_seats_by_party':None,'official_local_seats_by_party':cfg['local_seats_by_party']}
    if year==2007:
        comp=grouped_2007_seats(recon_agg)
        exp=cfg['local_seats_by_party']
        allocation_diag={'status':'PASS_EXACT_OFFICIAL_AGGREGATE_MATCH' if comp==exp else 'MISMATCH_REQUIRES_REVIEW',
                         'computed_local_seats_by_party':comp,'official_local_seats_by_party':exp,
                         'method':'threshold on documented party vote sum; below-threshold votes excluded from Hare quotient; largest remainder.'}
        if comp!=exp:
            for r in rows:
                r['local_seat_allocation_status']='AMBIGUOUS_ALLOCATOR_AGGREGATE_MISMATCH'
        else:
            for r in rows: r['local_seat_allocation_status']='VERIFIED_BY_EXACT_OFFICIAL_AGGREGATE_REPRODUCTION'
    local=cfg['local_seats_by_party']; total=cfg['total_seats_by_party']
    national={}
    if year==2002:
        for p,t in total.items(): national[p]=t-local.get(p,0)
    else:
        # National-list seats are the differences for parties with explicit total/local identities; grouped coalitions have zero national seats.
        national={'PI':6,'PJD':6,'MP':5,'RNI':5,'USFP':5,'PPS':3}
    canonical={'schema_version':'1.0','year':year,'election_date':'2002-09-27' if year==2002 else '2007-09-07',
               'source_origin':cfg['source_origin'],'source_quality_note':cfg['source_note'],'raw_sha256':sha_file(raw),
               'local_party_columns':party_cols,'local_rows':rows,
               'official_aggregate_seats':{'local':local,'national':national,'total':total},
               'vote_arithmetic':{'status':'NOT_EVALUABLE_EXACTLY','reason':'Exact valid-ballot counts are not a native workbook column; no arithmetic is fabricated from rounded turnout/invalid-rate fields.'},
               'seat_arithmetic':seat_arith,'district_seat_reconstruction':allocation_diag,
               'provenance_note':'The canonical filename is source-neutral; no false attribution to TAFRA as original authority.'}
    dump(outdir/f'legislative_{year}_outcome_canonical.json',canonical)
    native={'schema_version':'1.0','year':year,'source_layer':'OUTCOME_TRANSCRIPTION_ONLY',
            'warning':'NOT_AN_ELIGIBLE_PRE_ELECTION_SNAPSHOT_INPUT',
            'rows':[{'native_id':r['native_id'],'id_constituency':r['id_constituency'],'region':r['region'],'prefprov':r['prefprov'],'constituency':r['constituency'],'magnitude':r['magnitude']} for r in rows]}
    dump(outdir/'historical_native_map_outcome_transcription.json',native)
    dump(outdir/'historical_native_map.json',dict(native, artifact_role='CANONICAL_HISTORICAL_NATIVE_MAP_POST_FREEZE', scientific_boundary='May support geography/crosswalk reconstruction but MUST NOT be imported by the same-year pre-election snapshot generator.'))
    modern_path,xw=crosswalk(year,rows)
    dump(outdir/'crosswalk_to_modern.json',{'schema_version':'1.0','year':year,'modern_universe_path':str(modern_path.relative_to(ROOT)),'rows':xw,
                                            'policy':'Exact normalized names + small explicit mapping table only; no fuzzy coercion.'})
    sources=[
      {'source_id':f'OPENAFRICA_TAFRA_{year}','source_class':'T3' if year==2002 else 'T0','url':cfg['source_url'],'publication_date':None,'archive_date':None,'access_date':ACCESS_DATE,'territory':'ALL_LOCAL','party':None,'candidate':None,'fact':cfg['source_note'],'status':'AMBIGUOUS' if year==2002 else 'VERIFIED','provenance':cfg['source_origin']},
      {'source_id':f'OFFICIAL_AGGREGATE_{year}','source_class':'T2','url':cfg['official_result_url'],'publication_date':'2002-09-30' if year==2002 else '2007-09-11','archive_date':None,'access_date':ACCESS_DATE,'territory':'NATIONAL','party':None,'candidate':None,'fact':'Official Ministry of Interior aggregate local seat distribution.' if year==2002 else 'Final Ministry of Interior local + national seat results.','status':'VERIFIED','provenance':'POST_ELECTION_OUTCOME_SOURCE'},
      {'source_id':f'IPU_FINAL_{year}','source_class':'T0','url':cfg['final_result_url'],'publication_date':None,'archive_date':None,'access_date':ACCESS_DATE,'territory':'NATIONAL','party':None,'candidate':None,'fact':'Institutional final result cross-check.','status':'VERIFIED','provenance':'POST_ELECTION_OUTCOME_CROSSCHECK'}]
    dump(outdir/'source_inventory_outcome.json',{'schema_version':'1.0','year':year,'sources':sources})
    amb=[]
    if year==2002:
        amb.append({'type':'source_limitation','status':'AMBIGUOUS','fact':'District party-vote matrix omits small parties; source explicitly warns of incomplete primary coverage and errors in secondary reconstruction.'})
        amb.append({'type':'district_seats','status':'MISSING','fact':'Per-district seat allocation is not inferred from the incomplete 2002 vote matrix.'})
    if year==2007 and allocation_diag['status']!='PASS_EXACT_OFFICIAL_AGGREGATE_MATCH':
        amb.append({'type':'allocator_mismatch','status':'AMBIGUOUS','details':allocation_diag})
    dump(outdir/'ambiguities_outcome.json',{'year':year,'ambiguities':amb})
    exact=sum(1 for r in xw if r['mapping_type']=='EXACT'); approx=sum(1 for r in xw if r['mapping_type'] in {'RENAMED','SPLIT','MERGED','PARTIAL'}); unresolved=sum(1 for r in xw if r['mapping_type'] in {'AMBIGUOUS','UNRESOLVED'})
    cov={'year':year,'phase':'OUTCOME','real_constituency_count':cfg['expected'],'outcome_territory_rows':len(rows),
         'outcome_territory_coverage_pct':round(100*len(rows)/cfg['expected'],2),'party_columns_documented':len(party_cols),
         'local_vote_matrix_status':cfg['matrix_status'],'national_vote_counts_status':'MISSING',
         'official_local_seat_aggregate_status':'VERIFIED','official_total_seat_aggregate_status':'VERIFIED',
         'district_seat_allocation_status':allocation_diag['status'],
         'crosswalk_EXACT_count':exact,'crosswalk_EXACT_pct':round(100*exact/cfg['expected'],2),
         'crosswalk_APPROX_count':approx,'crosswalk_APPROX_pct':round(100*approx/cfg['expected'],2),
         'crosswalk_UNRESOLVED_count':unresolved,'crosswalk_UNRESOLVED_pct':round(100*unresolved/cfg['expected'],2)}
    dump(outdir/'coverage_outcome.json',cov)
    manifest={'schema_version':'1.0','year':year,'phase':'OUTCOME','generator':'historical_outcome_2002_2007.py','raw_input':str(raw.relative_to(ROOT)),'raw_sha256':sha_file(raw),'files':[]}
    for fn in [f'legislative_{year}_outcome_canonical.json','historical_native_map_outcome_transcription.json','historical_native_map.json','crosswalk_to_modern.json','source_inventory_outcome.json','ambiguities_outcome.json','coverage_outcome.json']:
        p=outdir/fn; manifest['files'].append({'path':str(p.relative_to(ROOT)),'sha256':sha_file(p)})
    dump(outdir/'outcome_manifest.json',manifest)
    dump(outdir/'outcome_hashes_sha256.json',{'year':year,'files':{fn:sha_file(outdir/fn) for fn in [f'legislative_{year}_outcome_canonical.json','historical_native_map_outcome_transcription.json','historical_native_map.json','crosswalk_to_modern.json','source_inventory_outcome.json','ambiguities_outcome.json','coverage_outcome.json','outcome_manifest.json']}})
    print(json.dumps({'year':year,'rows':len(rows),'party_cols':len(party_cols),'seat_sum':seat_sum,'allocator':allocation_diag['status'],'crosswalk_exact':exact,'crosswalk_approx':approx},sort_keys=True))

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--year',type=int,choices=[2002,2007],required=True); build(ap.parse_args().year)
