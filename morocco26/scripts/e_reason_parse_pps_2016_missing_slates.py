#!/usr/bin/env python3
"""Parse PPS 2016 candidate identities for districts still missing from PJD.

The parser follows the frozen T1 evidence contract and the geometry calibrated
before this extraction revision. Each poster page represents one constituency.
For 2-3 seats candidate cards use one row around 62.3% page height. For 4-6
seats they use two rows around 51% and 73%; at most three cards per row.
Only the first text line at each calibrated card anchor is candidate identity;
biography/occupation lines immediately below are excluded by vertical geometry.
No legal list rank is inferred from poster position.
"""
from __future__ import annotations
import html,json,re,unicodedata
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import pdfplumber
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json';COV=ER/'evidence/pjd_2016_text_coverage/coverage.json';AUD=ER/'evidence/pps_2016_pdf_provenance_audit/audit.json';PTR=ER/'pps_2016_regional_pdf_probe_latest.json';OUT=ER/'evidence/pps_2016_parsed_missing_slates'
CRITICAL_REGIONS={'casablanca-settat','souss-massa','oriental','beni-mellal-khenifra','rabat-sale-kenitra','marrakech-safi'}
REGION_MATCH={'casablanca-settat':'casablanca settat','souss-massa':'souss massa','oriental':'oriental','beni-mellal-khenifra':'beni mellal khenifra','rabat-sale-kenitra':'rabat sale kenitra','marrakech-safi':'marrakech safi'}
TERRITORY_ALIASES={
 'فجيج':'figuig','فيجيج':'figuig','شتوكة ايت باها':'chtouka-ait-baha','شتوكة آيت باها':'chtouka-ait-baha','خريبكة':'khouribga',
 'انفا':'casablanca-anfa','آنفا':'casablanca-anfa','عين السبع الحي المحمدي':'ain-sebaa-hay-mohammadi','عين السبع':'ain-sebaa-hay-mohammadi',
 'سيدي البرنوصي':'sidi-bernoussi','مولاي رشيد':'moulay-rachid','المحمدية':'mohammadia','برشيد':'berrechid','الصويرة':'essaouira',
 'الغرب':'el-gharb','الخميسات':'khemisset-ouelmes','الخميسات والماس':'khemisset-ouelmes','تيفلت الرماني':'tiflet-rommani','تيفلت - الرماني':'tiflet-rommani','سيدي قاسم':'sidi-kacem',
}
CID_RE=re.compile(r'\(?cid:\d+\)?|\)?\d+:dic\(?',re.I)
def clean(v):return ' '.join(str(v or '').replace('\n',' ').split())
def norm_ar(s):
 x=unicodedata.normalize('NFKC',html.unescape(clean(s))).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}));x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x);x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def compact_ar(s):return norm_ar(s).replace(' ','')
def norm_latin(s):
 x=unicodedata.normalize('NFKD',str(s or ''));x=''.join(c for c in x if not unicodedata.combining(c)).casefold();return ' '.join(re.sub(r'[^a-z0-9]+',' ',x).split())
def logical_word(v):return unicodedata.normalize('NFKC',clean(v))[::-1]
def arabic_word(v):return bool(re.search(r'[\u0600-\u06FF]',unicodedata.normalize('NFKC',str(v or ''))))
def row_layout(seats):
 if seats<=3:return [(0.623,seats)]
 if seats==4:return [(0.510,2),(0.732,2)]
 if seats==5:return [(0.510,3),(0.732,2)]
 return [(0.510,3),(0.732,3)]
def resolve_name(raw_words,pypdf_lines):
 # Spatial words are in visual character order. Do not use CID-fragment tokens
 # as anchors because they represent a font-map loss, not literal name text.
 ordered=sorted(raw_words,key=lambda z:-float(z['x0']))
 logical=[logical_word(w['text']) for w in ordered]
 clean_tokens=[x for x,w in zip(logical,ordered) if not CID_RE.search(str(w['text'])) and norm_ar(x)]
 guess=clean(' '.join(logical));guess=clean(CID_RE.sub(' ',guess));anchors=[norm_ar(x) for x in clean_tokens if len(compact_ar(x))>=2]
 # If font-map CID loss occurred, recover the complete logical line only when
 # the remaining anchors identify exactly one pypdf text line on the same page.
 had_cid=any(CID_RE.search(str(w['text'])) for w in ordered)
 candidates=[]
 if anchors:
  for line in pypdf_lines:
   nl=norm_ar(line);cl=compact_ar(line)
   if 2<=len(nl.split())<=6 and all(compact_ar(a) in cl for a in anchors):candidates.append(nl)
  candidates=list(dict.fromkeys(candidates))
 if had_cid:
  if len(candidates)==1:return candidates[0],'UNIQUE_PYPDF_LINE_FROM_SPATIAL_ANCHORS',{'raw_words':[w['text'] for w in ordered],'anchors':anchors,'line_candidates':candidates}
  return None,'CID_FONTMAP_UNRESOLVED',{'raw_words':[w['text'] for w in ordered],'anchors':anchors,'line_candidates':candidates}
 # Without CID loss, the calibrated first line itself is the admissible table/poster evidence.
 ng=norm_ar(guess)
 if len(ng.split())>=2:return ng,'CALIBRATED_FIRST_CARD_LINE',{'raw_words':[w['text'] for w in ordered],'anchors':anchors,'pypdf_line_match':ng in [norm_ar(x) for x in pypdf_lines]}
 return None,'NAME_NOT_MULTIWORD',{'raw_words':[w['text'] for w in ordered],'anchors':anchors}
def main():
 cross=json.loads(CROSS.read_text(encoding='utf-8'));cov=json.loads(COV.read_text(encoding='utf-8'));aud=json.loads(AUD.read_text(encoding='utf-8'));ptr=json.loads(PTR.read_text(encoding='utf-8'));probe=json.loads((ROOT/ptr['latest_probe']).read_text(encoding='utf-8'))
 if cross.get('status')!='PASS':raise RuntimeError('Arabic bridge not PASS')
 if aud.get('counts',{}).get('mechanically_admissible_pdfs',0)<12:raise RuntimeError('latest PPS provenance audit must pass 12 regional PDFs')
 target={x['constituency_id'] for x in cov['missing'] if int(x['historical_seats_2016'])>=3};by_cid={r['source_2026_constituency_id']:r for r in cross['records']};patterns=defaultdict(set)
 for cid in target:
  r=by_cid[cid]
  for v in (r.get('name_ar'),r.get('name_ar_source_form'),r.get('name_ar_match_key')):
   if compact_ar(v):patterns[cid].add(compact_ar(v))
 for v,cid in TERRITORY_ALIASES.items():
  if cid in target:patterns[cid].add(compact_ar(v))
 passed_hash={r['probe_sha256']:r for r in aud['relationships'] if r['mechanical_pass']};docs=[x for x in probe['pdf_hits'] if x['region_slug'] in CRITICAL_REGIONS and x['sha256'] in passed_hash]
 territories=[];candidates=[];failures=[];page_diag=[]
 for d in docs:
  path=ROOT/d['pdf']['raw_path'];reader=PdfReader(str(path));rel=passed_hash[d['sha256']]
  with pdfplumber.open(str(path)) as pdf:
   if len(pdf.pages)!=len(reader.pages):raise RuntimeError('page-count mismatch')
   for i,(page,pypage) in enumerate(zip(pdf.pages,reader.pages),1):
    ptext=pypage.extract_text() or '';pc=compact_ar(ptext);lines=[clean(x) for x in ptext.splitlines() if clean(x)];possible=[]
    for cid in sorted(target):
     rr=by_cid[cid]
     if norm_latin(rr.get('historical_region'))!=REGION_MATCH[d['region_slug']]:continue
     matched=[pat for pat in patterns[cid] if pat and pat in pc]
     if matched:possible.append((cid,max(matched,key=len)))
    if len(possible)!=1:
     page_diag.append({'region':d['region_slug'],'page':i,'territory_candidates':[x[0] for x in possible],'status':'SKIP_TERRITORY_NOT_UNIQUE'});continue
    cid,matched=possible[0];rr=by_cid[cid];seats=int(rr['historical_seats_2016']);words=page.extract_words(use_text_flow=False,keep_blank_chars=False,x_tolerance=1,y_tolerance=1,extra_attrs=['size']) or []
    names=[];cards=[];errors=[];layout=row_layout(seats);w=float(page.width);h=float(page.height);left=.07*w;right=.93*w;span=right-left
    for row_no,(anchor_frac,ncols) in enumerate(layout):
     anchor=anchor_frac*h;tolerance=.015*h;row_words=[x for x in words if arabic_word(x['text']) and abs(float(x['top'])-anchor)<=tolerance]
     bins=[[] for _ in range(ncols)]
     for x in row_words:
      center=(float(x['x0'])+float(x['x1']))/2;pos=(center-left)/span;bi=min(ncols-1,max(0,int(pos*ncols)));bins[bi].append(x)
     # Display card order is irrelevant to list rank, but use right-to-left for stable evidence excerpts.
     for bi in reversed(range(ncols)):
      name,method,detail=resolve_name(bins[bi],lines);cards.append({'row':row_no,'bin_from_left':bi,'anchor_fraction':anchor_frac,'method':method,'detail':detail,'candidate_name_ar':name})
      if name:names.append(name)
      else:errors.append(f'UNRESOLVED_CARD_row{row_no}_bin{bi}')
    if len(names)!=seats:errors.append(f'CANDIDATE_COUNT_{len(names)}_NE_SEATS_{seats}')
    if len({compact_ar(x) for x in names})!=len(names):errors.append('DUPLICATE_CANDIDATE_IDENTITY')
    page_diag.append({'region':d['region_slug'],'page':i,'constituency_id':cid,'historical_constituency':rr['historical_constituency'],'seats':seats,'matched_territory_pattern':matched,'layout':layout,'cards':cards,'errors':errors})
    if errors:failures.append(page_diag[-1]);continue
    excerpt={'page':i,'territory_pattern':matched,'layout':layout,'candidate_cards':cards};territories.append({'year':2016,'party':'PPS','constituency_id':cid,'historical_id_constituency':rr['historical_id_constituency'],'historical_constituency':rr['historical_constituency'],'historical_region':rr['historical_region'],'seats':seats,'candidate_count':seats,'FORMAL_ENDORSEMENT':True,'source_class':'T1_OFFICIAL_PARTY','pdf_sha256':d['sha256'],'parent_page_url':rel['page_url'],'parent_page_timestamps':rel['page_timestamps'],'evidence_excerpt':excerpt})
    for display_no,name in enumerate(names,1):candidates.append({'year':2016,'party':'PPS','constituency_id':cid,'historical_id_constituency':rr['historical_id_constituency'],'historical_constituency':rr['historical_constituency'],'candidate_name_ar':name,'candidate_name_ar_normalized':norm_ar(name),'candidate_rank':None,'CANDIDATE_REGISTERED_RANK':None,'rank_evidence_status':'MISSING_NOT_INFERRED_FROM_POSTER_LAYOUT','FORMAL_ENDORSEMENT':True,'party_fact_status':'PARTY_ANNOUNCED','poster_display_order_only':display_no,'evidence':{'publication_time':rel['page_timestamps'][0] if rel['page_timestamps'] else None,'retrieval_time':aud['created_at'],'source_class':'T1_OFFICIAL_PARTY','content_sha256':d['sha256'],'parent_page_url':rel['page_url'],'page':i,'archived_excerpt':excerpt}})
 byterr=defaultdict(list)
 for c in candidates:byterr[c['constituency_id']].append(c)
 identity=sum(len({x['candidate_name_ar_normalized'] for x in xs})>=3 for xs in byterr.values());payload={'schema_version':'2.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'PARTIAL_VALID','target_missing_ge3_districts':sorted(target),'territory_rows':territories,'candidate_rows':candidates,'failures':failures,'page_diagnostics':page_diag,'counts':{'target_missing_ge3':len(target),'territories_recovered':len(territories),'candidate_rows':len(candidates),'recovered_districts_with_at_least_three_verified_candidate_identities':identity},'invariants':{'geometry_calibration_precedes_parser_revision':True,'candidate_rank_inferred_from_layout':False,'biography_lines_excluded_by_anchor_geometry':True,'failed_pages_promoted':False,'source_only_T1_pre_cutoff':True,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'parsed_missing_slates.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'counts':payload['counts'],'territories':[x['historical_constituency'] for x in territories],'failure_count':len(failures),'failure_sample':[{'constituency':x.get('historical_constituency'),'region':x.get('region'),'page':x.get('page'),'errors':x.get('errors')} for x in failures[:12]]},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
