#!/usr/bin/env python3
"""Parse PPS 2016 candidate identities for districts still missing from PJD.

Only mechanically-admissible PPS PDFs are used. Territory is resolved through
the audited Arabic->TAFRA-2016 bridge. Candidate names are recovered from the
large-font candidate band of each one-constituency poster page. A page is
accepted only if exactly historical seat-magnitude non-empty candidate columns
are recovered. List rank is intentionally left MISSING because poster columns
are not assumed to encode legal list order.
"""
from __future__ import annotations
import hashlib,html,json,re,unicodedata
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
import pdfplumber
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json';COV=ER/'evidence/pjd_2016_text_coverage/coverage.json';AUD=ER/'evidence/pps_2016_pdf_provenance_audit/audit.json';PTR=ER/'pps_2016_regional_pdf_probe_latest.json';OUT=ER/'evidence/pps_2016_parsed_missing_slates'
CRITICAL_REGIONS={'casablanca-settat','souss-massa','oriental','beni-mellal-khenifra'}
REGION_MATCH={'casablanca-settat':'casablanca settat','souss-massa':'souss massa','oriental':'oriental','beni-mellal-khenifra':'beni mellal khenifra'}
# Known historical Arabic spelling variants are identity-only and outcome-free.
TERRITORY_ALIASES={'فجيج':'figuig','فيجيج':'figuig','شتوكة ايت باها':'chtouka-ait-baha','شتوكة آيت باها':'chtouka-ait-baha','خريبكة':'khouribga','انفا':'casablanca-anfa','آنفا':'casablanca-anfa','عين السبع الحي المحمدي':'ain-sebaa-hay-mohammadi','عين السبع':'ain-sebaa-hay-mohammadi','سيدي البرنوصي':'sidi-bernoussi','مولاي رشيد':'moulay-rachid','المحمدية':'mohammadia','برشيد':'berrechid'}
def clean(v):return ' '.join(str(v or '').replace('\n',' ').split())
def norm_ar(s):
 x=unicodedata.normalize('NFKC',html.unescape(clean(s))).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}));x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x);x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def compact_ar(s):return norm_ar(s).replace(' ','')
def norm_latin(s):
 x=unicodedata.normalize('NFKD',str(s or ''));x=''.join(c for c in x if not unicodedata.combining(c)).casefold();return ' '.join(re.sub(r'[^a-z0-9]+',' ',x).split())
def logical_word(v):
 # pdfplumber spatial words are stored in visual codepoint order for these PDFs.
 return unicodedata.normalize('NFKC',clean(v))[::-1]
def arabic_word(v):return bool(re.search(r'[\u0600-\u06FF]',unicodedata.normalize('NFKC',str(v or ''))))
def main():
 cross=json.loads(CROSS.read_text(encoding='utf-8'));cov=json.loads(COV.read_text(encoding='utf-8'));aud=json.loads(AUD.read_text(encoding='utf-8'));ptr=json.loads(PTR.read_text(encoding='utf-8'));probe=json.loads((ROOT/ptr['latest_probe']).read_text(encoding='utf-8'))
 if cross.get('status')!='PASS':raise RuntimeError('Arabic bridge not PASS')
 if aud.get('status')!='PASS_PARTIAL':raise RuntimeError('PPS provenance audit not PASS_PARTIAL')
 target={x['constituency_id'] for x in cov['missing'] if int(x['historical_seats_2016'])>=3}
 by_cid={r['source_2026_constituency_id']:r for r in cross['records']}
 # Build Arabic identity patterns only for missing >=3 districts.
 patterns=defaultdict(set)
 for cid in target:
  r=by_cid[cid]
  for v in (r.get('name_ar'),r.get('name_ar_source_form'),r.get('name_ar_match_key')):
   if compact_ar(v):patterns[cid].add(compact_ar(v))
 for v,cid in TERRITORY_ALIASES.items():
  if cid in target:patterns[cid].add(compact_ar(v))
 passed_hash={r['probe_sha256']:r for r in aud['relationships'] if r['mechanical_pass']}
 docs=[x for x in probe['pdf_hits'] if x['region_slug'] in CRITICAL_REGIONS and x['sha256'] in passed_hash]
 territories=[];candidates=[];failures=[];page_diag=[]
 for d in docs:
  path=ROOT/d['pdf']['raw_path'];reader=PdfReader(str(path));rel=passed_hash[d['sha256']]
  with pdfplumber.open(str(path)) as pdf:
   if len(pdf.pages)!=len(reader.pages):raise RuntimeError('page-count mismatch between extractors')
   for i,(page,pypage) in enumerate(zip(pdf.pages,reader.pages),1):
    ptext=pypage.extract_text() or '';pc=compact_ar(ptext)
    # Region filter + missing-target patterns make identity resolution conservative.
    possible=[]
    for cid in sorted(target):
     rr=by_cid[cid]
     if norm_latin(rr.get('historical_region'))!=REGION_MATCH[d['region_slug']]:continue
     matched=[pat for pat in patterns[cid] if pat and pat in pc]
     if matched:possible.append((cid,max(matched,key=len)))
    if len(possible)!=1:
     page_diag.append({'region':d['region_slug'],'page':i,'territory_candidates':[x[0] for x in possible],'status':'SKIP_TERRITORY_NOT_UNIQUE'});continue
    cid,matched=possible[0];rr=by_cid[cid];seats=int(rr['historical_seats_2016'])
    words=page.extract_words(use_text_flow=False,keep_blank_chars=False,x_tolerance=2,y_tolerance=2,extra_attrs=['size']) or []
    # Candidate names occupy a stable large-font band around 60-66% page height;
    # occupation/biography text is smaller. Bounds are geometry, not content.
    selected=[]
    for w in words:
     size=float(w.get('size') or 0);top=float(w['top'])
     if 12.0<=size<=16.5 and 0.585*float(page.height)<=top<=0.655*float(page.height) and arabic_word(w['text']):selected.append(w)
    # Equal-width poster panels. Assign each large-font word by center to one of
    # `seats` columns; this is used only if every column becomes non-empty.
    left=0.07*float(page.width);right=0.93*float(page.width);span=right-left
    bins=[[] for _ in range(seats)]
    for w in selected:
     center=(float(w['x0'])+float(w['x1']))/2
     pos=(center-left)/span;idx=min(seats-1,max(0,int(pos*seats)));bins[idx].append(w)
    names=[];bin_diag=[]
    for bi,ws in enumerate(bins):
     # Spatial right-to-left word order, then visual->logical codepoint reversal.
     toks=[logical_word(w['text']) for w in sorted(ws,key=lambda z:-float(z['x0']))]
     name=clean(' '.join(toks));names.append(name);bin_diag.append({'bin_from_left':bi,'raw_words':[w['text'] for w in sorted(ws,key=lambda z:-float(z['x0']))],'logical_name':name})
    errors=[]
    if len(names)!=seats or any(len(norm_ar(x).split())<2 for x in names):errors.append('NOT_EXACTLY_ONE_MULTIWORD_NAME_PER_SEAT_COLUMN')
    if len({compact_ar(x) for x in names if compact_ar(x)})!=seats:errors.append('DUPLICATE_OR_EMPTY_CANDIDATE')
    page_diag.append({'region':d['region_slug'],'page':i,'constituency_id':cid,'historical_constituency':rr['historical_constituency'],'seats':seats,'matched_territory_pattern':matched,'selected_large_font_words':len(selected),'bins':bin_diag,'errors':errors})
    if errors:
     failures.append(page_diag[-1]);continue
    excerpt={'page':i,'territory_pattern':matched,'candidate_geometry_bins':bin_diag}
    territories.append({'year':2016,'party':'PPS','constituency_id':cid,'historical_id_constituency':rr['historical_id_constituency'],'historical_constituency':rr['historical_constituency'],'historical_region':rr['historical_region'],'seats':seats,'candidate_count':seats,'FORMAL_ENDORSEMENT':True,'source_class':'T1_OFFICIAL_PARTY','pdf_sha256':d['sha256'],'parent_page_url':rel['page_url'],'parent_page_timestamps':rel['page_timestamps'],'evidence_excerpt':excerpt})
    for display_col,name in enumerate(reversed(names),1):
     candidates.append({'year':2016,'party':'PPS','constituency_id':cid,'historical_id_constituency':rr['historical_id_constituency'],'historical_constituency':rr['historical_constituency'],'candidate_name_ar':name,'candidate_name_ar_normalized':norm_ar(name),'candidate_rank':None,'CANDIDATE_REGISTERED_RANK':None,'rank_evidence_status':'MISSING_NOT_INFERRED_FROM_POSTER_COLUMN','FORMAL_ENDORSEMENT':True,'party_fact_status':'PARTY_ANNOUNCED','display_column_from_right':display_col,'evidence':{'publication_time':rel['page_timestamps'][0] if rel['page_timestamps'] else None,'retrieval_time':aud['created_at'],'source_class':'T1_OFFICIAL_PARTY','content_sha256':d['sha256'],'parent_page_url':rel['page_url'],'page':i,'archived_excerpt':excerpt}})
 byterr=defaultdict(list)
 for c in candidates:byterr[c['constituency_id']].append(c)
 identity=sum(len({x['candidate_name_ar_normalized'] for x in xs})>=3 for xs in byterr.values())
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'PARTIAL_VALID','target_missing_ge3_districts':sorted(target),'territory_rows':territories,'candidate_rows':candidates,'failures':failures,'page_diagnostics':page_diag,'counts':{'target_missing_ge3':len(target),'territories_recovered':len(territories),'candidate_rows':len(candidates),'recovered_districts_with_at_least_three_verified_candidate_identities':identity},'invariants':{'candidate_rank_inferred_from_layout':False,'failed_pages_promoted':False,'source_only_T1_pre_cutoff':True,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'parsed_missing_slates.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'counts':payload['counts'],'territories':[x['historical_constituency'] for x in territories],'failure_count':len(failures),'failures':[{'constituency':x.get('historical_constituency'),'region':x.get('region'),'page':x.get('page'),'errors':x.get('errors')} for x in failures]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
