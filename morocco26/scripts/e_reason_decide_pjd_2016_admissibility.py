#!/usr/bin/env python3
"""Issue an explicit, fail-closed admissibility decision for migrated PJD PDFs.

No new source class is introduced. The documents retain T1_OFFICIAL_PARTY
rank. Their *transport* is a current migrated static mirror whose pre-cutoff
existence/content identity is established by the conditions pre-registered in
e_reason_source_registry_v1.json and mechanically verified by the provenance
audit. This decision authorizes party-announced/party-endorsed candidate facts
only; it does not assert T0 legal registration.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
REG=ER/'e_reason_source_registry_v1.json'
POL=ER/'e_reason_source_policy_v1.json'
AUDIT=ER/'evidence/pjd_2016_provenance_audit/audit.json'
OUT=ER/'evidence/pjd_2016_admissibility'


def main():
    reg=json.loads(REG.read_text(encoding='utf-8'))
    pol=json.loads(POL.read_text(encoding='utf-8'))
    audit=json.loads(AUDIT.read_text(encoding='utf-8'))
    entry=next((x for x in reg.get('entries',[]) if x.get('domain')=='pjd.ma'),None)
    if not entry: raise RuntimeError('pjd.ma not registered')
    if entry.get('source_class')!='T1_OFFICIAL_PARTY': raise RuntimeError('pjd.ma class drift')
    if entry.get('qualification_status')!='QUALIFIED_BEFORE_EXTRACTION': raise RuntimeError('pjd.ma not qualified before extraction')
    if 'T1_OFFICIAL_PARTY' not in pol.get('allowed_source_classes',[]): raise RuntimeError('T1 not allowed by frozen policy')
    mirror_rule='Current migrated static files are accepted only as archival mirrors of a pre-cutoff first-party attachment when the historical article, attachment filename and document content jointly establish provenance.'
    if mirror_rule not in entry.get('restrictions',[]): raise RuntimeError('pre-extraction migrated-mirror condition missing')
    if audit.get('documents_audited')!=3 or not audit.get('all_mechanical_checks_pass'): raise RuntimeError('provenance audit not 3/3 PASS')

    decisions=[]
    for r in audit['rows']:
        criteria={
            'official_domain_prequalified_T1_before_extraction':True,
            'historical_article_publication_pre_cutoff':r.get('publication_pre_cutoff') is True,
            'current_official_article_links_expected_attachment_basename':r.get('expected_attachment_linked') is True,
            'pdf_internal_creation_pre_cutoff':r.get('pdf_creation_pre_cutoff_if_present') is True,
            'document_explicitly_describes_upcoming_7_october_poll':r.get('pre_election_phrase_hits',{}).get('اقتراع يوم 7 أكتوبر') is True,
            'document_is_candidate_slate':bool(r.get('pre_election_phrase_hits',{}).get('لائحة المرشحين') or r.get('pre_election_phrase_hits',{}).get('لائحة باقي المرشحين')),
            'document_is_party_secretariat_material':r.get('pre_election_phrase_hits',{}).get('الأمانة العامة') is True,
            'no_target_election_outcome_terms_detected':not any(r.get('post_election_outcome_term_hits',{}).values()),
            'mechanical_provenance_audit_pass':r.get('mechanical_provenance_checks_pass') is True,
        }
        passed=all(criteria.values())
        decisions.append({
            'article_id':r['article_id'],
            'source_class':'T1_OFFICIAL_PARTY',
            'transport':'MIGRATED_STATIC_ARCHIVAL_MIRROR',
            'official_article_url':r['official_article_url'],
            'article_publication_dates':r['html_detected_publication_dates'],
            'attachment_basename':r['expected_attachment'],
            'mirror_url':r['mirror_url'],
            'pdf_sha256':r['pdf_sha256'],
            'pdf_creation_date':r['pdf_creation_date_parsed_utc_assumption'],
            'criteria':criteria,
            'decision':'ADMISSIBLE_FOR_PRE_CUTOFF_T1_PARTY_FACTS' if passed else 'REJECT',
            'authorized_fact_scope':['PARTY_ANNOUNCED_CANDIDATE_IDENTITY','CANDIDATE_REGISTERED_RANK_AS_PARTY_SLATE_RANK','FORMAL_ENDORSEMENT'],
            'explicitly_not_authorized':['T0_LEGAL_REGISTRATION','TARGET_ELECTION_OUTCOME','WINNER_LOSER_STATUS','POST_ELECTION_ANALYSIS'],
        })
    accepted=[x for x in decisions if x['decision'].startswith('ADMISSIBLE')]
    payload={
        'schema_version':'1.0',
        'decision_id':'M26-E-REASON-PJD-2016-MIGRATED-STATIC-ADMISSIBILITY-V1',
        'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'frozen_source_policy':str(POL.relative_to(ROOT)),
        'pre_extraction_source_registry':str(REG.relative_to(ROOT)),
        'provenance_audit':str(AUDIT.relative_to(ROOT)),
        'source_class_preserved':'T1_OFFICIAL_PARTY',
        'new_source_class_added':False,
        'accepted_document_count':len(accepted),
        'rejected_document_count':len(decisions)-len(accepted),
        'status':'PASS' if len(accepted)==3 else 'FAIL_CLOSED',
        'decisions':decisions,
        'invariants':{
            'legal_registration_inferred':False,
            'outcomes_unsealed':False,
            'predictive_judgments_generated':False,
            'forecast_delta_generated':False,
            'F1_created':False,
        },
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'decision.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':payload['status'],'accepted_document_count':len(accepted),'decisions':[{'article_id':x['article_id'],'decision':x['decision']} for x in decisions]},ensure_ascii=False,indent=2))
    if payload['status']!='PASS': raise SystemExit(2)

if __name__=='__main__': main()
