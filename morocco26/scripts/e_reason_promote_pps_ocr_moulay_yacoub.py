#!/usr/bin/env python3
"""Promote only the fail-closed Moulay-Yacoub PPS OCR page into 2016 evidence.

The underlying PPS PDF is already mechanically admissible T1 evidence. OCR was
used only because the PDF font map destroyed the constituency header text. This
promotion requires: exact Moulay-Yacoub header tokens with >=85 confidence,
explicit 7-Oct-2016 legislative context, exactly two high-confidence candidate
name groups in the calibrated name band, and TAFRA-2016 seat magnitude == 2.
No list rank is inferred. No other OCR page is promoted.
"""
from __future__ import annotations
import json,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
OCR=ER/'evidence/pps_2016_final_two_page_ocr/diagnostic.json'
AUD=ER/'evidence/pps_2016_pdf_provenance_audit/audit.json'
CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json'
OUT=ER/'evidence/pps_2016_ocr_moulay_yacoub'
CID='moulay-yaacoub'

def norm(s):
 x=unicodedata.normalize('NFKC',str(s or '')).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}));x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x);x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def main():
 ocr=json.loads(OCR.read_text(encoding='utf-8'));aud=json.loads(AUD.read_text(encoding='utf-8'));cross=json.loads(CROSS.read_text(encoding='utf-8'))
 if ocr.get('status')!='OCR_DIAGNOSTIC_COMPLETE':raise RuntimeError('OCR diagnostic incomplete')
 if ocr.get('source_class')!='T1_OFFICIAL_PARTY':raise RuntimeError('OCR source class drift')
 pdf_sha=ocr['source_pdf_sha256'];rel=next((x for x in aud.get('relationships',[]) if x.get('probe_sha256')==pdf_sha and x.get('mechanical_pass')),None)
 if rel is None:raise RuntimeError('underlying PPS PDF is not mechanically admissible')
 territory=next((x for x in cross['records'] if x.get('source_2026_constituency_id')==CID),None)
 if territory is None:raise RuntimeError('Moulay-Yacoub missing from audited crosswalk')
 if int(territory['historical_seats_2016'])!=2:raise RuntimeError('historical seat magnitude is not 2')
 page=next((x for x in ocr['pages'] if int(x['page'])==3),None)
 if page is None:raise RuntimeError('OCR page 3 missing')
 text=norm(page['ocr_text'])
 if 'مولاي يعقوب' not in text:raise RuntimeError('exact Moulay-Yacoub OCR header missing')
 if 'الانتخابات التشريعية' not in text or 'اكتوبر2016' not in text or '07' not in text:raise RuntimeError('explicit target-election prospective context missing')
 words=page['high_conf_arabic_words']
 def exact_word(token):
  hits=[w for w in words if norm(w.get('text'))==norm(token)]
  if not hits:return None
  return max(hits,key=lambda x:float(x.get('conf',-1)))
 header_tokens=[]
 for token in ('مولاي','يعقوب'):
  hit=exact_word(token)
  if hit is None or float(hit['conf'])<85:raise RuntimeError(f'header token {token} below confidence gate')
  header_tokens.append(hit)
 # Candidate names are the only Arabic words in the narrow first-name-line band
 # (65.0%-67.5% of raster height). Occupations begin below this band.
 h=float(page['raster_height']);w=float(page['raster_width']);y0=.650*h;y1=.675*h
 band=[x for x in words if y0<=float(x['top'])<=y1 and float(x.get('conf',-1))>=85 and norm(x.get('text')) and not norm(x.get('text')).isdigit()]
 left=[];right=[]
 for x in band:
  cx=float(x['left'])+float(x['width'])/2
  (left if cx<w/2 else right).append(x)
 groups=[right,left]
 candidates=[]
 for display,grp in enumerate(groups,1):
  if len(grp)<2:raise RuntimeError(f'candidate group {display} has fewer than two high-confidence tokens')
  ordered=sorted(grp,key=lambda x:-(float(x['left'])+float(x['width'])/2))
  name=' '.join(norm(x['text']) for x in ordered if norm(x['text']))
  if len(name.split())<2:raise RuntimeError('candidate name is not multi-token')
  candidates.append({'name':name,'display_order_only':display,'tokens':[{'text':x['text'],'normalized':norm(x['text']),'conf':float(x['conf']),'left':x['left'],'top':x['top'],'width':x['width'],'height':x['height']} for x in ordered]})
 if len(candidates)!=2 or len({x['name'] for x in candidates})!=2:raise RuntimeError('candidate count/uniqueness mismatch')
 # Guard exact recovered identities expected from the page line, without any
 # fuzzy correction or semantic name completion.
 recovered={x['name'] for x in candidates}
 if recovered!={'اسامة البياز','محمد النوايتي'}:raise RuntimeError(f'unexpected OCR candidate identities: {sorted(recovered)}')
 evidence_common={'publication_time':rel['page_timestamps'][0] if rel.get('page_timestamps') else None,'retrieval_time':ocr['created_at'],'source_class':'T1_OFFICIAL_PARTY','content_sha256':pdf_sha,'parent_page_url':rel['page_url'],'pdf_page':3,'raster_sha256':page['raster_sha256'],'header_tokens':[{'text':x['text'],'normalized':norm(x['text']),'conf':float(x['conf']),'left':x['left'],'top':x['top']} for x in header_tokens],'ocr_text_excerpt':'مولاي يعقوب | الانتخابات التشريعية - 07 اكتوبر2016'}
 rows=[]
 for x in candidates:
  rows.append({'year':2016,'party':'PPS','constituency_id':CID,'historical_id_constituency':territory['historical_id_constituency'],'historical_constituency':territory['historical_constituency'],'candidate_name_ar':x['name'],'candidate_name_ar_normalized':norm(x['name']),'candidate_rank':None,'CANDIDATE_REGISTERED_RANK':None,'rank_evidence_status':'MISSING_NOT_INFERRED_FROM_POSTER_LAYOUT','FORMAL_ENDORSEMENT':True,'party_fact_status':'PARTY_ANNOUNCED','identity_verification':'TARGETED_OCR_EXACT_HEADER_PLUS_HIGH_CONFIDENCE_NAME_BAND','poster_display_order_only':x['display_order_only'],'evidence':{**evidence_common,'candidate_tokens':x['tokens']}})
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'PASS','source_artifact':str(OCR.relative_to(ROOT)),'source_pdf_sha256':pdf_sha,'territory_rows':[{'year':2016,'party':'PPS','constituency_id':CID,'historical_id_constituency':territory['historical_id_constituency'],'historical_constituency':territory['historical_constituency'],'historical_region':territory['historical_region'],'seats':2,'candidate_count':2,'FORMAL_ENDORSEMENT':True,'source_class':'T1_OFFICIAL_PARTY','identity_verification':'TARGETED_OCR_EXACT_HEADER_PLUS_HIGH_CONFIDENCE_NAME_BAND'}],'candidate_rows':rows,'counts':{'territories':1,'candidate_rows':2,'districts_with_at_least_three_candidate_capacity_when_added_to_existing_two_PJD':1},'invariants':{'ocr_page_promoted':3,'other_ocr_pages_promoted':False,'exact_header_required':True,'minimum_word_confidence':85,'candidate_count_equals_historical_seats':True,'candidate_rank_inferred':False,'person_name_fuzzy_matching':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'evidence.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':payload['status'],'territory':CID,'candidates':[x['name'] for x in candidates],'pdf_sha256':pdf_sha},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
