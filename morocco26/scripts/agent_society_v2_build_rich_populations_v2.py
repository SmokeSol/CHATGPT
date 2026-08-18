#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import pyreadstat
import agent_society_v2_build_rich_populations as b

N=b.N
SEED=b.SEED
EXPECTED={k:v for k,v in b.EXPECTED.items() if k in {"ind","hh","encdm"}}
RICH_SOURCE_FAMILIES=["RGPH2014_INDIVIDUAL_MICRODATA","RGPH2014_HOUSEHOLD_MICRODATA","RGPH_DERIVED_HOUSEHOLD","ENCDM2014_SES_DONOR","PRIOR_ELECTION_ANCHOR","HCP_PRE_ELECTION_LABOUR_CONTEXT"]
ATTITUDE_CONTEXT={
  2016:{"source":"Afrobarometer Round 6 Morocco","fieldwork":"2015-11-02/2015-11-22","mode":"AGGREGATE_CONTEXT_RESERVED_NOT_PERSON_LEVEL_ASSIGNED","reason":"Raw respondent SAV is protected by an anti-bot challenge in the execution environment. No synthetic person-level attitudes are fabricated."},
  2021:{"source":"Afrobarometer Round 8 Morocco","fieldwork":"2021-02-08/2021-02-25","mode":"AGGREGATE_CONTEXT_RESERVED_NOT_PERSON_LEVEL_ASSIGNED","reason":"Raw respondent SAV is protected by an anti-bot challenge in the execution environment. No synthetic person-level attitudes are fabricated."}
}

def build_record(p,h,c,hd,im,hm,w,year,enc,eidx,ti):
    delta=2 if year==2016 else 7
    head_age=b.safe_int(hd.get("head_age2014",p["age2014"]),int(p["age2014"]))+delta
    rec={
      "archetype_id":None,"weight":float(w),"prior_vote_or_abstention":str(p["prior_vote_or_abstention"]),
      "age_years":int(p["age_target"]),"age_band":p["age_band"],"sex":p["sex"],"urban_rural":p["urban_rural"],
      "marital_status":b.code_label(im,"E_MAT",p["E_MAT"]),"relationship_to_household_head":b.code_label(im,"LIEN_CM",p["LIEN_CM"]),
      "children_ever_living":None if pd.isna(p["ENF_VIV"]) or float(p["ENF_VIV"])>=90 else int(p["ENF_VIV"]),
      "education_level":b.code_label(im,"NIV_ET_AGR",p["NIV_ET_AGR"]),"education_detailed":b.code_label(im,"NIV_ET",p["NIV_ET"]),
      "schooling_status":b.code_label(im,"scol",p["scol"]),"literacy_status":b.code_label(im,"LIR_ECR",p["LIR_ECR"]),"diploma_group":b.code_label(im,"EG_DIP_SGG",p["EG_DIP_SGG"]),
      "activity_status":p["activity_status"],"occupation_group":b.code_label(im,"PROF_GG",p["PROF_GG"]),"occupation_detailed":b.code_label(im,"PROF_SGG",p["PROF_SGG"]),
      "professional_status":b.code_label(im,"STAT_PROF",p["STAT_PROF"]),"industry_sector":b.code_label(im,"ACT_SECTEUR",p["ACT_SECTEUR"]),"industry_section":b.code_label(im,"ACT_SECTION",p["ACT_SECTION"]),
      "workplace_geography":b.code_label(im,"TRAV_LIEU",p["TRAV_LIEU"]),"commute_mode":b.code_label(im,"TRAV_TRANS",p["TRAV_TRANS"]),
      "household_size":b.safe_int(h.get("taille",1),1),"dwelling_type":b.code_label(hm,"TYPE_LOG",h.get("TYPE_LOG",np.nan)),
      "wall_material":b.code_label(hm,"murs",h.get("murs",np.nan)),"roof_material":b.code_label(hm,"toit",h.get("toit",np.nan)),"floor_material":b.code_label(hm,"sol",h.get("sol",np.nan)),
      "dwelling_age":b.code_label(hm,"AGE_LOG",h.get("AGE_LOG",np.nan)),"rooms":None if pd.isna(h.get("pieces",np.nan)) else b.safe_int(h.get("pieces")),"tenure_status":b.code_label(hm,"STAT_OCC",h.get("STAT_OCC",np.nan)),
      "kitchen_available":b.code_label(hm,"cuis",h.get("cuis",np.nan)),"toilet_available":b.code_label(hm,"wc",h.get("wc",np.nan)),"bath_shower_available":b.code_label(hm,"bd",h.get("bd",np.nan)),"local_bath_available":b.code_label(hm,"bloc",h.get("bloc",np.nan)),
      "lighting_mode":b.code_label(hm,"ECL_MODE",h.get("ECL_MODE",np.nan)),"water_supply_mode":b.code_label(hm,"EAU_MODE",h.get("EAU_MODE",np.nan)),"wastewater_mode":b.code_label(hm,"EAUX_US",h.get("EAUX_US",np.nan)),"waste_disposal_mode":b.code_label(hm,"dech",h.get("dech",np.nan)),
      "gas_cooking":b.code_label(hm,"gaz",h.get("gaz",np.nan)),"electric_cooking":b.code_label(hm,"elec",h.get("elec",np.nan)),"charcoal_cooking":b.code_label(hm,"char",h.get("char",np.nan)),"wood_cooking":b.code_label(hm,"bois",h.get("bois",np.nan)),"livestock_status":b.code_label(hm,"DEJ_ANIM",h.get("DEJ_ANIM",np.nan)),
      "tv_owned":b.code_label(hm,"tele",h.get("tele",np.nan)),"radio_owned":b.code_label(hm,"radio",h.get("radio",np.nan)),"mobile_phone_owned":b.code_label(hm,"TEL_PORT",h.get("TEL_PORT",np.nan)),"fixed_phone_owned":b.code_label(hm,"TEL_FIXE",h.get("TEL_FIXE",np.nan)),"internet_owned":b.code_label(hm,"net",h.get("net",np.nan)),"computer_owned":b.code_label(hm,"pc",h.get("pc",np.nan)),"satellite_owned":b.code_label(hm,"parab",h.get("parab",np.nan)),"refrigerator_owned":b.code_label(hm,"frigo",h.get("frigo",np.nan)),
      "cars_count":b.safe_int(h.get("voit",0),0),"motorcycles_count":b.safe_int(h.get("moto",0),0),"trucks_count":b.safe_int(h.get("cam",0),0),"tractors_count":b.safe_int(h.get("tract",0),0),
      "paved_road_distance_km":None if pd.isna(h.get("ROUTE_DIST",np.nan)) else float(h.get("ROUTE_DIST")),"household_type":b.code_label(hm,"MEN_TYPE",h.get("MEN_TYPE",np.nan)),
      "household_children_count":b.safe_int(c.get("child",0),0),"household_adult_count":b.safe_int(c.get("adult",0),0),"household_elderly_count":b.safe_int(c.get("elderly",0),0),"household_worker_count":b.safe_int(c.get("worker",0),0),"household_unemployed_count":b.safe_int(c.get("unemployed",0),0),"household_student_count":b.safe_int(c.get("student",0),0),
      "dependency_ratio":float((c.get("child",0)+c.get("elderly",0))/max(1,c.get("adult",1))),"persons_per_room":float(b.safe_int(h.get("taille",1),1)/max(1,b.safe_int(h.get("pieces",1),1))),"asset_index":b.profile_asset(h),"basic_services_index":b.profile_services(h),
      "head_sex":b.sex_band(hd.get("head_sex",p["sexe"])),"head_age_band":b.age_band(head_age),"head_education_band":b.edu_band(hd.get("head_edu",p["NIV_ET_AGR"])),
      "target_year_unemployment_rate":float(b.LABOR[year]["unemployment"]),"target_year_youth_unemployment_rate":float(b.LABOR[year]["youth_unemployment"]),"target_year_female_unemployment_rate":float(b.LABOR[year]["female_unemployment"]),"target_year_underemployment_rate":float(b.LABOR[year]["underemployment"]),
    }
    donor={**p.to_dict(),**h.to_dict(),"head_sex":hd.get("head_sex",p["sexe"]),"head_age_target":head_age,"head_edu":hd.get("head_edu",p["NIV_ET_AGR"])}
    rec.update(b.ses_features(b.pick_encdm(enc,eidx,donor,SEED+year+ti)))
    return rec

def main():
    ap=argparse.ArgumentParser()
    for n in ["ind","hh","encdm","pop2016","pop2021","outdir"]: ap.add_argument("--"+n,required=True)
    a=ap.parse_args(); out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    for k,p in [("ind",a.ind),("hh",a.hh),("encdm",a.encdm)]:
        s=b.sha(p)
        if s!=EXPECTED[k]: raise RuntimeError(f"{k} sha mismatch {s}")
    print("loading RGPH individual...")
    ind,im=pyreadstat.read_dta(a.ind,usecols=b.IND_COLS,apply_value_formats=False)
    ind["age2014"]=[b.age2014(r) for r in ind.itertuples(index=False)]; ind=ind[ind.age2014.notna()].copy(); ind["age2014"]=ind.age2014.astype(int)
    prolabels=(im.variable_value_labels or {}).get("pro",{}); ind["pro_name"]=ind["pro"].map(prolabels).fillna(ind["pro"].astype(str)); ind["pro_norm"]=ind.pro_name.map(b.norm)
    head=(ind[pd.to_numeric(ind.LIEN_CM,errors="coerce")==0][["pro","MEN_PRO","sexe","age2014","NIV_ET_AGR","TY_ACT"]].copy().drop_duplicates(["pro","MEN_PRO"]).rename(columns={"sexe":"head_sex","age2014":"head_age2014","NIV_ET_AGR":"head_edu","TY_ACT":"head_activity"}).set_index(["pro","MEN_PRO"]))
    comp={2016:b.build_hh_comp(ind,2016),2021:b.build_hh_comp(ind,2021)}
    print("loading household and ENCDM...")
    hh,hm=pyreadstat.read_dta(a.hh,usecols=b.HH_COLS,apply_value_formats=False); hh=hh.drop_duplicates(["pro","MEN_PRO"]).set_index(["pro","MEN_PRO"])
    enc,_=pyreadstat.read_sav(a.encdm,usecols=b.ENCDM_COLS,apply_value_formats=False); eidx=b.donor_index_encdm(enc)
    pops={2016:json.load(open(a.pop2016)),2021:json.load(open(a.pop2021))}; all_records=[]; audits={}
    for year in [2016,2021]:
        delta=2 if year==2016 else 7; ind["age_target"]=ind.age2014+delta; ind["age_band"]=ind.age_target.map(b.age_band); ind["sex"]=ind.sexe.map(b.sex_band); ind["urban_rural"]=ind.mil.map(b.ur_band); ind["education_band"]=ind.NIV_ET_AGR.map(b.edu_band); ind["activity_status"]=ind.TY_ACT.map(b.act_band); eligible=ind[ind.age_target>=18].copy()
        base_rates={}
        for u in ["URBAN","RURAL","ALL"]:
            q=eligible if u=="ALL" else eligible[eligible.urban_rural==u]; ww=pd.to_numeric(q.pds,errors="coerce").fillna(1).clip(lower=0).to_numpy(); aa=q.activity_status.to_numpy(); den=ww[np.isin(aa,["ACTIVE_EMPLOYED","UNEMPLOYED"])].sum(); num=ww[aa=="UNEMPLOYED"].sum(); base_rates[u]=float(num/den) if den else .1
        territories=[]; year_records=[]; fail=[]; available=set(eligible.pro_norm.drop_duplicates())
        for ti,t in enumerate(pops[year]["territories"]):
            cid=t["constituency_id"]; parent,geo0=b.resolve_parent(t["prefecture_or_province"],available); pool=eligible[eligible.pro_norm==parent]
            if len(pool)<N: fail.append({"constituency_id":cid,"reason":"INSUFFICIENT_PARENT_POOL","parent":parent,"rows":len(pool)}); continue
            pw=pd.to_numeric(pool.pds,errors="coerce").fillna(1).clip(lower=.000001).to_numpy(float); lm=np.array([b.labour_multiplier(ac,u,year,base_rates) for ac,u in zip(pool.activity_status,pool.urban_rural)]); sw=pw*lm; tm=b.margins(pool,sw); prior=t["target_marginals"]["prior_vote_or_abstention"]; best=None
            for attempt in range(48):
                rng=np.random.default_rng(SEED+year*100000+ti*101+attempt); pick=rng.choice(len(pool),N,replace=False,p=sw/sw.sum()); r=b.prior_assign(pool.iloc[pick].copy().reset_index(drop=True),prior,SEED+year+ti+attempt); targets={**tm,"prior_vote_or_abstention":prior}; w,err=b.ipf(r,targets)
                if w is None: continue
                ess=float(1/(w*w).sum()); mw=float(w.max()); cand=(err,-ess,mw,r,w)
                if best is None or cand[:3]<best[:3]: best=cand
                if err<2e-8 and ess>=128 and mw<=.05: break
            if best is None or best[0]>5e-6 or -best[1]<128 or best[2]>.05: fail.append({"constituency_id":cid,"reason":"IPF_GATE","best":None if best is None else {"err":best[0],"ess":-best[1],"max_weight":best[2]}}); continue
            err,negess,mw,r,w=best; records=[]
            for j,p in r.iterrows():
                key=(p["pro"],p["MEN_PRO"]); h=hh.loc[key] if key in hh.index else pd.Series(dtype=object); c=comp[year].loc[key] if key in comp[year].index else pd.Series(dtype=object); hd=head.loc[key] if key in head.index else pd.Series(dtype=object); rec=build_record(p,h,c,hd,im,hm,w[j],year,enc,eidx,ti); rec["archetype_id"]=f"R{j+1:03d}"; records.append(rec)
            geo="PARENT_PROXY_SPLIT_CONSTITUENCY" if cid in b.SPLIT else geo0; safe=[k for k in records[0] if k not in ("archetype_id","weight","prior_vote_or_abstention")]; q={"raking_max_abs_error":float(err),"effective_archetype_count":float(-negess),"max_single_archetype_weight":float(mw),"geography_confidence":geo,"observed_or_derived_voter_dimensions":len(safe)}
            territories.append({"constituency_id":cid,"constituency_name":t["constituency_name"],"prefecture_or_province":t["prefecture_or_province"],"prior_election_year":t["prior_election_year"],"prior_historical_match":t["prior_historical_match"],"geography_confidence":geo,"target_core_marginals":targets,"quality":q,"archetypes":records}); year_records += [{**rr,"year":year,"constituency_id":cid,"geography_confidence":geo} for rr in records]
        output={"schema_version":"1.1","population_id":f"M26-ASV2-RICH-{year}-POP-V2","experiment_id":"M26-AGENT-SOCIETY-V2-001","target_election_year":year,"status":"PASS" if not fail and len(territories)==92 else "FAIL","archetypes_per_constituency":N,"target_outcome_used":False,"real_llm_outputs_used":False,"source_hashes":EXPECTED,"source_families":RICH_SOURCE_FAMILIES,"pre_election_attitude_context":ATTITUDE_CONTEXT[year],"target_year_update":{"aging_years":delta,"labor_context":b.LABOR[year]},"territories":territories,"failures":fail}; b.jsave(out/f"{year}_rich_population_v2.json",output); all_records += year_records; audits[year]={"territories":len(territories),"failures":fail,"min_ess":min((t["quality"]["effective_archetype_count"] for t in territories),default=0),"max_weight":max((t["quality"]["max_single_archetype_weight"] for t in territories),default=1),"direct_geo":sum(t["geography_confidence"]=="DIRECT_MICRODATA_ADMIN" for t in territories),"proxy_geo":sum(t["geography_confidence"]!="DIRECT_MICRODATA_ADMIN" for t in territories)}; print(year,audits[year])
    if not all_records: raise RuntimeError("no RICH records produced")
    r0=["age_band","sex","urban_rural","education_level","activity_status","prior_vote_or_abstention"]; rich=[k for k in all_records[0] if k not in {"archetype_id","weight","year","constituency_id","geography_confidence"}]; rng=np.random.default_rng(SEED); sample=[all_records[i] for i in rng.choice(len(all_records),min(12000,len(all_records)),replace=False)]; er0=b.effective_rank(sample,r0); err=b.effective_rank(sample,rich); ratio=err["effective_rank"]/er0["effective_rank"]
    cert={"schema_version":"1.1","certificate_id":"M26-ASV2-RICH-DATA-POWER-CERTIFICATE-V2","experiment_id":"M26-AGENT-SOCIETY-V2-001","target_outcomes_used":False,"real_llm_outputs_used":False,"individual_attitude_donor_used":False,"attitude_layer_status":"AGGREGATE_CONTEXT_ONLY_RESERVED; NOT COUNTED TOWARD X10 VOTER INFORMATION","safe_feature_count":len(rich),"source_families":RICH_SOURCE_FAMILIES,"R0_effective_rank":er0,"RICH_effective_rank":err,"effective_rank_ratio":ratio,"year_audits":audits,"sensitive_or_direct_vote_features_included":False,"geography_robustness_rule":"Historical scoring must report ALL_92 and DIRECT_MICRODATA_ADMIN_ONLY; proxy-confined effects are rejected.","gates":{"all_92_both_years":all(audits[y]["territories"]==92 and not audits[y]["failures"] for y in [2016,2021]),"safe_dimensions_ge_60":len(rich)>=60,"source_families_ge_5":len(RICH_SOURCE_FAMILIES)>=5,"effective_rank_ratio_ge_10":ratio>=10,"min_ess_ge_128":min(audits[y]["min_ess"] for y in [2016,2021])>=128,"max_weight_le_0_05":max(audits[y]["max_weight"] for y in [2016,2021])<=.05,"no_sensitive_or_direct_vote_features":True,"x10_does_not_rely_on_person_level_survey_imputation":True}}; cert["overall_pass"]=all(cert["gates"].values()); cert["status"]="ASV2_RICH_DATA_POWER_PASS" if cert["overall_pass"] else "ASV2_RICH_DATA_POWER_INSUFFICIENT"; b.jsave(out/"rich_data_power_certificate_v2.json",cert); print(json.dumps(cert,indent=2))
    if not cert["overall_pass"]: raise SystemExit(2)
    with zipfile.ZipFile(out/"asv2-rich-populations-v2.zip","w",zipfile.ZIP_DEFLATED) as z:
        for fn in ["2016_rich_population_v2.json","2021_rich_population_v2.json","rich_data_power_certificate_v2.json"]: z.write(out/fn,fn)
if __name__=="__main__": main()
