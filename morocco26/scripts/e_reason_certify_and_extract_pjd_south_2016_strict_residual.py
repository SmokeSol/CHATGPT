#!/usr/bin/env python3
"""Certify the PJD South/Souss/Orient 2016 mirror and extract four residuals.

This uses the *already frozen* source-registry rule permitting a current migrated
static file only when a pre-cutoff first-party article, the attachment filename,
and the document contents jointly establish provenance. The current HTML/PDF
transport itself is not treated as a historical timestamp. Candidate facts come
only from the first-party PDF content after that provenance certificate passes.

Targets are fixed from the strict gate before extraction: Tiznit, Taourirt,
Jerada and Guercif, each currently carrying exactly two strict PPS identities.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
REG=ER/'e_reason_source_registry_v1.json'
MAN=ER/'evidence/pjd_2016_documents/pjd2016_32113538749_1/run_manifest.json'
STRICT=ER/'evidence/strict_2016_integrity_gate/gate.json'
OUT=ER/'evidence/strict_2016_pjd_south_residual'
ARTICLE_ID='SOUTH_SOUSS_ORIENT'
EXPECTED_ATTACHMENT='mrshhw_jht_ljnwb_wsws_wlshrq.pdf'
EXPECTED_SHA='48878329a2849f980bf65b6b2e1ef1a68836c71aa5fb0eaee05421822a9e8143'
TARGETS={
 'tiznit':{
  'historical_constituency':'Tiznit',
  'district_token':'تيزنيت',
  'row_marker':'11سوس- ماسة تيزنيتتيزنيت2ابراهيم بوغضنعبد الجبار القسطلاني',
  'candidates':['ابراهيم بوغضن','عبد الجبار القسطلاني'],
 },
 'taourirt':{
  'historical_constituency':'Taourirt',
  'district_token':'تاوريرت',
  'row_marker':'21الشرقتاوريرتتاوريرت2احميدة المحجوبيمحمد نجمي',
  'candidates':['احميدة المحجوبي','محمد نجمي'],
 },
 'jerada':{
  'historical_constituency':'Jerada',
  'district_token':'جرادة',
  'row_marker':'22الشرقجرادة جرادة 2عبد العزيز بنعائشةمصطفى العلوي',
  'candidates':['عبد العزيز بنعائشة','مصطفى العلوي'],
 },
 'guercif':{
  'historical_constituency':'Guercif',
  'district_token':'جرسيف',
  'row_marker':'23الشرقجرسيفجرسيف2بلقاسم اليوسفيأحمد عزوزي',
  'candidates':['بلقاسم اليوسفي','أحمد عزوزي'],
 },
}
def sha256_file(path:Path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def norm_space(s):return ' '.join(str(s or '').replace('\r','').split())
def main():
 reg=json.loads(REG.read_text(encoding='utf-8'));man=json.loads(MAN.read_text(encoding='utf-8'));strict=json.loads(STRICT.read_text(encoding='utf-8'))
 if strict.get('status')!='E_REASON_2016_STRICT_INTEGRITY_PARTIAL':raise RuntimeError('strict gate is not partial; do not re-target')
 if strict.get('counts',{}).get('districts_with_at_least_three_verified_candidate_identities')!=66:raise RuntimeError('strict identity baseline drifted from fixed 66')
 residual={x['constituency_id']:x for x in strict.get('residual_below_three',[])}
 for cid in TARGETS:
  x=residual.get(cid)
  if not x or x.get('verified_distinct_candidate_identities')!=2:raise RuntimeError(f'{cid} is no longer an exact-two residual')
  if x.get('pipeline_identity_counts',{}).get('PPS_TYPO')!=2:raise RuntimeError(f'{cid} no longer has two strict PPS identities')
 pjd=next((x for x in reg.get('entries',[]) if x.get('domain')=='pjd.ma'),None)
 if not pjd or pjd.get('qualification_status')!='QUALIFIED_BEFORE_EXTRACTION' or pjd.get('source_class')!='T1_OFFICIAL_PARTY':raise RuntimeError('pjd.ma registry qualification missing')
 required_rule='Current migrated static files are accepted only as archival mirrors of a pre-cutoff first-party attachment when the historical article, attachment filename and document content jointly establish provenance.'
 if required_rule not in pjd.get('restrictions',[]):raise RuntimeError('frozen migrated-static provenance rule missing')
 art=next((x for x in man.get('articles',[]) if x.get('id')==ARTICLE_ID),None)
 doc=next((x for x in man.get('documents',[]) if x.get('article_id')==ARTICLE_ID),None)
 if not art or not doc:raise RuntimeError('south article/document manifest relation missing')
 if art.get('expected_attachment')!=EXPECTED_ATTACHMENT or doc.get('expected_attachment')!=EXPECTED_ATTACHMENT:raise RuntimeError('attachment filename mismatch')
 published=str(art.get('published_at_source') or '')
 if not published.startswith('2016-08-28'):raise RuntimeError('historical article publication timestamp drift')
 if doc.get('sha256')!=EXPECTED_SHA:raise RuntimeError('document SHA drift')
 raw=ROOT/doc['raw_path'];textp=ROOT/doc['text_path']
 if sha256_file(raw)!=EXPECTED_SHA:raise RuntimeError('frozen PDF bytes do not match manifest SHA')
 text=textp.read_text(encoding='utf-8')
 # Joint provenance: article->same filename, and document self-identifies as
 # PJD General Secretariat candidate list for the 7 October poll and target regions.
 content_checks={
  'general_secretariat':'الأمانة العامة' in text,
  'candidate_list_title':'لائحة باقي المرشحين للدوائر الانتخابية المحلية برسم اقتراع يوم 7 أكتوبر' in text,
  'south_souss_orient_scope':'الجهات الجنوبية وجهتا سوس ماسة والشرق' in text,
 }
 if not all(content_checks.values()):raise RuntimeError(f'document content provenance checks failed: {content_checks}')
 # Verify all target source rows before emitting any candidate row.
 source_rows={}
 for cid,spec in TARGETS.items():
  if spec['row_marker'] not in text:raise RuntimeError(f'exact frozen source row not found for {cid}')
  source_rows[cid]=spec['row_marker']
 certificate={
  'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'PASS',
  'source_class':'T1_OFFICIAL_PARTY','qualified_domain':'pjd.ma','registry_rule':required_rule,
  'article':{'id':ARTICLE_ID,'url':art['url'],'published_at_source':published,'expected_attachment':EXPECTED_ATTACHMENT},
  'document':{'transport':doc['transport'],'url':doc['url'],'sha256':EXPECTED_SHA,'raw_path':doc['raw_path'],'text_path':doc['text_path']},
  'joint_provenance_checks':{'precutoff_first_party_article':True,'exact_attachment_filename_relation':True,'document_hash_reverified':True,**content_checks},
  'decision':'CURRENT_MIGRATED_STATIC_MIRROR_ADMISSIBLE_UNDER_FROZEN_REGISTRY_RULE',
  'invariants':{'current_html_body_used_for_candidate_identity':False,'postcutoff_outcome_used':False,'search_snippet_used_as_evidence':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False},
 }
 candidates=[];territories=[]
 for cid,spec in TARGETS.items():
  territories.append({'year':2016,'party':'PJD','constituency_id':cid,'historical_constituency':spec['historical_constituency'],'candidate_count_promoted':len(spec['candidates']),'FORMAL_ENDORSEMENT':True,'source_class':'T1_OFFICIAL_PARTY','identity_verification':'CERTIFIED_FIRST_PARTY_PDF_EXACT_ROW','source_pdf_sha256':EXPECTED_SHA,'source_article_url':art['url'],'source_article_published_at':published,'source_row':source_rows[cid]})
  for i,name in enumerate(spec['candidates'],1):
   candidates.append({'year':2016,'party':'PJD','constituency_id':cid,'historical_constituency':spec['historical_constituency'],'candidate_name_ar':name,'candidate_name_ar_normalized':name,'candidate_rank':None,'CANDIDATE_REGISTERED_RANK':None,'rank_evidence_status':'PARTY_TABLE_POSITION_NOT_USED_AS_LEGAL_REGISTRATION','party_table_position':i,'FORMAL_ENDORSEMENT':True,'party_fact_status':'PARTY_ANNOUNCED','identity_verification':'CERTIFIED_FIRST_PARTY_PDF_EXACT_ROW','evidence':{'publication_time':published,'source_class':'T1_OFFICIAL_PARTY','content_sha256':EXPECTED_SHA,'parent_page_url':art['url'],'attachment_filename':EXPECTED_ATTACHMENT,'archived_text_path':doc['text_path'],'exact_source_row':source_rows[cid]}})
 evidence={'schema_version':'1.0','created_at':certificate['created_at'],'status':'PASS','provenance_certificate':'certificate.json','territory_rows':territories,'candidate_rows':candidates,'counts':{'territories':len(territories),'candidate_rows':len(candidates),'pre_extraction_strict_identity_pass_districts':66,'potential_post_union_identity_pass_districts':70},'invariants':{'targets_fixed_from_exact_two_residuals_before_extraction':True,'source_rows_exactly_verified':True,'candidate_rank_inferred_as_legal_registration':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'certificate.json').write_text(json.dumps(certificate,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'certificate':certificate['status'],'evidence':evidence['status'],'targets':[{'cid':x['constituency_id'],'names':[c['candidate_name_ar'] for c in candidates if c['constituency_id']==x['constituency_id']]} for x in territories]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
