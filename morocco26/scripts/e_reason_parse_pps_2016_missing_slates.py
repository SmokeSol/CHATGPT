#!/usr/bin/env python3
"""Parse all mechanically admissible PPS 2016 regional candidate posters.

All 12 regional PDFs are first-party T1 documents linked to official PPS pages
published before the 7 October poll. Each poster page represents one local
constituency. Candidate identity is the first Arabic line in each calibrated
candidate card; biography/occupation text below is excluded. A page is promoted
only when exactly historical seat magnitude distinct identities are recovered.
Poster position is never interpreted as legal list rank.
"""
from __future__ import annotations
import html,json,re,unicodedata
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import pdfplumber
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json';AUD=ER/'evidence/pps_2016_pdf_provenance_audit/audit.json';PTR=ER/'pps_2016_regional_pdf_probe_latest.json';OUT=ER/'evidence/pps_2016_parsed_missing_slates'
REGION_MATCH={'casablanca-settat':'casablanca settat','souss-massa':'souss massa','oriental':'oriental','beni-mellal-khenifra':'beni mellal khenifra','rabat-sale-kenitra':'rabat sale kenitra','marrakech-safi':'marrakech safi','fes-meknes':'fes meknes','tanger-tetouan-al-hoceima':'tanger tetouan al hoceima','draa-tafilalet':'draa tafilalet','guelmim-oued-noun':'guelmim oued noun','laayoune-sakia-el-hamra':'laayoune sakia el hamra','dakhla-oued-ed-dahab':'dakhla oued ed dahab'}
ALIASES={'فجيج':'figuig','فيجيج':'figuig','شتوكة ايت باها':'chtouka-ait-baha','شتوكة آيت باها':'chtouka-ait-baha','خريبكة':'khouribga','انفا':'casablanca-anfa','آنفا':'casablanca-anfa','عين السبع الحي المحمدي':'ain-sebaa-hay-mohammadi','عين السبع':'ain-sebaa-hay-mohammadi','سيدي البرنوصي':'sidi-bernoussi','مولاي رشيد':'moulay-rachid','المحمدية':'mohammadia','برشيد':'berrechid','الصويرة':'essaouira','الغرب':'el-gharb','الخميسات':'khemisset-ouelmes','الخميسات والماس':'khemisset-ouelmes','تيفلت الرماني':'tiflet-rommani','تيفلت - الرماني':'tiflet-rommani','سيدي قاسم':'sidi-kacem','سال المدينة':'sale-medina','سلا المدينة':'sale-medina','سلا الجديدة':'sala-al-jadida','سال الجديدة':'sala-al-jadida','الرباط المحيط':'rabat-ocean','الرباط شالة':'rabat-chellah','ازيلال دمنات':'azilal-demnate','ازيالل دمنات':'azilal-demnate','بوملان':'boulemane'}
CID_RE=re.compile(r'\(?cid:\d+\)?|\)?\d+:dic\(?',re.I)
def clean(v):return ' '.join(str(v or '').replace('\n',' ').split())
def norm_ar(s):
 x=unicodedata.normalize('NFKC',html.unescape(clean(s))).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}));x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x);x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def compact(s):return norm_ar(s).replace(' ','')
def norm_latin(s):
 x=unicodedata.normalize('NFKD',str(s or ''));x=''.join(c for c in x if not unicodedata.combining(c)).casefold();return ' '.join(re.sub(r'[^a-z0-9]+',' ',x).split())
def logical(v):return unicodedata.normalize('NFKC',clean(v))[::-1]
def is_ar(v):return bool(re.search(r'[\u0600-\u06FF]',unicodedata.normalize('NFKC',str(v or ''))))
def rowspec(seats):
 if seats<=3:return [(0.575,0.680,seats)]
 if seats==4:return [(0.455,0.605,2),(0.675,0.825,2)]
 if seats==5:return [(0.455,0.605,3),(0.675,0.825,2)]
 return [(0.455,0.605,3),(0.675,0.825,3)]
def clusters(words):
 gs=[]
 for w in sorted(words,key=lambda z:(float(z['top']),-float(z['x0']))):
  g=next((x for x in gs if abs(x['top']-float(w['top']))<=3.0),None)
  if g is None:g={'top':float(w['top']),'words':[]};gs.append(g)
  g['words'].append(w)
 return sorted(gs,key=lambda x:x['top'])
def resolve_name(ws,lines):
 ordered=sorted(ws,key=lambda z:-float(z['x0']));raw=[str(w['text']) for w in ordered];logical_tokens=[logical(x) for x in raw];anchors=[norm_ar(x) for x,r in zip(logical_tokens,raw) if not CID_RE.search(r) and len(compact(x))>=2];guess=norm_ar(CID_RE.sub(' ',clean(' '.join(logical_tokens))));had_cid=any(CID_RE.search(x) for x in raw);matches=[]
 if anchors:
  for line in lines:
   nl=norm_ar(line);cl=compact(line)
   if 2<=len(nl.split())<=6 and all(compact(a) in cl for a in anchors):matches.append(nl)
  matches=list(dict.fromkeys(matches))
 if had_cid or len(guess.split())<2:
  if len(matches)==1:return matches[0],'UNIQUE_PYPDF_LINE_FROM_CARD_ANCHORS',{'raw_words':raw,'anchors':anchors,'line_candidates':matches}
  return None,'CARD_NAME_UNRESOLVED',{'raw_words':raw,'anchors':anchors,'line_candidates':matches,'guess':guess}
 return guess,'FIRST_ARABIC_LINE_IN_CARD',{'raw_words':raw,'anchors':anchors}
def main():
 cross=json.loads(CROSS.read_text(encoding='utf-8'));aud=json.loads(AUD.read_text(encoding='utf-8'));ptr=json.loads(PTR.read_text(encoding='utf-8'));probe=json.loads((ROOT/ptr['latest_probe']).read_text(encoding='utf-8'))
 if cross.get('status')!='PASS' or cross['counts']['resolved']!=92:raise RuntimeError('Arabic bridge not 92/92 PASS')
 if aud.get('counts',{}).get('mechanically_admissible_pdfs',0)<12:raise RuntimeError('PPS provenance not 12/12')
 by={r['source_2026_constituency_id']:r for r in cross['records']};patterns=defaultdict(set)
 for cid,r in by.items():
  for v in (r.get('name_ar'),r.get('name_ar_source_form'),r.get('name_ar_match_key')):
   if compact(v):patterns[cid].add(compact(v))
 for v,cid in ALIASES.items():
  if cid in by:patterns[cid].add(compact(v))
 passed={r['probe_sha256']:r for r in aud['relationships'] if r['mechanical_pass']};docs=[x for x in probe['pdf_hits'] if x['sha256'] in passed];territories=[];candidates=[];failures=[];diag=[];seen=set()
 for d in docs:
  rel=passed[d['sha256']];reader=PdfReader(str(ROOT/d['pdf']['raw_path']))
  with pdfplumber.open(str(ROOT/d['pdf']['raw_path'])) as pdf:
   for pn,(page,pypage) in enumerate(zip(pdf.pages,reader.pages),1):
    ptext=pypage.extract_text() or '';pc=compact(ptext);lines=[clean(x) for x in ptext.splitlines() if clean(x)];possible=[]
    for cid,r in by.items():
     if norm_latin(r.get('historical_region'))!=REGION_MATCH.get(d['region_slug']):continue
     m=[p for p in patterns[cid] if p and p in pc]
     if m:possible.append((cid,max(m,key=len)))
    if len(possible)!=1:diag.append({'region':d['region_slug'],'page':pn,'territory_candidates':[x[0] for x in possible],'status':'SKIP_TERRITORY_NOT_UNIQUE'});continue
    cid,matched=possible[0];r=by[cid];seats=int(r['historical_seats_2016']);words=page.extract_words(use_text_flow=False,keep_blank_chars=False,x_tolerance=1,y_tolerance=1,extra_attrs=['size']) or [];w=float(page.width);h=float(page.height);left=.065*w;right=.935*w;span=right-left;names=[];cards=[];errors=[]
    for rowno,(y0f,y1f,ncols) in enumerate(rowspec(seats)):
     for bi in reversed(range(ncols)):
      x0=left+span*bi/ncols;x1=left+span*(bi+1)/ncols;cell=[x for x in words if is_ar(x['text']) and y0f*h<=float(x['top'])<=y1f*h and x0<=(float(x['x0'])+float(x['x1']))/2<=x1];gs=clusters(cell);first=gs[0] if gs else None;name,method,detail=resolve_name(first['words'],lines) if first else (None,'EMPTY_CARD',{'raw_words':[]});cards.append({'row':rowno,'bin_from_left':bi,'first_line_top':round(first['top'],2) if first else None,'method':method,'detail':detail,'candidate_name_ar':name})
      if name:names.append(name)
      else:errors.append(f'UNRESOLVED_CARD_r{rowno}_b{bi}')
    if len(names)!=seats:errors.append(f'CANDIDATE_COUNT_{len(names)}_NE_SEATS_{seats}')
    if len({compact(x) for x in names})!=len(names):errors.append('DUPLICATE_CANDIDATE_IDENTITY')
    drow={'region':d['region_slug'],'page':pn,'constituency_id':cid,'historical_constituency':r['historical_constituency'],'seats':seats,'cards':cards,'errors':errors};diag.append(drow)
    if errors:failures.append(drow);continue
    if cid in seen:failures.append({**drow,'errors':['DUPLICATE_TERRITORY_PAGE']});continue
    seen.add(cid);excerpt={'page':pn,'territory_pattern':matched,'candidate_cards':cards};territories.append({'year':2016,'party':'PPS','constituency_id':cid,'historical_id_constituency':r['historical_id_constituency'],'historical_constituency':r['historical_constituency'],'historical_region':r['historical_region'],'seats':seats,'candidate_count':seats,'FORMAL_ENDORSEMENT':True,'source_class':'T1_OFFICIAL_PARTY','pdf_sha256':d['sha256'],'parent_page_url':rel['page_url'],'parent_page_timestamps':rel['page_timestamps'],'evidence_excerpt':excerpt})
    for n,name in enumerate(names,1):candidates.append({'year':2016,'party':'PPS','constituency_id':cid,'historical_id_constituency':r['historical_id_constituency'],'historical_constituency':r['historical_constituency'],'candidate_name_ar':name,'candidate_name_ar_normalized':norm_ar(name),'candidate_rank':None,'CANDIDATE_REGISTERED_RANK':None,'rank_evidence_status':'MISSING_NOT_INFERRED_FROM_POSTER_LAYOUT','FORMAL_ENDORSEMENT':True,'party_fact_status':'PARTY_ANNOUNCED','poster_display_order_only':n,'evidence':{'publication_time':rel['page_timestamps'][0] if rel['page_timestamps'] else None,'retrieval_time':aud['created_at'],'source_class':'T1_OFFICIAL_PARTY','content_sha256':d['sha256'],'parent_page_url':rel['page_url'],'page':pn,'archived_excerpt':excerpt}})
 bt=defaultdict(list)
 for c in candidates:bt[c['constituency_id']].append(c)
 ident=sum(len({x['candidate_name_ar_normalized'] for x in xs})>=3 for xs in bt.values());enr=len(bt);payload={'schema_version':'4.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'PASS_2016_COLLECTION_GATE' if ident>=70 and enr>=50 else 'PARTIAL_VALID','territory_rows':territories,'candidate_rows':candidates,'failures':failures,'page_diagnostics':diag,'counts':{'regional_pdfs_used':len(docs),'territories_recovered':len(territories),'candidate_rows':len(candidates),'districts_with_at_least_three_verified_candidate_identities':ident,'districts_with_formal_endorsement_enrichment':enr,'required_identity_districts':70,'required_enriched_districts':50,'identity_gate_pass':ident>=70,'enriched_gate_pass':enr>=50,'data_sufficiency_gate_pass':ident>=70 and enr>=50},'invariants':{'candidate_card_rule':'FIRST_ARABIC_LINE_IN_EACH_CALIBRATED_CARD','candidate_rank_inferred_from_layout':False,'failed_pages_promoted':False,'source_only_T1_pre_cutoff':True,'outcomes_unsealed':False,'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'parsed_missing_slates.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':payload['status'],'counts':payload['counts'],'failure_count':len(failures),'unresolved_territory_pages':sum(x.get('status')=='SKIP_TERRITORY_NOT_UNIQUE' for x in diag)},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
