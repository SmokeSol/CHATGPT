#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_2002 = ROOT / 'data' / 'goal100' / 'historical' / '2002' / 'historical_native_map_pre_election.json'
OUT = ROOT / 'data' / 'goal100' / 'historical' / '2007'
ACCESS_DATE = '2026-08-19'
ELECTION_DATE = '2007-09-07'

SOURCES = {
    'LM_MAP_20020921': {'source_class': 'T2_MAP_CONTEMPORARY','url': 'https://lematin.ma/journal/2002/Fiches-techniques-des-circonscriptions-electorales/20927/amp','publication_date': '2002-09-21','archive_date': None,'fact': 'Complete 91-constituency 2002 pre-election technical map with magnitudes.'},
    'ALM_PROPOSAL_20070206': {'source_class': 'T2_CONTEMPORARY','url': 'https://aujourdhui.ma/?p=60488','publication_date': '2007-02-06','archive_date': None,'fact': 'Interior Ministry February proposal table gives old/new names and magnitudes for Casablanca, Rabat, Marrakech, Fes, Meknes and Tanger-Tetouan changes.'},
    'ALM_GOV_20070222': {'source_class': 'T2_CONTEMPORARY','url': 'https://aujourdhui.ma/societe/elections-lexecutif-accelere-la-cadence-47631','publication_date': '2007-02-22','archive_date': None,'fact': 'Government-stage decree project modifies 2002 map and states no change from the 3 February version; principal changes named.'},
    'LM_GOV_20070222': {'source_class': 'T2_MAP_REPORTING_GOVERNMENT','url': 'https://lematin.ma/journal/2006/Conseil-de-gouvernement_Les-candidatures-devront-etre-deposees--du-17-au-24-aoA-t/3112.html','publication_date': '2007-02-22','archive_date': None,'fact': 'Government spokesman: project completes/modifies 7 Aug 2002 district decree; 295 local seats remain unchanged.'},
    'ALM_ADOPTION_20070326': {'source_class': 'T2_CONTEMPORARY','url': 'https://aujourdhui.ma/politique/elections-2007-le-decoupage-adopte-94553','publication_date': '2007-03-26','archive_date': None,'fact': 'Council of Ministers of 23 March approved election-related decree projects including electoral delimitation.'},
    'LM_GLOBAL_20070824': {'source_class': 'T2_MAP_CONTEMPORARY','url': 'https://lematin.ma/journal/2006/Demarrage-de-la-campagne-electorale-deux-semaines-pour-convaincre_30-sieges-sont-reserves-aux-listes-nationales-des-femmes/74118.html','publication_date': '2007-08-24','archive_date': None,'fact': 'Pre-election campaign opening: 95 local constituencies, 295 local seats, 30-seat women national list, proportional largest remainder and 6% threshold.'},
    'ASSAHRAA_MAP_20070829': {'source_class': 'T2_MAP_CONTEMPORARY','url': 'https://assahraa.ma/journal/2007/46530','publication_date': '2007-08-29','archive_date': None,'fact': 'MAP campaign series explicitly covering 95 districts; directly states final names/magnitudes for Rabat, Marrakech, Boujdour, Fes, Taroudant, Sale, Skhirate-Temara and Khemisset districts.'},
    'ASSAHRAA_MAP_20070901': {'source_class': 'T2_MAP_CONTEMPORARY','url': 'https://assahraa.ma/journal/2007/46728','publication_date': '2007-09-01','archive_date': None,'fact': 'MAP campaign series gives all 11 Greater Casablanca districts and all 31 magnitudes; also Rhamna/Sraghna-Zemrane and Sefrou.'},
    'LM_MAP_20070902': {'source_class': 'T2_MAP_CONTEMPORARY','url': 'https://lematin.ma/journal/2007/Legislatives-a-travers-les-regions_15-listes-locales-a-Laayoune-et-23-a-Meknes-Tafilelt/76043.html','publication_date': '2007-09-02','archive_date': None,'fact': 'MAP/Interior pre-election list distribution over 95 districts; directly confirms Laayoune 3 seats and many final district names including Ismailia Karouan.'},
    'ASSAHRAA_ADMIN_20070904': {'source_class': 'T2_CONTEMPORARY','url': 'https://assahraa.ma/journal/2007/46818','publication_date': '2007-09-04','archive_date': None,'fact': "Pre-election contemporary source confirms M'Diq-Fnideq prefecture existed before polling day; it does not itself state the parliamentary magnitude."},
}

def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace('’', "'").replace('–', '-').replace('—', '-')
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()

def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')

def load_2002_rows():
    rows = json.loads(SRC_2002.read_text(encoding='utf-8'))['rows']
    if len(rows) != 91: raise SystemExit(f'BASE_2002_COUNT_FAIL:{len(rows)}')
    if sum(int(r['magnitude']) for r in rows) != 295: raise SystemExit('BASE_2002_SEAT_SUM_FAIL')
    return rows

def carried(r):
    return {'native_id': None,'constituency': r['constituency'],'prefprov': r.get('prefprov'),'magnitude': int(r['magnitude']),'status': 'AMBIGUOUS','evidence_mode': 'LEGAL_CARRY_FORWARD_FROM_2002','source_ids': ['LM_MAP_20020921','ALM_GOV_20070222','LM_GOV_20070222','ALM_ADOPTION_20070326','LM_GLOBAL_20070824'],'provenance': '2002 verified native row carried into 2007 because the 2007 legal process explicitly modifies/completes the 2002 decree; sources call the listed urban changes the principal changes, not an exhaustive no-change certificate for every other row.','ambiguities': ['No row-specific final pre-election 2007 magnitude citation attached; carry-forward remains explicit uncertainty, never false/zero.'],'inherited_2002_native_id': r.get('native_id')}

def replacement(name, magnitude, prefprov, status, mode, source_ids, note, old_ids=None):
    return {'native_id': None,'constituency': name,'prefprov': prefprov,'magnitude': int(magnitude),'status': status,'evidence_mode': mode,'source_ids': source_ids,'provenance': note,'ambiguities': [] if status == 'VERIFIED' else [note],'inherited_2002_native_id': old_ids}

def build():
    base = load_2002_rows(); by_norm = {norm(r['constituency']): r for r in base}
    if len(by_norm) != 91: raise SystemExit('BASE_2002_DUPLICATE_NORMALIZED_NAMES')
    remove_names = {'Rabat-Almohit','Rabat-Chellah','Casablanca-Anfa','Al Fida-Derb Sultan','Aïn Sebaâ-Hay Mohammadi','Aïn Chock-Hay Hassani','Sidi Bernoussi-Zénata',"Ben M'sick-Médiouna",'Moulay Rachid-Sidi Othmane','Mohammadia','Marrakech-Ménara','Marrakech-Médina','Sidi Youssef Ben Ali','Fès-El-Jadid-Dar Dbibagh','Fès-Médina','Zouagha-Moulay Yacoub','Meknès-El Menzeh','Al-Ismaïlia','Al Fahss-Bni Makada','Chefchaouen','Tétouan','Taroudannt','Taroudannt Achamalia'}
    remove_norm = {norm(x) for x in remove_names}; missing_remove = sorted(remove_norm - set(by_norm))
    if missing_remove: raise SystemExit('EXPECTED_2002_ROWS_NOT_FOUND:' + '|'.join(missing_remove))
    rows = [carried(r) for r in base if norm(r['constituency']) not in remove_norm]
    old = lambda *names: [by_norm[norm(n)]['native_id'] for n in names]
    rows += [replacement('Rabat-Océan',4,'Rabat','VERIFIED','DIRECT_PRE_ELECTION_FINAL',['ASSAHRAA_MAP_20070829'],'MAP source of 29 Aug directly states Rabat-Ocean has four seats.',old('Rabat-Almohit')),replacement('Rabat-Chellah',3,'Rabat','VERIFIED','DIRECT_PRE_ELECTION_FINAL',['ASSAHRAA_MAP_20070829'],'MAP source of 29 Aug directly states Rabat-Chellah has three seats.',old('Rabat-Chellah'))]
    casa=[('Casablanca-Anfa',4,'Casablanca-Anfa'),('Al Fida-Mers Sultan',3,'Al Fida-Mers Sultan'),('Aïn Sebaâ-Hay Mohammadi',3,'Aïn Sebaâ-Hay Mohammadi'),('Hay Hassani',3,'Hay Hassani'),('Sidi Bernoussi',3,'Sidi Bernoussi'),('Moulay Rachid',3,'Moulay Rachid'),('Nouaceur',3,'Nouaceur'),('Mohammedia',3,'Mohammedia'),('Aïn Chock',2,'Aïn Chock'),("Ben M'sick",2,"Ben M'sick"),('Médiouna',2,'Médiouna')]
    casa_old=old('Casablanca-Anfa','Al Fida-Derb Sultan','Aïn Sebaâ-Hay Mohammadi','Aïn Chock-Hay Hassani','Sidi Bernoussi-Zénata',"Ben M'sick-Médiouna",'Moulay Rachid-Sidi Othmane','Mohammadia')
    for name,mag,pref in casa: rows.append(replacement(name,mag,pref,'VERIFIED','DIRECT_PRE_ELECTION_FINAL',['ASSAHRAA_MAP_20070901'],'MAP source of 1 Sep directly lists all 11 Greater Casablanca constituencies and their magnitudes.',casa_old))
    marr_old=old('Marrakech-Ménara','Marrakech-Médina','Sidi Youssef Ben Ali')
    for name in ['Marrakech ville-Sidi Youssef Ben Ali','Guéliz-Ennakhil','Ménara']: rows.append(replacement(name,3,'Marrakech','VERIFIED','DIRECT_PRE_ELECTION_FINAL',['ASSAHRAA_MAP_20070829'],'MAP source of 29 Aug directly states the three Marrakech districts each elect three members.',marr_old))
    fes_old=old('Fès-El-Jadid-Dar Dbibagh','Fès-Médina','Zouagha-Moulay Yacoub')
    rows += [replacement('Fès-Nord',4,'Fès','VERIFIED','DIRECT_PRE_ELECTION_FINAL',['ASSAHRAA_MAP_20070829'],'MAP source of 29 Aug directly states Fes-Nord has four seats.',fes_old),replacement('Fès-Sud',4,'Fès','VERIFIED','DIRECT_PRE_ELECTION_FINAL',['ASSAHRAA_MAP_20070829'],'MAP source of 29 Aug directly states Fes-Sud has four seats.',fes_old),replacement('Moulay Yacoub',2,'Moulay Yacoub','AMBIGUOUS','PROPOSAL_PLUS_GOVERNMENT_ADOPTION',['ALM_PROPOSAL_20070206','ALM_GOV_20070222','LM_GOV_20070222','ALM_ADOPTION_20070326'],'February pre-election table gives Moulay Yacoub two seats and government-stage project says no change from that version; no direct late-campaign row citation recovered.',fes_old)]
    mek_old=old('Meknès-El Menzeh','Al-Ismaïlia')
    rows += [replacement('Hamria-Ahouaz Meknès-Zerhoune',3,'Meknès','AMBIGUOUS','PROPOSAL_PLUS_GOVERNMENT_ADOPTION',['ALM_PROPOSAL_20070206','ALM_GOV_20070222','LM_GOV_20070222','ALM_ADOPTION_20070326'],'February table gives this new Meknes district three seats and government-stage project says no change from that version; final campaign alias not independently recovered.',mek_old),replacement('Ismaïlia-Guerrouane',3,'Meknès','AMBIGUOUS','PROPOSAL_PLUS_FINAL_EXISTENCE',['ALM_PROPOSAL_20070206','ALM_GOV_20070222','LM_MAP_20070902'],'February table gives three seats; 2 Sep Interior/MAP distribution independently confirms final Ismailia Karouan naming, but the late article does not restate magnitude.',mek_old)]
    north_old=old('Al Fahss-Bni Makada','Chefchaouen','Tétouan')
    rows += [replacement('Tétouan',4,'Tétouan','AMBIGUOUS','PROPOSAL_PLUS_GOVERNMENT_ADOPTION',['ALM_PROPOSAL_20070206','ALM_GOV_20070222','LM_GOV_20070222','ALM_ADOPTION_20070326'],'February table changes Tetouan from five to four seats; government-stage project says no change from that version.',north_old),replacement('Fahs-Anjra',2,'Fahs-Anjra','AMBIGUOUS','PROPOSAL_PLUS_GOVERNMENT_ADOPTION',['ALM_PROPOSAL_20070206','ALM_GOV_20070222','LM_GOV_20070222','ALM_ADOPTION_20070326'],'February table creates/renames Fahs-Anjra at two seats; government-stage project says no change from that version.',north_old),replacement('Chefchaouen',4,'Chefchaouen','AMBIGUOUS','PROPOSAL_PLUS_FINAL_EXISTENCE',['ALM_PROPOSAL_20070206','ALM_GOV_20070222','LM_MAP_20070902'],'February table changes Chefchaouen from five to four seats; 2 Sep Interior/MAP list distribution confirms final constituency existence but not magnitude.',north_old),replacement("M'Diq-Fnideq",2,"M'Diq-Fnideq",'AMBIGUOUS','AMBIGUOUS_LEGAL_DERIVATION',['ALM_PROPOSAL_20070206','ALM_GOV_20070222','LM_GOV_20070222','ALM_ADOPTION_20070326','LM_GLOBAL_20070824','ASSAHRAA_ADMIN_20070904'],"M'Diq-Fnideq prefecture is independently documented pre-election. Two-seat magnitude is the residual required by the documented North reconfiguration while preserving the unchanged 295-seat national total and the legal minimum of two seats; no direct pre-election row-level magnitude citation was recovered.",north_old)]
    tar_old=old('Taroudannt','Taroudannt Achamalia')
    rows += [replacement('Taroudant-Nord',3,'Taroudant','VERIFIED','DIRECT_PRE_ELECTION_FINAL',['ASSAHRAA_MAP_20070829'],'MAP source of 29 Aug directly states Taroudant northern district has three seats.',tar_old),replacement('Taroudant-Sud',4,'Taroudant','VERIFIED','DIRECT_PRE_ELECTION_FINAL',['ASSAHRAA_MAP_20070829'],'MAP source of 29 Aug directly states Taroudant southern district has four seats.',tar_old)]
    direct_upgrades={norm('Salé-Médina'):('ASSAHRAA_MAP_20070829','MAP 29 Aug directly states Sale-Medina has four seats.'),norm('Salé-El Jadida'):('ASSAHRAA_MAP_20070829','MAP 29 Aug directly states Sale-El Jadida has three seats.'),norm('Skhirate-Témara'):('ASSAHRAA_MAP_20070829','MAP 29 Aug directly states Skhirate-Temara has three seats.'),norm('Khémisset-Oulmès'):('ASSAHRAA_MAP_20070829','MAP 29 Aug directly states Khemisset-Oulmes has three seats.'),norm('Tiflet-Rommani'):('ASSAHRAA_MAP_20070829','MAP 29 Aug directly states Tiflet-Rommani has three seats.'),norm('Boujdour'):('ASSAHRAA_MAP_20070829','MAP 29 Aug directly states Boujdour has two seats.'),norm('Rhamna'):('ASSAHRAA_MAP_20070901','MAP 1 Sep directly states Rhamna has three seats.'),norm('Sraghna-Zemrane'):('ASSAHRAA_MAP_20070901','MAP 1 Sep directly states Sraghna-Zemrane has four seats.'),norm('Sefrou'):('ASSAHRAA_MAP_20070901','MAP 1 Sep directly states Sefrou has three seats.'),norm('Laâyoune'):('LM_MAP_20070902','MAP/Interior 2 Sep directly states Laayoune has three seats.')}
    for r in rows:
        hit=direct_upgrades.get(norm(r['constituency']))
        if hit:
            sid,note=hit; r['status']='VERIFIED'; r['evidence_mode']='DIRECT_PRE_ELECTION_FINAL'; r['source_ids']=[sid]; r['provenance']=note; r['ambiguities']=[]
    rows=sorted(rows,key=lambda r:norm(r['constituency']))
    for i,r in enumerate(rows,1): r['native_id']=f'M26-2007V2-{i:03d}'; r['year']=2007
    count=len(rows); seat_sum=sum(r['magnitude'] for r in rows)
    if count!=95: raise SystemExit(f'V2_COUNT_FAIL:{count}')
    if seat_sum!=295: raise SystemExit(f'V2_SEAT_SUM_FAIL:{seat_sum}')
    if len({norm(r['constituency']) for r in rows})!=95: raise SystemExit('V2_DUPLICATE_NORMALIZED_NAMES')
    mode_counts=Counter(r['evidence_mode'] for r in rows); status_counts=Counter(r['status'] for r in rows); direct_seats=sum(r['magnitude'] for r in rows if r['evidence_mode']=='DIRECT_PRE_ELECTION_FINAL')
    dump(OUT/'historical_native_map_pre_election_v2.json',{'schema_version':'2.0','year':2007,'election_date':ELECTION_DATE,'artifact_role':'PRE_ELECTION_NATIVE_MAP_V2','construction_rule':'Derived only from the frozen 2002 pre-election map and sources published before 2007-09-07. Target-year result data are forbidden inputs.','real_constituency_count':count,'local_seat_sum':seat_sum,'rows':rows})
    missing_fields=['parties_present','head_candidates','incumbent_mp','incumbent_party','party_switch','local_elected_office','provincial_or_regional_office','party_role','former_minister_or_national_role','formal_alliance','formal_endorsement','withdrawal_or_invalidation','death_or_incapacity','documented_competitor_count']
    snapshot_rows=[]
    for r in rows:
        facts={field:{'value':None,'status':'MISSING','provenance':'NOT_RECOVERED_IN_V2_MAP_RECONSTRUCTION'} for field in missing_fields}
        snapshot_rows.append({'native_id':r['native_id'],'constituency':r['constituency'],'magnitude':r['magnitude'],'map_status':r['status'],'map_evidence_mode':r['evidence_mode'],'map_source_ids':r['source_ids'],'facts':facts})
    dump(OUT/'pre_election_snapshot_v2.json',{'schema_version':'2.0','year':2007,'cutoff_date':ELECTION_DATE,'snapshot_type':'PRE_ELECTION_ONLY','target_outcome_dependency':None,'rules':{'local_constituencies':95,'local_seats':295,'national_seats':30,'allocation':'PROPORTIONAL_LARGEST_REMAINDER','threshold_pct':6,'national_list':'30 seats reserved to national women lists','source_ids':['LM_GLOBAL_20070824']},'territories':snapshot_rows})
    inv=[]
    for sid,s in SOURCES.items(): inv.append({'source_id':sid,'url':s['url'],'publication_date':s['publication_date'],'archive_date':s['archive_date'],'access_date':ACCESS_DATE,'source_class':s['source_class'],'territory':'MULTIPLE_OR_ALL','party':None,'candidate':None,'fact':s['fact'],'status':'VERIFIED','provenance':'PRE_ELECTION_SOURCE'})
    dump(OUT/'source_inventory_snapshot_v2.json',{'schema_version':'2.0','year':2007,'sources':inv})
    ambiguities=[{'native_id':r['native_id'],'constituency':r['constituency'],'type':'MAP_EVIDENCE','status':'AMBIGUOUS','detail':a} for r in rows for a in r['ambiguities']]
    dump(OUT/'ambiguities_snapshot_v2.json',{'year':2007,'ambiguities':ambiguities})
    dump(OUT/'coverage_snapshot_v2.json',{'year':2007,'phase':'PRE_ELECTION_SNAPSHOT_V2','real_constituency_count':count,'native_map_rows':count,'native_map_coverage_pct':100.0,'local_seat_sum':seat_sum,'map_status_counts':dict(status_counts),'evidence_mode_counts':dict(mode_counts),'direct_pre_election_final_row_pct':round(100*mode_counts.get('DIRECT_PRE_ELECTION_FINAL',0)/count,2),'direct_pre_election_final_seat_pct':round(100*direct_seats/295,2),'candidate_feature_policy':'EXPLICIT_MISSING_NOT_ZERO','candidate_feature_coverage_pct':0.0,'scientific_status_before_target_open':'PARTIAL_PRE_ELECTION_SNAPSHOT','reason':'Native map is complete 95/295 from pre-election lineage, but a substantial share remains legal carry-forward/ambiguous pending independent target-open reconciliation; no same-year target was consulted.'})
    dump(OUT/'anti_leakage_certificate_v2.json',{'schema_version':'2.0','year':2007,'declaration':'TARGET_OUTCOME_NOT_USED_IN_PRE_ELECTION_SNAPSHOT','base_input':str(SRC_2002.relative_to(ROOT)),'base_input_sha256':sha256(SRC_2002),'forbidden_same_year_inputs':['data/goal100/older_history_probe/raw/parlement-elections-2007-1-0.xlsx','data/goal100/historical/2007/legislative_2007_outcome_canonical.json'],'generator':'scripts/build_2007_pre_election_snapshot_v2.py','cutoff':ELECTION_DATE,'temporal_check':'ALL_SOURCE_PUBLICATION_DATES_LT_ELECTION_DATE','unknown_discipline':'MISSING_VALUES_REMAIN_NULL_AND_NEVER_COERCED_TO_FALSE_OR_ZERO'})
    names=['historical_native_map_pre_election_v2.json','pre_election_snapshot_v2.json','source_inventory_snapshot_v2.json','ambiguities_snapshot_v2.json','coverage_snapshot_v2.json','anti_leakage_certificate_v2.json']
    dump(OUT/'snapshot_manifest_v2.json',{'schema_version':'2.0','year':2007,'phase':'PRE_ELECTION_SNAPSHOT_V2','generator':'scripts/build_2007_pre_election_snapshot_v2.py','generated_at':ACCESS_DATE,'files':[{'path':str((OUT/n).relative_to(ROOT)),'sha256':sha256(OUT/n)} for n in names]})
    names.append('snapshot_manifest_v2.json'); dump(OUT/'snapshot_hashes_sha256_v2.json',{'year':2007,'files':{n:sha256(OUT/n) for n in names}})
    print(json.dumps({'status':'SNAPSHOT_V2_BUILT','rows':count,'seats':seat_sum,'status_counts':dict(status_counts),'mode_counts':dict(mode_counts)},sort_keys=True))

if __name__=='__main__': build()
