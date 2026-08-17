#!/usr/bin/env python3
"""Parse PPS 2016 identities for districts still missing from PJD.

The calibrated poster geometry is card-based, not globally line-aligned. Each
candidate card is isolated by row + horizontal panel. Within that card, the
first Arabic text line is the candidate name; occupation/biography lines below
are excluded. A page is promoted only when exactly TAFRA-2016 seat magnitude
unique candidate identities are recovered. Poster position never implies rank.
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
TERRITORY_ALIASES={'فجيج':'figuig','فيجيج':'figuig','شتوكة ايت باها':'chtouka-ait-baha','شتوكة آيت باها':'chtouka-ait-baha','خريبكة':'khouribga','انفا':'casablanca-anfa','آنفا':'casablanca-anfa','عين السبع الحي المحمدي':'ain-sebaa-hay-mohammadi','عين السبع':'ain-sebaa-hay-mohammadi','سيدي البرنوصي':'sidi-bernoussi','مولاي رشيد':'moulay-rachid','المحمدية':'mohammadia','برشيد':'berrechid','الصويرة':'essaouira','الغرب':'el-gharb','الخميسات':'khemisset-ouelmes','الخميسات والماس':'khemisset-ouelmes','تيفلت الرماني':'tiflet-rommani','تيفلت - الرماني':'tiflet-rommani','سيدي قاسم':'sidi-kacem'}
CID_RE=re.compile(r'\(?cid:\d+\)?|\)?\d+:dic\(?',re.I)
def clean(v):return ' '.join(str(v or '').replace('\n',' ').split())
def norm_ar(s):
 x=unicodedata.normalize('NFKC',html.unescape(clean(s))).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}));x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x);x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def compact_ar(s):return norm_ar(s).replace(' ','')
def norm_latin(s):
 x=unicodedata.normalize('NFKD',str(s or ''));x=''.join(c for c in x if not unicodedata.combining(c)).casefold();return ' '.join(re.sub(r'[^a-z0-9]+',' ',x).split())
def logical_word(v):return unicodedata.normalize('NFKC',clean(v))[::-1]
def arabic_word(v):return bool(re.search(r'[\u0600-\u06FF]',unicodedata.normalize('NFKC',str(v or ''))))
def card_rows(seats):
 if seats<=3:return [(0.575,0.680,seats)]
 if seats==4:return [(0.455,0.605,2),(0.675,0.825,2)]
 if seats==5:return [(0.455,0.605,3),(0.675,0.825,2)]
 return [(0.455,0.605,3),(0.675,0.825,3)]
def cluster_lines(words):
 groups=[]
 for w in sorted(words,key=lambda z:(float(z['top']),-float(z['x0']))):
  target=None
  for g in groups:
   if abs(g['top']-float(w['top']))<=3.0:target=g;break
  if target is None:target={'top':float(w['top']),'words':[]};groups.append(target)
  target['words'].append(w)
 return sorted(groups,key=lambda g:g['top'])
def resolve_line(raw_words,pypdf_lines):
 ordered=sorted(raw_words,key=lambda z:-float(z['x0']));raw=[str(w['text']) for w in ordered];logical=[logical_word(x) for x in raw];had_cid=any(CID_RE.search(x) for x in raw)
 anchors=[norm_ar(x) for x,r in zip(logical,raw) if not CID_RE.search(r) and len(compact_ar(x))>=2];guess=norm_ar(CID_RE.sub(' ',clean(' '.join(logical))))
 line_candidates=[]
 if anchors:
  for line in pypdf_lines:
   nl=norm_ar(line);cl=compact_ar(line)
   if 2<=len(nl.split())<=6 and all(compact_ar(a) in cl for a in anchors):line_candidates.append(nl)
  line_candidates=list(dict.fromkeys(line_candidates))
 if had_cid or len(guess.split())<2:
  if len(line_candidates)==1:return line_candidates[0],'UNIQUE_PYPDF_LINE_FROM_CARD_ANCHORS',{'raw_words':raw,'anchors':anchors,'line_candidates':line_candidates}
  return None,'CARD_NAME_UNRESOLVED',{'raw_words':raw,'anchors':anchors,'line_candidates':line_candidates,'guess':guess}
 return guess,'FIRST_ARABIC_LINE_IN_CARD',{'raw_words':raw,'anchors':anchors,'pypdf_line_match':guess in [norm_ar(x) for x in pypdf_lines]}
def main():
 cross=json.loads(CROSS.read_text(encoding='utf-8'));cov=json.loads(COV.read_text(encoding='utf-8'));aud=json.loads(AUD.read_text(encoding='utf-8'));ptr=json.loads(PTR.read_text(encoding='utf-8'));probe=json.loads((ROOT/ptr['latest_probe']).read_text(encoding='utf-8'))
 if cross.get('status')!='PASS':raise RuntimeError('Arabic bridge not PASS')
 if aud.get('counts',{}).get('mechanically_admissible_pdfs',0)<12:raise RuntimeError('PPS provenance audit must pass 12 regional PDFs')
 target={x['constituency_id'] for x in cov['missing'] if int(x['historical_seats_2016'])>=3};by_cid={r['source_2026_constituency_id']:r for r in cross['records']};patterns=defaultdict(set)
 for cid in target:
  r=by_cid[cid]
  for v in (r.get('name_ar'),r.get('name_ar_source_form'),r.get('name_ar_match_key')):
   if compact_ar(v):patterns[cid].add(compact_ar(v))
 for v,cid in TERRITORY_ALIASES.items():
  if cid in target:patterns[cid].add(compact_ar(v))
 passed={r['probe_sha256']:r for r in aud['relationships'] if r['mechanical_pass']};docs=[x for x in probe['pdf_hits'] if x['region_slug'] in CRITICAL_REGIONS and x['sha256'] in passed]
 territories=[];candidates=[];failures=[];diagnostics=[]
 for d in docs:
  path=ROOT/d['pdf']['raw_path'];reader=PdfReader(str(path));rel=passed[d['sha256']]
  with pdfplumber.open(str(path)) as pdf:
   if len(pdf.pages)!=len(reader.pages):raise RuntimeError('page-count mismatch')
   for pn,(page,pypage) in enumerate(zip(pdf.pages,reader.pages),1):
    ptext=pypage.extract_text() or '';pc=compact_ar(ptext);plines=[clean(x) for x in ptext.splitlines() if clean(x)];possible=[]
    for cid in sorted(target):
     rr=by_cid[cid]
     if norm_latin(rr.get('historical_region'))!=REGION_MATCH[d['region_slug']]:continue
     matched=[p for p in patterns[cid] if p and p in pc]
     if matched:possible.append((cid,max(matched,key=len)))
    if len(possible)!=1:
     diagnostics.append({'region':d['region_slug'],'page':pn,'territory_candidates':[x[0] for x in possible],'status':'SKIP_TERRITORY_NOT_UNIQUE'});continue
    cid,matched=possible[0];rr=by_cid[cid];seats=int(rr['historical_seats_2016']);words=page.extract_words(use_text_flow=False,keep_blank_chars=False,x_tolerance=1,y_tolerance=1,extra_attrs=['size']) or [];w=float(page.width);h=float(page.height);left=.065*w;right=.935*w;span=right-left;names=[];cards=[];errors=[]
    for row_no,(y0f,y1f,ncols) in enumerate(card_rows(seats)):
     y0=y0f*h;y1=y1f*h
     for bi in reversed(range(ncols)):
      x0=left+span*(bi/ncols);x1=left+span*((bi+1)/ncols);cell=[x for x in words if arabic_word(x['text']) and y0<=float(x['top'])<=y1 and x0<=(float(x['x0'])+float(x['x1']))/2<=x1];groups=cluster_lines(cell);first=groups[0] if groups else None
      if first:name,method,detail=resolve_line(first['words'],plines)
      else:name,method,detail=None,'EMPTY_CARD',{'raw_words':[]}
      card={'row':row_no,'bin_from_left':bi,'y_range':[round(y0f,3),round(y1f,3)],'first_line_top':round(first['top'],2) if first else None,'method':method,'detail':detail,'candidate_name_ar':name};cards.append(card)
      if name:names.append(name)
      else:errors.append(f'UNRESOLVED_CARD_r{row_no}_b{bi}')
    if len(names)!=seats:errors.append(f'CANDIDATE_COUNT_{len(names)}_NE_SEATS_{seats}')
    if len({compact_ar(x) for x in names})!=len(names):errors.append('DUPLICATE_CANDIDATE_IDENTITY')
    diag={'region':d['region_slug'],'page':pn,'constituency_id':cid,'historical_constituency':rr['historical_constituency'],'seats':seats,'matched_territory_pattern':matched,'card_layout':card_rows(seats),'cards':cards,'errors':errors};diagnostics.append(diag)
    if errors:failures.append(diag);continue
    excerpt={'page':pn,'territory_pattern':matched,'candidate_cards':cards};territories.append({'year':2016,'party':'PPS','constituency_id':cid,'historical_id_constituency':rr['historical_id_constituency'],'historical_constituency':rr['historical_constituency'],'historical_region':rr['historical_region'],'seats':seats,'candidate_count':seats,'FORMAL_ENDORSEMENT':True,'source_class':'T1_OFFICIAL_PARTY','pdf_sha256':d['sha256'],'parent_page_url':rel['page_url'],'parent_page_timestamps':rel['page_timestamps'],'evidence_excerpt':excerpt})
    for display,name in enumerate(names,1):candidates.append({'year':2016,'party':'PPS','constituency_id':cid,'historical_id_constituency':rr['historical_id_constituency'],'historical_constituency':rr['historical_constituency'],'candidate_name_ar':name,'candidate_name_ar_normalized':norm_ar(name),'candidate_rank':None,'CANDIDATE_REGISTERED_RANK':None,'rank_evidence_status':'MISSING_NOT_INFERRED_FROM_POSTER_LAYOUT','FORMAL_ENDORSEMENT':True,'party_fact_status':'PARTY_ANNOUNCED','poster_display_order_only':display,'evidence':{'publication_time':rel['page_timestamps'][0] if rel['page_timestamps'] else None,'retrieval_time':aud['created_at'],'source_class':'T1_OFFICIAL_PARTY','content_sha256':d['sha256'],'parent_page_url':rel['page_url'],'page':pn,'archived_excerpt':excerpt}})
 by=defaultdict(list)
 for c in candidates:by[c['constituency_id']].append(c)
 identity=sum(len({x['candidate_name_ar_normalized'] for x in xs})>=3 for xs in by.values());status='PASS_TARGET_COVERAGE' if identity>=13 else 'PARTIAL_VALID';payload={'schema_version':'3.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':status,'target_missing_ge3_districts':sorted(target),'territory_rows':territories,'candidate_rows':candidates,'failures':failures,'page_diagnostics':diagnostics,'counts':{'target_missing_ge3':len(target),'territories_recovered':len(territories),'candidate_rows':len(candidates),'recovered_districts_with_at_least_three_verified_candidate_identities':identity,'needed_from_pps_to_close_2016_identity_gate':13,'pps_closure_threshold_reached':identity>=13},'invariants':{'candidate_card_rule':'FIRST_ARABIC_LINE_IN_EACH_CALIBRATED_CARD','candidate_rank_inferred_from_layout':False,'failed_pages_promoted':False,'source_only_T1_pre_cutoff':True,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'parsed_missing_slates.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':status,'counts':payload['counts'],'territories':[x['historical_constituency'] for x in territories],'failure_count':len(failures),'failure_sample':[{'constituency':x.get('historical_constituency'),'region':x.get('region'),'page':x.get('page'),'errors':x.get('errors')} for x in failures[:12]]},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
