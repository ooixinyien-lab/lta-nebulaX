import importlib.util
from copy import deepcopy
import pytest
from backend.app.services.scheduler import solve
from backend.app.services.checker import check_plan
from backend.app.services.common import make_allocation
from scripts.generate_synthetic_dataset import (
    build_feasible_snapshot,
    build_trivial_fastpath_scenario,
)

HAS_CP_SAT = importlib.util.find_spec('ortools') is not None


@pytest.fixture(autouse=True)
def approve_seed_work(snapshot):
    for request in snapshot['requests']:
        if request['status']=='submitted':
            request['status']='approved'


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


def test_demo_solver_preserves_manual_lock(snapshot):
    request=next(r for r in snapshot['requests'] if r['id']=='R03')
    locked=make_allocation(request,'2026-09-14T02:30:00+08:00','E03',locked=True)
    result=solve(snapshot,'demo_search',locked_allocations=[locked])
    allocation=next(a for a in result['allocations'] if a['request_id']=='R03')
    assert allocation['start']=='2026-09-14T02:30:00+08:00'
    assert allocation['locked'] is True
    assert not check_plan(snapshot,result['allocations'],True)


@pytest.mark.skipif(not HAS_CP_SAT,reason='OR-Tools not installed; install requirements-cpsat.txt')
def test_cp_sat_dispatches_to_the_canonical_full_solver():
    """The integration seam returns the full solver's independently checked result."""
    snapshot = build_feasible_snapshot().to_dict()
    result=solve(snapshot,'cp_sat')
    assert result['engine']=='cp_sat'
    assert result['solver_version']=='full'
    assert result['status']=='OPTIMAL'
    assert result['validation']['valid'] is True
    assert result['objective_components']['moved_count']==0


@pytest.mark.skipif(not HAS_CP_SAT,reason='OR-Tools not installed; install requirements-cpsat.txt')
def test_cp_sat_recovery_uses_the_full_result_contract():
    """A proven strict failure is distinct from a valid recovery result."""
    snapshot = build_trivial_fastpath_scenario('domain_impossible').to_dict()
    result=solve(snapshot,'cp_sat')
    assert result['strict_status']=='INFEASIBLE'
    assert result['recovery_status']=='OPTIMAL'
    assert result['mode']=='recovery'
    assert result['deferred_requests'][0]['request_id']=='REQ_IMPOSSIBLE'


@pytest.mark.skipif(not HAS_CP_SAT,reason='OR-Tools not installed; install requirements-cpsat.txt')
def test_cp_sat_rejects_a_fixture_without_an_explicit_planning_night(snapshot):
    """The canonical engine never guesses the first engineering window."""
    result=solve(snapshot,'cp_sat')
    assert result['status']=='INPUT_ERROR'
    assert 'planning night' in result['message'].lower()
