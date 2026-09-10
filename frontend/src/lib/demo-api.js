// Temporary UI adapter. All mutations stay in this browser; no solver is called.
const KEY = 'railplan-ui-demo-v2';
const clone = value => structuredClone(value);
const users = [
  {id:'demo-officer',name:'Planning officer',role:'officer'},
  {id:'demo-track',name:'Track team',role:'requester'},
  {id:'demo-signals',name:'Systems team',role:'requester'}
];
let loading;
async function seed() {
  const response = await fetch('/static/demo-snapshot.json?v=2');
  if (!response.ok) throw new Error('Cannot load the UI demo fixture.');
  return {snapshot:await response.json(),proposals:[],audit:[]};
}
async function load() {
  if (!loading) loading = (async () => {
    try { const saved=JSON.parse(localStorage.getItem(KEY)); if(saved?.snapshot?.metadata?.ui_demo)return saved; } catch (_) { /* Restore a broken browser save from the fixture. */ }
    return seed();
  })().catch(error => { loading=null; throw error; });
  return loading;
}
function fail(message,status=400) { const error=new Error(message);error.status=status;throw error; }
function request(snapshot,id) { return snapshot.requests.find(r=>r.id===id) || fail(`Unknown request ${id}`); }
function allocation(snapshot,draft) {
  const r=request(snapshot,draft.request_id);
  return {...draft,end:new Date(Date.parse(draft.start)+r.phases.reduce((n,p)=>n+p.duration_minutes,0)*60000).toISOString(),
    engineer_id:draft.engineer_id||r.preferred_engineer||r.eligible_engineers[0],equipment_ids:[...r.required_equipment_ids],locked:!!draft.locked};
}
// Visual overlap hints only. These do not implement the planning model.
function issues(snapshot,plan) {
  const result=[];
  for(let i=0;i<plan.length;i++)for(let j=i+1;j<plan.length;j++){
    const a=plan[i],b=plan[j];
    if(Date.parse(a.start)>=Date.parse(b.end)||Date.parse(b.start)>=Date.parse(a.end))continue;
    const ra=request(snapshot,a.request_id),rb=request(snapshot,b.request_id);
    if(ra.protected_sectors.some(s=>rb.protected_sectors.includes(s))||a.engineer_id===b.engineer_id||a.equipment_ids.some(q=>b.equipment_ids.includes(q)))
      result.push({code:'DEMO_OVERLAP',request_ids:[a.request_id,b.request_id],message:'Demo overlap: shared sector, engineer or equipment.',severity:'error'});
  }
  return result;
}
export async function demoApi(path,{body={}}={},identity) {
  const user=users.find(u=>u.id===identity);
  if(!user)fail('Choose a local demo profile',401);
  const db=await load(),s=db.snapshot;
  const save=(action,bump=true)=>{
    if(bump)s.metadata.planning_version++;
    db.audit.unshift({actor:user.id,action,detail:'Browser demo',created_at:new Date().toISOString()});
    localStorage.setItem(KEY,JSON.stringify(db));
    return {ok:true,planning_version:s.metadata.planning_version};
  };
  if(path==='/me')return clone(user);
  if(path==='/planning-snapshot'){
    const result=clone(s);
    if(user.role==='officer' && db.draft)result.demo_draft=clone(db.draft);
    result.occupancy=s.committed_allocations.map(a=>({...a,protected_sectors:request(s,a.request_id).protected_sectors,label:user.role==='officer'||request(s,a.request_id).owner_id===user.id?a.request_id:'Reserved'}));
    if(user.role!=='officer'){
      result.requests=result.requests.filter(r=>r.owner_id===user.id);
      result.committed_allocations=result.committed_allocations.filter(a=>result.requests.some(r=>r.id===a.request_id));
    }
    return result;
  }
  if(path==='/requests'){
    if(user.role!=='requester')fail('Choose a requester profile',403);
    const id=`R${String(Math.max(0,...s.requests.map(r=>Number(r.id.slice(1))||0))+1).padStart(2,'0')}`;
    s.requests.push({...clone(body),id,status:'submitted',owner_id:user.id,power_zone:s.sectors.find(x=>x.id===body.work_sector)?.power_zone,
      eligible_engineers:s.engineers.filter(e=>e.skills.includes(body.required_skill)).map(e=>e.id)});
    save('request_submitted');return {id};
  }
  if(/^\/requests\/[^/]+\/cancel$/.test(path)){
    const r=request(s,decodeURIComponent(path.split('/')[2]));
    if(r.owner_id!==user.id||r.status==='scheduled')fail('This request cannot be withdrawn',403);
    r.status='cancelled';return save('request_withdrawn');
  }
  if(user.role!=='officer')fail('Planning officer required',403);
  if(path==='/audit')return clone(db.audit);
  if(path==='/proposals')return clone(db.proposals);
  if(path==='/conflicts/check')return {issues:issues(s,s.committed_allocations),planning_version:s.metadata.planning_version};
  if(path==='/schedule/check'){
    const plan=body.allocations.map(a=>allocation(s,a)),found=issues(s,plan);
    db.draft=clone(plan);localStorage.setItem(KEY,JSON.stringify(db));
    return {allocations:plan,issues:found,valid:!found.length,planning_version:s.metadata.planning_version};
  }
  if(path==='/requests/approval'){
    for(const id of body.request_ids){const r=request(s,id);if(r.status!=='scheduled')r.status=body.approved?'approved':'submitted';}
    return save('requests_updated');
  }
  if(path==='/allocations/locks'){
    s.committed_allocations.forEach(a=>{if(body.request_ids.includes(a.request_id))a.locked=body.locked;});
    return save('locks_updated');
  }
  if(path==='/schedule/proposals'||path==='/schedule/manual-proposals'){
    let plan;
    if(path==='/schedule/manual-proposals')plan=body.allocations.map(a=>allocation(s,a));
    else {
      const fixed=new Map([...s.committed_allocations.filter(a=>a.locked),...(body.locked_allocations||[])].map(a=>[a.request_id,a]));
      plan=s.requests.filter(r=>['approved','scheduled'].includes(r.status)).map(r=>allocation(s,fixed.get(r.id)||s.demo_schedule.find(a=>a.request_id===r.id)||{request_id:r.id,start:r.preferred_start}));
    }
    const found=issues(s,plan);
    const p={id:`P-${crypto.randomUUID()}`,status:'DEMO',engine:'ui_mock',status_workflow:'draft',planning_version:s.metadata.planning_version,
      allocations:plan,issues:found,message:'Preset demo schedule loaded. Only visual overlaps are checked.',elapsed_seconds:0,
      changes:plan.map(a=>({...a,title:request(s,a.request_id).title,preferred_start:request(s,a.request_id).preferred_start,explanation:'Preset UI demo placement.'}))};
    db.proposals.unshift(p);save('demo_proposal',false);return clone(p);
  }
  if(/^\/proposals\/[^/]+\/commit$/.test(path)){
    const p=db.proposals.find(p=>p.id===path.split('/')[2]);
    if(!p||p.status_workflow!=='draft'||body.expected_version!==s.metadata.planning_version||p.planning_version!==s.metadata.planning_version)fail('Refresh and create a new demo proposal.',409);
    s.committed_allocations=clone(p.allocations);
    delete db.draft;
    s.requests.forEach(r=>{if(p.allocations.some(a=>a.request_id===r.id))r.status='scheduled';else if(r.status==='scheduled')r.status='approved';});
    p.status_workflow='committed';return save('demo_plan_published');
  }
  if(path==='/resources'){
    const resource=s[body.kind]?.find(r=>r.id===body.id);if(!resource)fail('Unknown resource');
    if(body.serviceable!==undefined)resource.serviceable=body.serviceable;
    if(body.unavailable_from)(resource.unavailable??=[]).push({start:body.unavailable_from,end:body.unavailable_to});
    return save('resource_updated');
  }
  if(path==='/demo/reset'){
    const fresh=await seed();fresh.snapshot.metadata.planning_version=s.metadata.planning_version+1;
    loading=Promise.resolve(fresh);localStorage.setItem(KEY,JSON.stringify(fresh));return {ok:true};
  }
  fail(`No demo handler for ${path}`);
}
