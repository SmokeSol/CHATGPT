#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess,unicodedata
from difflib import SequenceMatcher
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data'/'goal100'/'historical'/'2007'; SNAP=D/'historical_native_map_pre_election_v2.json'; OUTCOME=D/'legislative_2007_outcome_canonical.json'
def norm(s):
 s=unicodedata.normalize('NFKD',str(s or '')); s=''.join(c for c in s if not unicodedata.combining(c)).lower(); s=s.replace('’',"'").replace('–','-').replace('—','-'); return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())
def dump(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def first_add(rel):
 xs=subprocess.check_output(['git','log','--diff-filter=A','--format=%H','--',rel],cwd=ROOT,text=True).strip().splitlines()
 if not xs: raise SystemExit('NO_GIT_ADD:'+rel)
 return xs[-1]
def ancestor(a,b): return subprocess.run(['git','merge-base','--is-ancestor',a,b],cwd=ROOT).returncode==0
ALIASES={
 norm('Hamria-Ahouaz Meknès-Zerhoune'):{norm('Meknès-El Menzeh'),norm('Meknes El Menzeh')},
 norm('Ismaïlia-Guerrouane'):{norm('Al-Ismaïlia'),norm('Meknès-Al Ismaïlia'),norm('Meknes Al Ismailia'),norm('Ismailia Karouan')},
 norm('Marrakech ville-Sidi Youssef Ben Ali'):{norm('Marrakech-Médina-Sidi Youssef Ben Ali'),norm('Marrakech Medina-Sidi Youssef Ben Ali')},
 norm('Rabat-Océan'):{norm('Rabat-Almohit'),norm('Rabat-El Mouhit')},
 norm('Aghriss-Tisselit'):{norm('Gheris-Tislit'),norm('Ghris Tislit')},
 norm('Karia-Rhafsai'):{norm('Karia-Ghafsai'),norm('Karia Ghafsai')},
 norm('El Rharb'):{norm('El-Gharb'),norm('El Gharb')},
 norm('Oued Zem-Abi Jaâd'):{norm('Oued-Zem - Bejaad'),norm('Oued Zem Bejaad')},
 norm('Berrchid'):{norm('Berrechid')},
 norm('Guercif'):{norm('Taza-Guercif'),norm('Taza Guercif')},
 norm('Sidi Kacem-Mechraa Belkciri-Dar Keddari'):{norm('Sidi-Kacem - Mechra-Bel-Ksiri - Dar-Gueddari'),norm('Sidi Kacem Mechra Bel Ksiri Dar Gueddari')},
 norm('Ouezzane-Had Kourt-Jorf Melha'):{norm('Ouezzane - Had-Kourt - Jorf-El-Melha'),norm('Ouezzane Had Kourt Jorf El Melha')},
 norm('Khouribga-Ouled Lbher Kbar et Sghar'):{norm('Khouribga - Oulad-Labhar - Laksar-et-Esghar'),norm('Khouribga Oulad Labhar Laksar et Esghar')},
 norm('Achamalia-Al Gharbia'):{norm('Nador-Nord-Ouest'),norm('Nador nord ouest')},
 norm('Al Janoubia-Acharquia'):{norm('Nador-Sud-Est'),norm('Nador sud est')},
 norm('Safi Chamalia'):{norm('Safi-Nord'),norm('Safi nord')},
 norm('Safi Al Janoubia'):{norm('Safi-Sud'),norm('Safi sud')},
}
for k,vs in list(ALIASES.items()):
 for v in vs: ALIASES.setdefault(v,set()).add(k)
def main():
 if not SNAP.exists() or not OUTCOME.exists(): raise SystemExit('MISSING_REQUIRED_POST_FREEZE_FILES')
 snap=json.loads(SNAP.read_text(encoding='utf-8'))['rows']; outcome=json.loads(OUTCOME.read_text(encoding='utf-8'))['local_rows']
 if len(snap)!=95 or len(outcome)!=95: raise SystemExit(f'ROW_COUNT_FAIL:{len(snap)}:{len(outcome)}')
 freeze=first_add(str(SNAP.relative_to(ROOT))); oc=first_add(str(OUTCOME.relative_to(ROOT)))
 if freeze==oc or not ancestor(freeze,oc): raise SystemExit(f'FREEZE_ORDER_FAIL:{freeze}:{oc}')
 ob={norm(r['constituency']):r for r in outcome}; unused=set(ob); matches=[]; unresolved=[]
 for s in snap:
  ns=norm(s['constituency']); match=None; typ=None
  if ns in unused: match=ob[ns]; typ='EXACT_NAME'
  else:
   hits=[x for x in ALIASES.get(ns,set()) if x in unused]
   if len(hits)==1: match=ob[hits[0]]; typ='RENAMED_EXPLICIT'
  if match is not None:
   no=norm(match['constituency']); ok=int(s['magnitude'])==int(match['magnitude']); matches.append({'snapshot_native_id':s['native_id'],'snapshot_constituency':s['constituency'],'snapshot_magnitude':s['magnitude'],'outcome_native_id':match['native_id'],'outcome_constituency':match['constituency'],'outcome_magnitude':match['magnitude'],'mapping_type':typ,'seat_match':ok,'snapshot_evidence_mode':s['evidence_mode'],'snapshot_map_status':s['status']}); unused.remove(no)
  else:
   same=[r for k,r in ob.items() if k in unused and int(r['magnitude'])==int(s['magnitude'])]; ranked=sorted([{'outcome_native_id':r['native_id'],'outcome_constituency':r['constituency'],'outcome_magnitude':r['magnitude'],'name_similarity':round(SequenceMatcher(None,ns,norm(r['constituency'])).ratio(),3)} for r in same],key=lambda x:x['name_similarity'],reverse=True)[:5]; unresolved.append({'snapshot_native_id':s['native_id'],'snapshot_constituency':s['constituency'],'snapshot_magnitude':s['magnitude'],'status':'UNRESOLVED_NO_AUTOMATIC_FUZZY_COERCION','candidate_only':ranked})
 bad=[m for m in matches if not m['seat_match']]; exact=sum(m['mapping_type']=='EXACT_NAME' for m in matches); renamed=sum(m['mapping_type']=='RENAMED_EXPLICIT' for m in matches)
 rec={'schema_version':'2.0','year':2007,'phase':'POST_FREEZE_TARGET_RECONCILIATION','anti_leakage':'Snapshot is read-only. Outcome opened only after snapshot freeze commit.','freeze_commit':freeze,'outcome_commit':oc,'snapshot_rows':len(snap),'outcome_rows':len(outcome),'matched_rows':len(matches),'exact_name_rows':exact,'renamed_explicit_rows':renamed,'unresolved_rows':len(unresolved),'unused_outcome_rows':len(unused),'seat_mismatches':len(bad),'matches':matches,'unresolved':unresolved,'unused_outcome_constituencies':[ob[k]['constituency'] for k in sorted(unused)],'seat_mismatch_details':bad}; dump(D/'territorial_reconciliation_v2.json',rec)
 status='PASS_FOR_ROLLING_ORIGIN_BACKTEST' if len(matches)==95 and not unused and not bad else 'PARTIAL_PRE_ELECTION_SNAPSHOT'
 gate={'year':2007,'scientific_status':status,'controls':{'snapshot_freeze_strict_ancestor_of_outcome':'PASS','target_snapshot_mutation':'PASS_READ_ONLY','territorial_row_count':'PASS','seat_arithmetic':'PASS' if not bad and len(matches)==95 else 'REVIEW','silent_fuzzy_coercion':'PASS_NONE_USED'},'reconciliation':{'matched_rows':len(matches),'exact_name_rows':exact,'renamed_explicit_rows':renamed,'unresolved_rows':len(unresolved),'unused_outcome_rows':len(unused),'seat_mismatches':len(bad)},'qualification':'A PASS means the frozen pre-election-derived 95/295 map reconciles one-to-one to the post-freeze 95/295 outcome without changing snapshot bytes. Candidate-feature missingness remains explicit and is not a map leakage failure.'}; dump(D/'acceptance_gate_v2.json',gate); print(json.dumps({'status':status,'matched':len(matches),'exact':exact,'renamed':renamed,'unresolved':len(unresolved),'unused':len(unused),'seat_mismatches':len(bad)},sort_keys=True))
if __name__=='__main__': main()
