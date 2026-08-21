from __future__ import annotations
import pathlib,subprocess,tempfile,unittest
from morocco26.agent_society_v4.vintage import build_named_vintage,VintageError
from morocco26.agent_society_v4.information_diet import build_information_diet
from morocco26.agent_society_v4.main_adapter import GitSnapshotReader,program_records,territory_records

def src(): return {'source_id':'P','known_at':'2026-08-20','tier':'T1'}
def spec(): return {'snapshot_id':'S','as_of':'2026-08-21','source_main_commit':'a'*40,'territories':[{'territory_id':'T1','territory_name':'One','region_id':'R1','registered_electorate':100,'ballots':{'LOCAL':{'options':[{'party_id':'P1','party_name':'P1','candidate':{'status':'OFFICIAL','candidate_name':'A','known_at':'2026-08-20','sources':[src()]},'program_axes':{'x':'HIGH'},'program_sources':[src()]},{'party_id':'P2','party_name':'P2','candidate':{'status':'NO_LIST','candidate_name':None,'known_at':'2026-08-20','sources':[src()]},'program_axes':{},'program_sources':[]},{'party_id':'P3','party_name':'P3','candidate':{'status':'UNKNOWN','candidate_name':None,'known_at':None,'sources':[]},'program_axes':{},'program_sources':[]}]},'REGIONAL':{'options':[{'party_id':'P1','party_name':'P1','candidate':{'status':'UNKNOWN','candidate_name':None,'known_at':None,'sources':[]},'program_axes':{},'program_sources':[]},{'party_id':'P3','party_name':'P3','candidate':{'status':'UNKNOWN','candidate_name':None,'known_at':None,'sources':[]},'program_axes':{},'program_sources':[]}]}}}]}
class CaveatTests(unittest.TestCase):
    def test_no_list_is_not_vote_option(self):
        snap=build_named_vintage(spec()); diet=build_information_diet({'cell_id':'C1','political_discussion':.2},snap['territories'][0]['ballots']['LOCAL'],snapshot_id='S'); self.assertEqual({x['party_id'] for x in diet['options']},{'P1','P3'}); self.assertEqual(diet['excluded_non_ballot_options'],[{'party_id':'P2','reason':'NO_LIST'}])
    def test_program_axes_need_provenance(self):
        value=spec(); value['territories'][0]['ballots']['LOCAL']['options'][0]['program_sources']=[]
        with self.assertRaises(VintageError): build_named_vintage(value)
    def test_program_and_territory_adapters_are_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); subprocess.run(['git','init','-q',str(root)],check=True); subprocess.run(['git','-C',str(root),'config','user.email','a@b.c'],check=True); subprocess.run(['git','-C',str(root),'config','user.name','T'],check=True); d=root/'morocco26/data'; d.mkdir(parents=True); (d/'party_program.json').write_text('[{"party":"P1","axes":{"employment":"HIGH"},"as_of":"2026-08-20"}]'); (d/'territory_crosswalk.json').write_text('[{"territory_id":"T1","territory_name":"One","region_id":"R1"}]'); subprocess.run(['git','-C',str(root),'add','.'],check=True); subprocess.run(['git','-C',str(root),'commit','-qm','x'],check=True); reader=GitSnapshotReader(root,'HEAD'); programs,_=program_records(reader,as_of='2026-08-21'); territories=territory_records(reader); self.assertEqual(programs[0]['party_id'],'P1'); self.assertEqual(territories[0]['territory_id'],'T1'); self.assertEqual(len(reader.commit_sha),40)
if __name__=='__main__': unittest.main()
