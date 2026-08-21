from __future__ import annotations

import pathlib
import subprocess
import tempfile
import unittest

from morocco26.agent_society_v4.calibration import CalibrationError, fit_2016, score_2021
from morocco26.agent_society_v4.contracts import CandidateRecord, CandidateState, BallotType, LambdaCalibration
from morocco26.agent_society_v4.electorate import calibrate_to_registered_totals
from morocco26.agent_society_v4.forecast import aggregate_cells, combine, log_ratio_delta, blend
from morocco26.agent_society_v4.historical import HistoricalError, pairing_index, register_surface
from morocco26.agent_society_v4.information_diet import build_information_diet, derive_profile
from morocco26.agent_society_v4.main_adapter import GitSnapshotReader, source_inventory, candidate_records
from morocco26.agent_society_v4.seats import SeatRuleConfig, decode, monte_carlo
from morocco26.agent_society_v4.social import SocialError, apply_social_round
from morocco26.agent_society_v4.society import build_work_item, validate_decision
from morocco26.agent_society_v4.vintage import VintageError, build_named_vintage, diff_vintages

SHA='a'*40

def source(date='2026-08-20'):
    return {'source_id':'S1','tier':'T1','known_at':date}

def option(party,name,state='OFFICIAL',candidate='Candidate'):
    return {'party_id':party,'party_name':name,'candidate':{'status':state,'candidate_name':candidate if state not in {'UNKNOWN','NO_LIST'} else None,'known_at':'2026-08-20' if state not in {'UNKNOWN','NO_LIST'} else None,'sources':[source()] if state not in {'UNKNOWN'} else [],'attributes':{},'unknown_reason':'NOT_VERIFIED' if state=='UNKNOWN' else None},'program_axes':{'employment':'HIGH','health':'MEDIUM','governance':'HIGH'}}

def spec(as_of='2026-08-21'):
    return {'snapshot_id':'S2026','as_of':as_of,'source_main_commit':SHA,'territories':[{'territory_id':'T1','territory_name':'Territory One','region_id':'R1','region_name':'Region One','registered_electorate':1000,'ballots':{'LOCAL':{'contest_id':'L1','options':[option('P1','Party 1'),option('P2','Party 2','UNKNOWN',None)]},'REGIONAL':{'contest_id':'R1','options':[option('P1','Party 1'),option('P2','Party 2')]}}}]}

class VintageTests(unittest.TestCase):
    def test_unknown_is_valid_and_never_named(self):
        snap=build_named_vintage(spec())
        unknown=snap['territories'][0]['ballots']['LOCAL']['options'][1]['candidate']
        self.assertEqual(unknown['status'],'UNKNOWN'); self.assertIsNone(unknown['candidate_name']); self.assertFalse(snap['silent_candidate_imputation'])
    def test_future_candidate_source_fails(self):
        value=spec(); value['territories'][0]['ballots']['LOCAL']['options'][0]['candidate']['known_at']='2026-08-22'; value['territories'][0]['ballots']['LOCAL']['options'][0]['candidate']['sources']=[source('2026-08-22')]
        with self.assertRaises(Exception): build_named_vintage(value)
    def test_two_ballots_required(self):
        value=spec(); del value['territories'][0]['ballots']['REGIONAL']
        with self.assertRaises(VintageError): build_named_vintage(value)
    def test_vintage_diff_is_local(self):
        old=build_named_vintage(spec('2026-08-21')); newer=spec('2026-08-22'); c=newer['territories'][0]['ballots']['LOCAL']['options'][1]['candidate']; c.update(status='DECLARED',candidate_name='New',known_at='2026-08-22',sources=[source('2026-08-22')]); c.pop('unknown_reason',None); new=build_named_vintage(newer); d=diff_vintages(old,new); self.assertEqual(d['affected_contests'],[{'territory_id':'T1','ballot':'LOCAL'}]); self.assertFalse(d['full_national_rerun_required'])

class DietAndSocialTests(unittest.TestCase):
    def test_diet_retains_all_ballot_options(self):
        snap=build_named_vintage(spec()); cell={'cell_id':'C1','political_discussion':0.05,'education_level':'PRIMARY','localism':0.2}; diet=build_information_diet(cell,snap['territories'][0]['ballots']['LOCAL'],snapshot_id=snap['snapshot_id']); self.assertTrue(diet['all_registered_options_retained']); self.assertEqual(len(diet['options']),2); self.assertFalse(diet['omniscient'])
    def test_information_profiles_differ(self):
        low=derive_profile({'political_discussion':0,'education_level':'PRIMARY'}); high=derive_profile({'political_discussion':1,'education_level':'TERTIARY'}); self.assertEqual(low['tier'],'LOW'); self.assertEqual(high['tier'],'HIGH')
    def test_social_layer_cannot_edit_vote_probabilities(self):
        state={'round':0,'parties':{'P1':{'candidate_perception':0}}}
        with self.assertRaises(SocialError): apply_social_round(state,[{'channel':'FAMILY','party_id':'P1','dimension':'candidate_perception','strength':.5,'source_credibility':.8,'vote_delta':.1}],susceptibility=.5,round_index=1)
        out=apply_social_round(state,[{'channel':'FAMILY','party_id':'P1','dimension':'candidate_perception','strength':.5,'source_credibility':.8}],susceptibility=.5,round_index=1); self.assertGreater(out['parties']['P1']['candidate_perception'],0); self.assertTrue(out['direct_probability_adjustment_forbidden'])

class ElectorateAndSocietyTests(unittest.TestCase):
    def test_registered_electorate_reconciles_exactly(self):
        rows=calibrate_to_registered_totals([{'cell_id':'C1','territory_id':'T1','population_weight':100},{'cell_id':'C2','territory_id':'T1','population_weight':200}],{'T1':180}); self.assertAlmostEqual(sum(r['registered_electorate_weight'] for r in rows),180)
    def test_work_item_separates_ballots(self):
        snap=build_named_vintage(spec()); cell={'cell_id':'C1','territory_id':'T1','political_discussion':.5}; work=build_work_item(snap,cell); self.assertEqual(set(work['information_diets']),{'LOCAL','REGIONAL'}); self.assertTrue(work['required_output']['split_ticket_allowed']); decision=validate_decision(work,{'work_item_id':work['work_item_id'],'turnout_probability':.6,'local_party_probabilities':{'P1':.7,'P2':.3},'regional_party_probabilities':{'P1':.3,'P2':.7}}); self.assertNotEqual(decision['local_party_probabilities'],decision['regional_party_probabilities'])

class ForecastTests(unittest.TestCase):
    def test_lambda_zero_returns_structural_baseline(self):
        base={'P1':.6,'P2':.4}; agent={'P1':.2,'P2':.8}; self.assertEqual(blend(base,log_ratio_delta(base,agent),0),base)
    def test_aggregate_and_combine(self):
        delta=aggregate_cells([{'contest_id':'L1','ballot':'LOCAL','contest_scope_id':'T1','registered_electorate_weight':100,'structural_party_probabilities':{'P1':.6,'P2':.4},'agent_party_probabilities':{'P1':.4,'P2':.6},'structural_turnout_probability':.5,'agent_turnout_probability':.6}]); structural={'contests':[{'contest_id':'L1','contest_scope_id':'T1','territory_id':'T1','region_id':'R1','ballot':'LOCAL','registered_electorate':100,'turnout_probability':.5,'party_probabilities':{'P1':.6,'P2':.4}}]}; out=combine(structural,delta,LambdaCalibration()); self.assertEqual(out['scientific_label'],'STRUCTURAL_BASELINE'); self.assertEqual(out['contests'][0]['party_probabilities'],{'P1':.6,'P2':.4})

class CalibrationTests(unittest.TestCase):
    def row(self): return {'development_split':'2016_DEVELOPMENT_ONLY','holdout_2021_visible':False,'local_baseline':{'P1':.6,'P2':.4},'local_society':{'P1':.5,'P2':.5},'local_actual':{'P1':.55,'P2':.45},'regional_baseline':{'P1':.6,'P2':.4},'regional_society':{'P1':.5,'P2':.5},'regional_actual':{'P1':.55,'P2':.45},'turnout_baseline':.5,'turnout_society':.6,'turnout_actual':.55}
    def test_2016_freeze_precedes_2021_holdout(self):
        freeze=fit_2016([self.row()]); self.assertEqual(freeze['status'],'PASS_LAMBDA_FROZEN_BEFORE_2021_HOLDOUT'); hold=dict(self.row()); hold.pop('development_split'); hold.pop('holdout_2021_visible'); hold['holdout_split']='2021_HOLDOUT_ONLY'; score=score_2021([hold],freeze); self.assertEqual(score['status'],'PASS_2021_HOLDOUT_SCORED_NO_RETUNING')
    def test_holdout_visible_during_fit_fails(self):
        row=self.row(); row['holdout_2021_visible']=True
        with self.assertRaises(CalibrationError): fit_2016([row])

class HistoricalTests(unittest.TestCase):
    def test_historical_surface_stays_blind(self):
        bridge={'status':'PASS_FROZEN_MAIN_BRIDGE_READY_FOR_G0_SOL','target_outcomes_present':False,'real_identity_material_present':False,'bridge_id':'B1'}; reg=register_surface({'anonymous_election_id':'E_01'},bridge,election_year=2016); self.assertFalse(reg['outcomes_present']); self.assertFalse(reg['unseal_authorized_here'])
    def test_pairing_requires_exact_cells(self):
        rich=[{'source_work_item_id':'W1','cell_id':'C1','output_ref':'r'}]; blind=[{'source_work_item_id':'W1','cell_id':'C1','output_ref':'b'}]; self.assertEqual(pairing_index(rich,blind)['pair_count'],1)
        with self.assertRaises(HistoricalError): pairing_index(rich,[])

class MainAdapterTests(unittest.TestCase):
    def test_reader_is_commit_pinned_and_filters_future_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); subprocess.run(['git','init','-q',str(root)],check=True); subprocess.run(['git','-C',str(root),'config','user.email','a@b.c'],check=True); subprocess.run(['git','-C',str(root),'config','user.name','T'],check=True); p=root/'morocco26/data/candidate_ledger.json'; p.parent.mkdir(parents=True); p.write_text('[{"territory_id":"T1","party":"P1","candidate_name":"A","status":"OFFICIAL","source_date":"2026-08-20"},{"territory_id":"T1","party":"P2","candidate_name":"B","status":"OFFICIAL","source_date":"2026-08-25"}]'); subprocess.run(['git','-C',str(root),'add','.'],check=True); subprocess.run(['git','-C',str(root),'commit','-qm','x'],check=True); reader=GitSnapshotReader(root,'HEAD'); self.assertEqual(len(reader.commit_sha),40); rows,_=candidate_records(reader,as_of='2026-08-21'); self.assertEqual([r.party_id for r in rows],['P1']); self.assertFalse(source_inventory(reader)['floating_reads'])

class SeatTests(unittest.TestCase):
    def config(self): return SeatRuleConfig('DHONDT','DHONDT',{'T1':3},{'R1':2},{'T1':'R1'},expected_local_total=3,expected_regional_total=2,official_rule_source='fixture')
    def forecast(self): return [{'contest_id':'L1','territory_id':'T1','region_id':None,'ballot':'LOCAL','registered_electorate':1000,'party_probabilities':{'P1':.6,'P2':.4}},{'contest_id':'R1','territory_id':None,'region_id':'R1','ballot':'REGIONAL','registered_electorate':1000,'party_probabilities':{'P1':.4,'P2':.6}}]
    def test_seats_and_monte_carlo(self):
        decoded=decode(self.forecast(),self.config()); self.assertEqual(decoded['seat_total'],5); first=monte_carlo(self.forecast(),self.config(),draws=20,seed=7); second=monte_carlo(self.forecast(),self.config(),draws=20,seed=7); self.assertEqual(first,second)

if __name__=='__main__': unittest.main()
