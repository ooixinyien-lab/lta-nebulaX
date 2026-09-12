from copy import deepcopy
from backend.app.services.checker import check_plan, unary_issues
from backend.app.services.common import preferred_plan, make_allocation
from backend.app.services.demo_search import solve
import pytest


@pytest.fixture(autouse=True)
def approve_seed_work(snapshot):
    for request in snapshot['requests']:
        if request['status']=='submitted':
            request['status']='approved'


def codes(problems):
    return {p['code'] for p in problems}

def test_known_initial_conflicts(snapshot):
    found = codes(check_plan(snapshot, preferred_plan(snapshot), True))
    assert found == {'DEPENDENCY','POWER','ENGINEER','EQUIPMENT','MANPOWER'}

def test_existing_bookings_are_feasible(snapshot):
    assert check_plan(snapshot, snapshot['committed_allocations']) == []

def test_complete_solution_passes_independent_checker(snapshot):
    result = solve(snapshot)
    assert not check_plan(snapshot, result['allocations'], require_all=True)

def test_phase_duration_cannot_be_shortened(snapshot):
    a = deepcopy(snapshot['committed_allocations'][0])
    a['end'] = '2026-09-14T02:10:00+08:00'
    assert 'DURATION' in codes(unary_issues(snapshot,snapshot['requests'][0],a))

def test_wrong_qualification(snapshot):
    a=make_allocation(snapshot['requests'][3], '2026-09-14T02:35:00+08:00','E03')
    assert 'QUALIFICATION' in codes(unary_issues(snapshot,snapshot['requests'][3],a))

def test_shared_power_zone_even_when_track_sectors_differ(snapshot):
    problems=check_plan(snapshot,preferred_plan(snapshot))
    assert any(p['code']=='POWER' and p['resource']=='Z01' for p in problems)
    assert not any(p['code']=='SPACE' for p in problems)

def test_insufficient_transfer_after_nonoverlap(snapshot):
    allocation=make_allocation(snapshot['requests'][3],'2026-09-14T02:20:00+08:00','E01')
    assert {'ENGINEER','EQUIPMENT'} <= codes(check_plan(snapshot,snapshot['committed_allocations']+[allocation]))

def test_resource_absence(snapshot):
    snapshot['engineers'][3]['unavailable']=[{'start':'2026-09-14T02:30:00+08:00','end':'2026-09-14T04:30:00+08:00'}]
    a=make_allocation(snapshot['requests'][3],'2026-09-14T02:35:00+08:00','E04')
    assert 'RESOURCE_UNAVAILABLE' in codes(unary_issues(snapshot,snapshot['requests'][3],a))

def test_missing_mandatory_requests_are_not_silently_dropped(snapshot):
    assert 'MISSING_WORK' in codes(check_plan(snapshot,snapshot['committed_allocations'],True))

def test_locked_booking_cannot_move(snapshot):
    plan=deepcopy(snapshot['committed_allocations'])
    plan[0]['start']='2026-09-14T01:05:00+08:00'
    assert 'LOCKED_BOOKING' in codes(check_plan(snapshot,plan))

def test_blackout_in_protection_footprint(snapshot):
    r=deepcopy(snapshot['requests'][3]);r['work_sector']='S06';r['protected_sectors']=['S06']
    a=make_allocation(r,'2026-09-14T03:00:00+08:00','E04')
    assert 'BLACKOUT' in codes(unary_issues(snapshot,r,a))

def test_missing_compatibility_rule_requests_review(snapshot):
    del snapshot['planning_rules']['power_compatibility']['OFF']['ON']
    assert 'REVIEW_REQUIRED' in codes(check_plan(snapshot,preferred_plan(snapshot)))

def test_handback_must_fit_window(snapshot):
    r=snapshot['requests'][3]
    a=make_allocation(r,'2026-09-14T03:30:00+08:00','E04')
    assert {'REQUEST_WINDOW','ENGINEERING_WINDOW'} <= codes(unary_issues(snapshot,r,a))
