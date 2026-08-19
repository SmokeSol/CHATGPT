import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("lsa",ROOT/"scripts"/"legal_seat_allocator.py")
lsa=importlib.util.module_from_spec(spec); spec.loader.exec_module(lsa)

def test_2002_three_percent_threshold():
    votes={"A":6000,"B":3000,"C":250}
    r=lsa.allocate(votes,3,2002)
    assert "C" in r["excluded_lists"]
    assert abs(r["quotient"]-(9250/3))<1e-9
    assert sum(r["seats"].values())==3

def test_2007_six_percent_threshold():
    votes={"A":6000,"B":3000,"C":500}
    r=lsa.allocate(votes,3,2007)
    assert "C" in r["excluded_lists"]
    assert abs(r["quotient"]-(9500/3))<1e-9
    assert sum(r["seats"].values())==3

def test_2016_three_percent_threshold_and_all_valid_vote_quotient():
    votes={"A":20000,"B":13000,"C":9000,"D":5600,"E":1400}
    r=lsa.allocate(votes,4,2016)
    assert abs(r["quotient"]-12250)<1e-9
    assert r["seats"]["E"]==0
    assert r["seats"]["A"]==2
    assert r["seats"]["B"]==1
    assert r["seats"]["C"]==1
    assert sum(r["seats"].values())==4

def test_2011_six_percent_threshold():
    votes={"A":6000,"B":3000,"C":500}
    r=lsa.allocate(votes,3,2011)
    assert "C" in r["excluded_lists"]
    assert abs(r["quotient"]-(9500/3))<1e-9
    assert sum(r["seats"].values())==3

def test_2011_national_must_be_allocated_by_independent_segment():
    with pytest.raises(lsa.AllocationError,match="independently"):
        lsa.allocate({"A":6000,"B":4000},90,2011,tier="national")
    assert lsa.allocate({"A":6000,"B":4000},60,2011,tier="national")["seats_allocated"]==60

def test_2021_registered_voter_quotient():
    votes={"A":24000,"B":20000,"C":15000,"D":10000,"E":5000}
    r=lsa.allocate(votes,4,2021,registered_voters=100000)
    assert r["quotient"]==25000
    assert r["seats"]=={"A":1,"B":1,"C":1,"D":1,"E":0}

def test_2021_shares_are_insufficient():
    with pytest.raises(lsa.AllocationError,match="shares alone are insufficient"):
        lsa.allocate_from_shares({"A":.5,"B":.3,"C":.2},3,2021)

def test_other_bucket_rejected():
    with pytest.raises(lsa.AllocationError,match="OTHER"):
        lsa.allocate({"A":1000,"OTHER":900},2,2016)

def test_unique_list_2021_requires_one_fifth_registered():
    r=lsa.allocate({"A":19000},3,2021,registered_voters=100000)
    assert r["status"]=="UNIQUE_LIST_BELOW_REGISTERED_VOTER_MINIMUM"
    r=lsa.allocate({"A":21000},3,2021,registered_voters=100000)
    assert r["seats_allocated"]>=1
