import importlib.util
from copy import deepcopy
import pytest
from backend.app.services.scheduler import solve
from backend.app.services.checker import check_plan

HAS_CP_SAT = importlib.util.find_spec('ortools') is not None


def test_demo_solver_calculates_reference_plan(snapshot):
    result=solve(snapshot,'demo_search')
    assert result['engine']=='demo_search'
    assert result['status']=='OPTIMAL'
    allocations={a['request_id']:a for a in result['allocations']}
    assert allocations['R03']['start']=='2026-09-14T02:30:00+08:00'
    assert allocations['R04']['start']=='2026-09-14T02:35:00+08:00'
    assert allocations['R04']['engineer_id']=='E01'
    assert result['objective']==475


def test_changed_input_changes_assignment(snapshot):
    snapshot['engineers'][0]['unavailable']=[{'start':'2026-09-14T02:20:00+08:00','end':'2026-09-14T04:30:00+08:00'}]
    result=solve(snapshot,'demo_search')
    a=next(a for a in result['allocations'] if a['request_id']=='R04')
    assert a['engineer_id']=='E04'
    assert not check_plan(snapshot,result['allocations'],True)


def test_equipment_outage_invalidates_locked_bookings(snapshot):
    snapshot['equipment'][0]['serviceable']=False
    result=solve(snapshot,'demo_search')
    assert result['status']=='REVIEW_REQUIRED'
    assert result['allocations']==[]


def test_impossible_duration_is_not_shortened(snapshot):
    snapshot['requests'][3]['phases'][1]['duration_minutes']=230
    result=solve(snapshot,'demo_search')
    assert result['status']=='INFEASIBLE'
    assert result['allocations']==[]


def test_date_flexibility_uses_different_nights(snapshot):
    snapshot['requests'][2]['allowed_dates']=['2026-09-15']
    result=solve(snapshot,'demo_search')
    assert next(a for a in result['allocations'] if a['request_id']=='R03')['start'].startswith('2026-09-15')


@pytest.mark.skipif(not HAS_CP_SAT,reason='OR-Tools not installed; install requirements-cpsat.txt')
def test_cp_sat_matches_reference_and_checker(snapshot):
    result=solve(snapshot,'cp_sat')
    assert result['engine']=='cp_sat'
    assert result['status']=='OPTIMAL'
    assert result['objective']==475
    assert not check_plan(snapshot,result['allocations'],True)


@pytest.mark.skipif(not HAS_CP_SAT,reason='OR-Tools not installed; install requirements-cpsat.txt')
@pytest.mark.parametrize('extra_minutes',[0,5,10,15,20])
def test_cp_sat_matches_small_reference_solver(snapshot,extra_minutes):
    snapshot['requests'][2]['phases'][1]['duration_minutes']+=extra_minutes
    cp=solve(snapshot,'cp_sat')
    reference=solve(snapshot,'demo_search')
    assert cp['status']==reference['status']=='OPTIMAL'
    assert cp['objective']==reference['objective']
    assert not check_plan(snapshot,cp['allocations'],True)


@pytest.mark.skipif(not HAS_CP_SAT,reason='OR-Tools not installed; install requirements-cpsat.txt')
def test_cp_sat_reassigns_an_absent_engineer(snapshot):
    snapshot['engineers'][0]['unavailable']=[{'start':'2026-09-14T02:20:00+08:00','end':'2026-09-14T04:30:00+08:00'}]
    result=solve(snapshot,'cp_sat')
    assert result['status']=='OPTIMAL'
    assert next(a for a in result['allocations'] if a['request_id']=='R04')['engineer_id']=='E04'
