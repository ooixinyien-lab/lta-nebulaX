import json
import pytest


def approve_pending(client, officer, request_ids=None):
    response=client.patch('/api/requests/approval',headers=officer,json={
        'request_ids':request_ids or ['R03','R04'],'approved':True})
    assert response.status_code==200,response.text
    return response.json()


def test_no_identity_cannot_read_data(client):
    assert client.get('/api/planning-snapshot').status_code==401


def test_requester_sees_only_own_requests(client,requester):
    snapshot=client.get('/api/planning-snapshot',headers=requester).json()
    assert {r['id'] for r in snapshot['requests']}=={'R01','R04'}
    assert all(r['owner_id']=='demo-track' for r in snapshot['requests'])
    assert any(o['label']=='Reserved' for o in snapshot['occupancy'])


def test_officer_sees_all(client,officer):
    assert len(client.get('/api/planning-snapshot',headers=officer).json()['requests'])==4


@pytest.mark.parametrize('path',['/api/conflicts/check','/api/schedule/proposals','/api/demo/reset'])
def test_requester_cannot_call_officer_actions(client,requester,path):
    assert client.post(path,headers=requester).status_code==403


def test_owner_id_cannot_be_spoofed(client,requester,new_request):
    new_request['owner_id']='demo-officer'
    assert client.post('/api/requests',headers=requester,json=new_request).status_code==422


def test_request_persists_without_becoming_a_booking(client,requester,new_request):
    response=client.post('/api/requests',headers=requester,json=new_request)
    assert response.status_code==201, response.text
    created=response.json()
    assert created['owner_id']=='demo-track'
    snapshot=client.get('/api/planning-snapshot',headers=requester).json()
    assert created['id'] in {r['id'] for r in snapshot['requests']}
    assert created['id'] not in {a['request_id'] for a in snapshot['committed_allocations']}
    assert snapshot['metadata']['planning_version']==2


def test_cannot_cancel_someone_elses_request(client,requester):
    assert client.post('/api/requests/R03/cancel',headers=requester).status_code==404


def test_can_withdraw_own_unbooked_request(client,requester):
    assert client.post('/api/requests/R04/cancel',headers=requester).status_code==200


def test_officer_cannot_submit_as_a_requester(client,officer,new_request):
    assert client.post('/api/requests',headers=officer,json=new_request).status_code==403


def test_requester_cannot_approve_or_lock(client,requester):
    assert client.patch('/api/requests/approval',headers=requester,json={'request_ids':['R03'],'approved':True}).status_code==403
    assert client.patch('/api/allocations/locks',headers=requester,json={'request_ids':['R01'],'locked':False}).status_code==403


def test_unapproved_requests_do_not_enter_solver(client,officer):
    result=client.post('/api/schedule/proposals',headers=officer,json={})
    assert result.status_code==409
    assert 'No approved' in result.text


def test_conflicts_come_from_the_checker(client,officer):
    result=client.post('/api/conflicts/check',headers=officer).json()
    assert result['issues']==[]
    approve_pending(client,officer)
    result=client.post('/api/conflicts/check',headers=officer).json()
    assert len(result['issues'])==5


def test_generate_then_publish(client,officer):
    approve_pending(client,officer)
    p=client.post('/api/schedule/proposals',headers=officer).json()
    assert p['status']=='OPTIMAL'
    before=client.get('/api/planning-snapshot',headers=officer).json()
    assert len(before['committed_allocations'])==2
    commit=client.post(f"/api/proposals/{p['id']}/commit",headers=officer,json={'expected_version':p['planning_version']})
    assert commit.status_code==200,commit.text
    after=client.get('/api/planning-snapshot',headers=officer).json()
    assert len(after['committed_allocations'])==4
    assert all(r['status']=='scheduled' for r in after['requests'])
    assert after['metadata']['planning_version']==before['metadata']['planning_version']+1
    assert client.post(f"/api/proposals/{p['id']}/commit",headers=officer,json={'expected_version':p['planning_version']}).status_code==409


def test_manual_plan_check_and_stage(client,officer):
    approve_pending(client,officer)
    automatic=client.post('/api/schedule/proposals',headers=officer).json()
    drafts=[{'request_id':a['request_id'],'start':a['start'],'engineer_id':a['engineer_id'],'locked':a.get('locked',False) or a['request_id']=='R03'} for a in automatic['allocations']]
    checked=client.post('/api/schedule/check',headers=officer,json={'allocations':drafts})
    assert checked.status_code==200, checked.text
    assert checked.json()['valid'] is True
    staged=client.post('/api/schedule/manual-proposals',headers=officer,json={'allocations':drafts})
    assert staged.status_code==200, staged.text
    assert staged.json()['engine']=='manual'
    assert staged.json()['status']=='VALID'


def test_solver_preserves_pending_job_lock(client,officer):
    approve_pending(client,officer)
    payload={'locked_allocations':[{'request_id':'R03','start':'2026-09-14T02:30:00+08:00','engineer_id':'E03','locked':True}]}
    result=client.post('/api/schedule/proposals',headers=officer,json=payload)
    assert result.status_code==200, result.text
    allocation=next(a for a in result.json()['allocations'] if a['request_id']=='R03')
    assert allocation['start']=='2026-09-14T02:30:00+08:00'
    assert allocation['locked'] is True


def test_conflicting_solver_lock_returns_issues(client,officer):
    approve_pending(client,officer)
    payload={'locked_allocations':[{'request_id':'R03','start':'2026-09-14T01:30:00+08:00','engineer_id':'E03','locked':True}]}
    result=client.post('/api/schedule/proposals',headers=officer,json=payload)
    assert result.status_code==200, result.text
    assert result.json()['status']=='LOCK_CONFLICT'
    assert result.json()['issues']


def test_stale_proposal_cannot_commit(client,officer):
    approve_pending(client,officer)
    p=client.post('/api/schedule/proposals',headers=officer).json()
    changed=client.patch('/api/resources',headers=officer,json={'kind':'engineers','id':'E01','unavailable_from':'2026-09-14T02:20:00+08:00','unavailable_to':'2026-09-14T04:30:00+08:00'})
    assert changed.status_code==200
    result=client.post(f"/api/proposals/{p['id']}/commit",headers=officer,json={'expected_version':p['planning_version']})
    assert result.status_code==409
    assert len(client.get('/api/planning-snapshot',headers=officer).json()['committed_allocations'])==2


def test_independent_recheck_blocks_a_tampered_proposal(client,officer):
    approve_pending(client,officer)
    p=client.post('/api/schedule/proposals',headers=officer).json()
    p['allocations'][0]['start']='2026-09-14T01:05:00+08:00'
    with client.app.state.db.connection(write=True) as c:
        c.execute('UPDATE proposals SET payload=? WHERE id=?',(json.dumps(p),p['id']))
    result=client.post(f"/api/proposals/{p['id']}/commit",headers=officer,json={'expected_version':p['planning_version']})
    assert result.status_code==409
    assert len(client.get('/api/planning-snapshot',headers=officer).json()['committed_allocations'])==2


def test_role_header_cannot_upgrade_a_requester(client):
    result=client.post('/api/schedule/proposals',headers={'X-Demo-User':'demo-track','X-Role':'officer'})
    assert result.status_code==403


def test_reset_increments_version_and_removes_proposals(client,officer):
    approve_pending(client,officer)
    client.post('/api/schedule/proposals',headers=officer)
    before=client.get('/api/planning-snapshot',headers=officer).json()['metadata']['planning_version']
    assert client.post('/api/demo/reset',headers=officer).status_code==200
    assert client.get('/api/proposals',headers=officer).json()==[]
    assert client.get('/api/planning-snapshot',headers=officer).json()['metadata']['planning_version']==before+1


def test_invalid_protection_reference_rejected(client,requester,new_request):
    new_request['protected_sectors']=['S04','not-a-sector']
    assert client.post('/api/requests',headers=requester,json=new_request).status_code==422


def test_no_frontend_secret_configuration(client):
    data=client.get('/api/config').json()
    assert data['supabase_publishable_key']==''
    assert 'officer_user_ids' not in data


def test_web_page_and_module_served(client):
    assert client.get('/').status_code==200
    assert client.get('/static/src/app.js').status_code==200
    assert client.get('/api/health').json()['ok'] is True


def test_officer_can_mass_approve_and_unapprove(client,officer):
    approved=approve_pending(client,officer,['R03'])
    assert approved['status']=='approved'
    snapshot=client.get('/api/planning-snapshot',headers=officer).json()
    assert next(r for r in snapshot['requests'] if r['id']=='R03')['status']=='approved'
    result=client.patch('/api/requests/approval',headers=officer,json={'request_ids':['R03'],'approved':False})
    assert result.status_code==200,result.text
    snapshot=client.get('/api/planning-snapshot',headers=officer).json()
    assert next(r for r in snapshot['requests'] if r['id']=='R03')['status']=='submitted'


def test_unlocked_published_job_can_be_reshuffled(client,officer):
    result=client.patch('/api/allocations/locks',headers=officer,json={'request_ids':['R01'],'locked':False})
    assert result.status_code==200,result.text
    snapshot=client.get('/api/planning-snapshot',headers=officer).json()
    assert next(a for a in snapshot['committed_allocations'] if a['request_id']=='R01')['locked'] is False
    proposal=client.post('/api/schedule/proposals',headers=officer,json={})
    assert proposal.status_code==200,proposal.text
    assert {a['request_id'] for a in proposal.json()['allocations']}=={'R01','R02'}


def test_unlocked_published_job_can_be_unscheduled_and_remains_approved(client,officer):
    assert client.patch('/api/allocations/locks',headers=officer,json={'request_ids':['R01'],'locked':False}).status_code==200
    snapshot=client.get('/api/planning-snapshot',headers=officer).json()
    r02=next(a for a in snapshot['committed_allocations'] if a['request_id']=='R02')
    draft={'request_id':'R02','start':r02['start'],'engineer_id':r02['engineer_id'],'locked':True}
    checked=client.post('/api/schedule/check',headers=officer,json={'allocations':[draft]})
    assert checked.status_code==200 and checked.json()['valid'] is True
    proposal=client.post('/api/schedule/manual-proposals',headers=officer,json={'allocations':[draft]})
    assert proposal.status_code==200,proposal.text
    body=proposal.json()
    assert any(change['request_id']=='R01' and change.get('removed') for change in body['changes'])
    committed=client.post(f"/api/proposals/{body['id']}/commit",headers=officer,json={'expected_version':body['planning_version']})
    assert committed.status_code==200,committed.text
    after=client.get('/api/planning-snapshot',headers=officer).json()
    assert 'R01' not in {a['request_id'] for a in after['committed_allocations']}
    assert next(r for r in after['requests'] if r['id']=='R01')['status']=='approved'
