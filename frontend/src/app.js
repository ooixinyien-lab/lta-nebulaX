import { loadConfig, chooseDemo, signIn, signOut, canRestoreDemo } from './auth/session.js?v=20260910-demo2';
import { api } from './lib/api.js?v=20260910-demo2';
import { h, badge, nextDate } from './lib/format.js';
import { loginPage } from './pages/login.js';
import { requesterPage, newRequestPage } from './pages/requester.js';
import { officerPage, resourcesPage } from './pages/officer.js?v=20260910-demo2';
import { networkMap } from './components/timeline.js?v=20260915-network-map-refinements';

const state = { config:null, user:null, snapshot:null, issues:[], proposal:null, audit:[], date:'2026-09-14', weekStart:'2026-09-14', weekDirection:0, page:'', viewMode:'requested', manualPlan:null, manualVersion:null, selectedSchedule:new Set(), selectedPool:new Set(), planHistoryPast:[], planHistoryFuture:[], navExpanded:false, busy:false, networkMapSelection:null };
const root = document.getElementById('app');

function duration(request) { return request.phases.reduce((sum,p)=>sum+Number(p.duration_minutes),0); }
function endAt(start, minutes) { return new Date(new Date(start).getTime()+minutes*60000).toISOString(); }
function allocationDate(iso) { const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Singapore',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(iso)).map(p=>[p.type,p.value]));return `${parts.year}-${parts.month}-${parts.day}`; }
function addDays(date,days){const value=new Date(`${date}T00:00:00Z`);value.setUTCDate(value.getUTCDate()+days);return value.toISOString().slice(0,10);}
function mondayOf(date){const value=new Date(`${date}T00:00:00Z`),day=value.getUTCDay()||7;value.setUTCDate(value.getUTCDate()-day+1);return value.toISOString().slice(0,10);}
function conflictCount(issues=state.issues){const ids=new Set(issues.flatMap(issue=>issue.request_ids||[]));return ids.size?Math.max(1,ids.size-1):issues.length;}
function draftPayload(allocations=state.manualPlan||[]) {
  return allocations.map(a=>({request_id:a.request_id,start:a.start,engineer_id:a.engineer_id,locked:!!a.locked}));
}
const clonePlan=(plan=state.manualPlan||[])=>plan.map(a=>({...a,equipment_ids:[...(a.equipment_ids||[])]}));
const planKey=plan=>JSON.stringify(draftPayload(plan).sort((a,b)=>a.request_id.localeCompare(b.request_id)));
const historyEntry=(plan=state.manualPlan||[],date=state.date,weekStart=state.weekStart)=>({plan:clonePlan(plan),date,weekStart});
function recordPlanHistory(previousPlan,previousDate=state.date,previousWeekStart=state.weekStart) {
  if(planKey(previousPlan)===planKey(state.manualPlan||[]))return;
  state.planHistoryPast.push(historyEntry(previousPlan,previousDate,previousWeekStart));
  if(state.planHistoryPast.length>50)state.planHistoryPast.shift();
  state.planHistoryFuture=[];
}
function clearPlanHistory(){state.planHistoryPast=[];state.planHistoryFuture=[];}
function seedManualPlan(force=false) {
  const version=state.snapshot?.metadata.planning_version;
  if (!force && state.manualPlan && state.manualVersion===version) return;
  state.manualPlan=(state.snapshot.demo_draft||state.snapshot.committed_allocations).map(a=>({...a,locked:!!a.locked}));
  state.manualVersion=version;
}
async function checkManualPlan() {
  const result=await api('/schedule/check',{method:'POST',body:{allocations:draftPayload()}});
  state.issues=result.issues;
  state.manualPlan=result.allocations;
  state.manualVersion=result.planning_version;
  return result;
}
async function applyPlanHistory(targetPlan) {
  const target=clonePlan(targetPlan),targetById=new Map(target.map(a=>[a.request_id,a]));
  const lock=[],unlock=[];
  for(const committed of state.snapshot.committed_allocations){
    const next=targetById.get(committed.request_id);if(!next||next.locked===committed.locked)continue;
    (next.locked?lock:unlock).push(committed.request_id);
  }
  for(const [ids,locked] of [[lock,true],[unlock,false]])if(ids.length){
    const result=await api('/allocations/locks',{method:'PATCH',body:{request_ids:ids,locked}});
    state.snapshot.metadata.planning_version=result.planning_version;
    state.snapshot.committed_allocations.forEach(a=>{if(ids.includes(a.request_id))a.locked=locked;});
  }
  state.manualPlan=target;state.proposal=null;state.selectedSchedule.clear();
  const checked=await checkManualPlan();
  if(checked.valid)state.proposal=await api('/schedule/manual-proposals',{method:'POST',body:{allocations:draftPayload()}});
  return checked;
}

let noticeTimer=null;
function notice(message, error=false) {
  const target=document.getElementById('notice');
  if (!target)return;
  target.innerHTML=`<div class="notice ${error?'warning':'success'}" role="status">${h(message)}</div>`;
  const week=document.querySelector('.week-overview');
  if(week){target.classList.add('planner-notice');target.style.top=`${week.offsetTop+12}px`;target.style.left=`${week.offsetLeft+18}px`;target.style.right=`${Math.max(18,target.parentElement.clientWidth-week.offsetLeft-week.offsetWidth+18)}px`;}
  clearTimeout(noticeTimer);
  noticeTimer=setTimeout(()=>{target.innerHTML='';target.classList.remove('planner-notice');target.removeAttribute('style');},10000);
}
async function reload() {
  state.snapshot=await api('/planning-snapshot');
  if (!state.snapshot.engineering_windows.some(w=>w.date===state.date)) state.date=state.snapshot.engineering_windows[0].date;
  if (state.user.role==='officer') {
    const [checks, proposals, audit]=await Promise.all([api('/conflicts/check',{method:'POST'}),api('/proposals'),api('/audit')]);
    state.issues=checks.issues; state.audit=audit;
    if (!state.proposal || state.proposal.status_workflow==='committed') state.proposal=proposals.find(p=>p.status_workflow==='draft')||null;
    seedManualPlan();
  }
}
async function enter() {
  state.user=await api('/me');
  state.page=state.user.role==='officer'?'planner':'my-requests';
  state.viewMode=state.user.role==='officer'?'requested':'booked';
  state.manualPlan=null;state.manualVersion=null;state.selectedSchedule.clear();state.selectedPool.clear();
  state.proposal=null;state.issues=[];state.audit=[];
  state.networkMapSelection=null;
  state.weekStart=mondayOf(state.date);
  clearPlanHistory();
  await reload();
}
function render() {
  if (!state.user) { root.innerHTML=loginPage(state.config); return; }
  const officer=state.user.role==='officer';
  const titles={'planner':['Engineering schedule',''],'network-map':['Network map','Inspect corridor topology, possessions and movement.'],'my-requests':['Your maintenance requests','Submit work packages and track approved allocations.'],'new-request':['Request track time','Tell the planner what you need, not just when you want it.'],'resources':['Resources & activity','Availability changes are planning changes.']};
  const [title,subtitle]=titles[state.page]||titles[officer?'planner':'my-requests'];
  const dates=[...new Set(state.snapshot.engineering_windows.map(w=>w.date))];
  const nav=officer?[['planner','Planning workspace','<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3v3M17 3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v13H4V6a1 1 0 0 1 1-1Zm3 8h3v3H8Z"/></svg>'],['network-map','Network map','<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16M7 4v4M17 10v4M10 16v4"/></svg>'],['resources','Resources & activity','<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/></svg>']]:[['my-requests','My requests','<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14v16H5zM8 9h8M8 13h8M8 17h5"/></svg>'],['network-map','Network map','<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16M7 4v4M17 10v4M10 16v4"/></svg>'],['new-request','New request','<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>']];
  let content=state.page==='network-map'?networkMap(state):state.page==='new-request'?newRequestPage(state.snapshot):state.page==='resources'?resourcesPage(state):officer?officerPage(state):requesterPage(state);
  const showDatePicker=!(officer&&state.page==='planner');
  const planner=officer&&state.page==='planner';
  const conflictDetails=state.issues.map(i=>`<article><b>${h(i.code.replaceAll('_',' '))}</b><span>${i.request_ids.map(h).join(' / ')}</span><p>${h(i.message)}</p></article>`).join('');
  const visibleConflictCount=conflictCount();
  const plannerActions=planner&&state.issues.length?`<span class="conflict-indicator" tabindex="0" aria-label="${visibleConflictCount} schedule conflicts">!<span class="conflict-popover"><strong>${visibleConflictCount} conflict${visibleConflictCount===1?'':'s'}</strong>${conflictDetails}</span></span>`:'';
  root.innerHTML=`<div class="app-shell"><aside class="sidebar ${state.navExpanded?'nav-expanded':''}"><a class="brand" href="#"><span class="brand-mark">N</span><span class="brand-label">NebulaX</span></a><div class="sidebar-kicker">MAINTENANCE WORKSPACE</div><nav>${nav.map(([id,label,icon])=>`<button class="nav-item ${state.page===id?'active':''}" data-nav="${id}" title="${h(label)}"><span class="nav-icon">${icon}</span><span class="nav-label">${h(label)}</span></button>`).join('')}</nav><div class="sidebar-note"><span class="status-dot"></span><strong>Fictional corridor</strong><p>Planning support only.<br>No live track access.</p></div><div class="sidebar-user"><div class="avatar">${officer?'O':'R'}</div><div class="user-copy"><strong>${h(state.user.name)}</strong><small>${officer?'Planning officer':'Requester'}</small></div><button data-action="logout" title="Sign out" aria-label="Sign out">&rarr;</button></div></aside><div class="app-main"><header class="topbar"><span>NEBULAX <span class="crumb">/ Canonical planner</span></span><div>${badge(state.config.ui_demo?'UI DEMO  /  MOCK SCHEDULE':'SYNTHETIC DATA','neutral')}${badge(state.config.auth_mode==='demo'?'LOCAL DEMO':'SUPABASE AUTH',state.config.auth_mode==='demo'?'warning':'success')}</div></header><main class="content ${planner?'planner-content':''}"><div class="page-heading"><div><div class="eyebrow dark">${officer?'OFFICER CONSOLE':'REQUESTER PORTAL'}</div><h1>${title}</h1>${subtitle?`<p>${subtitle}</p>`:''}</div><div class="page-actions">${showDatePicker?`<select id="date-picker" aria-label="Planning date">${dates.map(d=>`<option value="${d}" ${state.date===d?'selected':''}>${d}</option>`).join('')}</select>`:''}<button class="button secondary" data-action="refresh" aria-label="Refresh">&#8635;</button>${plannerActions}</div></div><div id="notice" role="alert"></div>${content}<footer class="app-footer"><span>Revision ${state.snapshot.metadata.planning_version} &middot; ${state.config.ui_demo?'Preset schedule  /  browser-saved demo  /  overlap hints only':state.config.solver_engine==='cp_sat'?'CP-SAT configured':'Tiny-demo search / not CP-SAT'}</span><span>All constraints are prototype assumptions.</span>${officer&&state.config.auth_mode==='demo'?'<button class="text-button" data-action="reset">Reset synthetic demo</button>':''}</footer></main></div></div>`;
  state.weekDirection=0;
  if(state.page!=='network-map')requestAnimationFrame(drawScheduleLinks);
  if (state.page==='new-request') updateRequestRequirements();
}
function drawScheduleLinks() {
  const timeline=document.querySelector('.editable-timeline .timeline');if(!timeline)return;
  timeline.querySelector('.timeline-links')?.remove();
  const timelineRect=timeline.getBoundingClientRect(),protections=[...timeline.querySelectorAll('.time-block.protection[data-job-part]')];
  if(!protections.length)return;
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('timeline-links');svg.setAttribute('aria-hidden','true');
  protections.forEach(part=>{const id=part.dataset.jobPart,job=[...timeline.querySelectorAll('.time-block[data-job-part]')].find(node=>node.dataset.jobPart===id&&!node.classList.contains('protection'));if(!job)return;const a=part.getBoundingClientRect(),b=job.getBoundingClientRect(),path=document.createElementNS('http://www.w3.org/2000/svg','path'),x1=a.left+a.width/2-timelineRect.left,y1=a.bottom-timelineRect.top,x2=b.left+b.width/2-timelineRect.left,y2=b.top-timelineRect.top,mid=(y1+y2)/2;path.dataset.jobLink=id;path.classList.add(job.classList.contains('locked')?'locked':'unlocked');path.setAttribute('d',`M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`);svg.append(path);});
  if(svg.childNodes.length)timeline.prepend(svg);
}
function updateRequestRequirements() {
  const form=document.getElementById('request-form'); if (!form) return;
  const entry=(state.snapshot.job_catalogue||[]).find(item=>item.work_type===form.elements.work_type?.value);
  const skill=entry?Object.keys(entry.required_engineer_roles)[0]:form.elements.required_skill.value;
  if(entry){form.elements.required_skill.value=skill;form.elements.power_requirement.value=entry.power_requirement;form.elements.technicians_required.value=entry.pooled_resources.TECH||0;}
  document.getElementById('engineer-select').innerHTML='<option value="">No preference</option>'+state.snapshot.engineers.filter(e=>e.skills.includes(skill)).map(e=>`<option value="${h(e.id)}">${h(e.id)} - ${h(e.name)}</option>`).join('');
}
async function run(task) {
  if (state.busy) return;
  state.busy=true;
  document.body.classList.add('is-busy');
  document.querySelectorAll('button').forEach(b=>b.disabled=true);
  try { const message=await task(); render(); if(message) notice(message); }
  catch(error) { if(error.status===401) { await signOut(); state.user=null; state.networkMapSelection=null; state.issues=[]; state.audit=[]; } render(); notice(error.message,true); }
  finally { state.busy=false; document.body.classList.remove('is-busy'); }
}

function selectNetworkMapTarget(target) {
  const type=target.hasAttribute('data-map-sector')?'sector':'station';
  state.networkMapSelection={type,id:target.getAttribute(`data-map-${type}`)};
  render();
}

document.addEventListener('click',event=>{
  const mapTarget=event.target.closest?.('[data-map-sector],[data-map-station]');
  if(mapTarget) { if(state.busy)return; selectNetworkMapTarget(mapTarget); return; }
  const el=event.target.closest('button'); if(!el||state.busy) return;
  if(el.dataset.demo) return run(async()=>{ chooseDemo(el.dataset.demo); await enter(); });
  if(el.dataset.nav) { if(state.page===el.dataset.nav)return; if(state.page==='network-map'||el.dataset.nav==='network-map')state.networkMapSelection=null;state.page=el.dataset.nav;render();return; }
  if(el.dataset.weekShift){const shift=Number(el.dataset.weekShift);state.weekDirection=Math.sign(shift);state.weekStart=addDays(state.weekStart,shift);state.date=state.weekStart;render();return;}
  if(el.dataset.scheduleDate) { state.date=el.dataset.scheduleDate;state.weekStart=mondayOf(state.date);render();return; }
  if(el.dataset.view) { state.viewMode=el.dataset.view; render(); return; }
  if(el.dataset.action==='select-all-schedule'){state.selectedSchedule=new Set((state.manualPlan||[]).filter(a=>allocationDate(a.start)===state.date).map(a=>a.request_id));render();return;}
  if(el.dataset.action==='clear-schedule-selection'){state.selectedSchedule.clear();render();return;}
  if(el.dataset.action==='undo-plan'||el.dataset.action==='redo-plan')return run(async()=>{const undo=el.dataset.action==='undo-plan',source=undo?state.planHistoryPast:state.planHistoryFuture,destination=undo?state.planHistoryFuture:state.planHistoryPast;if(!source.length)return;const current=historyEntry(),target=source.pop();destination.push(current);try{state.date=target.date;state.weekStart=target.weekStart;const checked=await applyPlanHistory(target.plan),count=conflictCount(checked.issues);return `${undo?'Undo':'Redo'} complete${checked.valid?'.':` with ${count} conflict${count===1?'':'s'}.`}`;}catch(error){destination.pop();source.push(target);state.manualPlan=current.plan;state.date=current.date;state.weekStart=current.weekStart;throw error;}});
  if(el.dataset.action==='batch-lock'||el.dataset.action==='batch-unlock')return run(async()=>{const previousPlan=clonePlan(),locked=el.dataset.action==='batch-lock',ids=[...state.selectedSchedule],committed=new Set(state.snapshot.committed_allocations.map(a=>a.request_id)),published=ids.filter(id=>committed.has(id));let version=state.snapshot.metadata.planning_version;if(published.length){const result=await api('/allocations/locks',{method:'PATCH',body:{request_ids:published,locked}});version=result.planning_version;state.snapshot.committed_allocations.forEach(a=>{if(published.includes(a.request_id))a.locked=locked;});}state.manualPlan.forEach(a=>{if(ids.includes(a.request_id))a.locked=locked;});state.manualVersion=version;state.snapshot.metadata.planning_version=version;state.proposal=null;state.selectedSchedule.clear();const checked=await checkManualPlan();const allLocked=state.manualPlan.every(a=>a.locked);if(locked&&checked.valid&&allLocked)state.proposal=await api('/schedule/manual-proposals',{method:'POST',body:{allocations:draftPayload()}});recordPlanHistory(previousPlan);return `${ids.length} job${ids.length===1?'':'s'} ${locked?'locked':'unlocked'}.`;});
  if(el.dataset.action==='select-all-pool'){const scheduled=new Set((state.manualPlan||[]).map(a=>a.request_id));state.selectedPool=new Set(state.snapshot.requests.filter(r=>r.status==='submitted'||(['approved','scheduled'].includes(r.status)&&!scheduled.has(r.id))).map(r=>r.id));render();return;}
  if(el.dataset.action==='clear-pool-selection'){state.selectedPool.clear();render();return;}
  if(el.dataset.action==='approve-selected'||el.dataset.action==='unapprove-selected')return run(async()=>{const approved=el.dataset.action==='approve-selected',ids=[...state.selectedPool];await api('/requests/approval',{method:'PATCH',body:{request_ids:ids,approved}});state.selectedPool.clear();state.selectedSchedule.clear();state.proposal=null;state.manualPlan=null;clearPlanHistory();await reload();return `${ids.length} request${ids.length===1?'':'s'} ${approved?'approved and ready to add':'returned to requested'}.`;});
  if(el.dataset.action==='add-to-schedule')return run(async()=>{const previousPlan=clonePlan(),scheduled=new Set(state.manualPlan.map(a=>a.request_id)),selected=state.selectedPool.size?state.selectedPool:null,candidates=state.snapshot.requests.filter(r=>['approved','scheduled'].includes(r.status)&&!scheduled.has(r.id)&&(!selected||selected.has(r.id)));if(!candidates.length)return 'Select or approve at least one request first.';for(const request of candidates){const initialStart=request.preferred_start||request.earliest_start,allocation={request_id:request.id,start:initialStart,end:endAt(initialStart,duration(request)),engineer_id:request.preferred_engineer||request.eligible_engineers[0],equipment_ids:[...request.required_equipment_ids],locked:false};state.manualPlan.push(allocation);const best=bestStartOnDate(request.id,allocationDate(allocation.start));allocation.start=best;allocation.end=endAt(best,duration(request));}state.selectedPool.clear();state.proposal=null;const result=await checkManualPlan();recordPlanHistory(previousPlan);const count=conflictCount(result.issues);return `${candidates.length} approved job${candidates.length===1?'':'s'} added without moving existing work${count?`; ${count} conflict${count===1?'':'s'} need attention`:''}.`;});
  if(el.dataset.cancel) return run(async()=>{ if(!confirm('Withdraw this unbooked request?')) return; await api(`/requests/${encodeURIComponent(el.dataset.cancel)}/cancel`,{method:'POST'}); await reload(); return 'Request withdrawn.'; });
  if(el.dataset.equipment) return run(async()=>{ await api('/resources',{method:'PATCH',body:{kind:'equipment',id:el.dataset.equipment,serviceable:el.dataset.serviceable==='true'}}); await reload(); return 'Equipment updated. Previous proposals are now stale.'; });
  if(el.dataset.action==='logout') return run(async()=>{ await signOut(); state.user=null;state.snapshot=null;state.proposal=null;state.networkMapSelection=null;state.issues=[];state.audit=[]; });
  if(el.dataset.action==='refresh') return run(async()=>{ state.manualPlan=null;clearPlanHistory();await reload();return 'Latest planning data loaded.'; });
  if(el.dataset.action==='save-demo') return run(async()=>{const p=await api('/schedule/manual-proposals',{method:'POST',body:{allocations:draftPayload()}});await api(`/proposals/${p.id}/commit`,{method:'POST',body:{expected_version:p.planning_version}});state.proposal=null;state.manualPlan=null;await reload();return 'Demo schedule saved in this browser.';});
  if(el.dataset.action==='generate') return run(async()=>{const previous=clonePlan();const p=await api('/schedule/proposals',{method:'POST',body:{locked_allocations:draftPayload().filter(a=>a.locked)}});state.manualPlan=p.allocations;state.manualVersion=p.planning_version;state.proposal=p;state.issues=p.validation?.issues||p.issues||[];recordPlanHistory(previous);return p.mode==='recovery'?`Best valid partial schedule generated; ${p.deferred_requests.length} request${p.deferred_requests.length===1?'':'s'} deferred.`:'Complete solver proposal generated.';});
  if(el.dataset.action==='commit') return run(async()=>{ if(!confirm('Approve and publish this synthetic plan? This does not authorise real railway access.')) return; const p=state.proposal; await api(`/proposals/${p.id}/commit`,{method:'POST',body:{expected_version:p.planning_version}});p.status_workflow='committed';state.viewMode='booked';await reload();return 'Plan published. Requesters can refresh to see their bookings.'; });
  if(el.dataset.action==='absence') return run(async()=>{ const date=state.snapshot.engineering_windows[0].date;await api('/resources',{method:'PATCH',body:{kind:'engineers',id:'E01',unavailable_from:`${date}T02:20:00+08:00`,unavailable_to:`${date}T04:30:00+08:00`}});await reload();return 'E01 is unavailable after 02:20 on the first demo night. Recalculate the pending plan.'; });
  if(el.dataset.action==='reset') return run(async()=>{ if(!confirm('Delete demo edits and proposals, and restore the fictional seed?'))return;await api('/demo/reset',{method:'POST'});state.proposal=null;state.manualPlan=null;state.viewMode='requested';clearPlanHistory();await reload();return 'Synthetic fixture restored.'; });
});
document.addEventListener('keydown',event=>{
  if(event.key!=='Enter'&&event.key!==' ')return;
  const mapTarget=event.target.closest?.('[data-map-sector],[data-map-station]');
  if(!mapTarget)return;
  event.preventDefault();
  selectNetworkMapTarget(mapTarget);
});

let pointerDrag=null;
async function unscheduleManualJob(id) {
  const allocation=state.manualPlan?.find(a=>a.request_id===id);if(!allocation||allocation.locked)return;
  const previousPlan=state.manualPlan.map(a=>({...a})),previousIssues=state.issues,previousProposal=state.proposal;
  state.manualPlan=state.manualPlan.filter(a=>a.request_id!==id);state.selectedSchedule.delete(id);state.proposal=null;render();
  return run(async()=>{try{const checked=await checkManualPlan();if(!checked.valid){recordPlanHistory(previousPlan);const warning=new Error(`${id} is unscheduled, but ${checked.issues.length} conflict${checked.issues.length===1?'':'s'} need attention.`);warning.keepMove=true;throw warning;}state.proposal=await api('/schedule/manual-proposals',{method:'POST',body:{allocations:draftPayload()}});recordPlanHistory(previousPlan);return `${id} returned to the approved request pool.`;}catch(error){if(!error.keepMove){state.manualPlan=previousPlan;state.issues=previousIssues;state.proposal=previousProposal;}throw error;}});
}
async function moveManualJob(id,lane,clientX) {
  const allocation=state.manualPlan?.find(a=>a.request_id===id);if(!allocation||allocation.locked)return;
  const request=state.snapshot.requests.find(r=>r.id===id),rect=lane.getBoundingClientRect(),windowStart=new Date(lane.dataset.windowStart).getTime(),windowEnd=new Date(lane.dataset.windowEnd).getTime();
  const totalMinutes=(windowEnd-windowStart)/60000,jobMinutes=duration(request),step=state.snapshot.planning_rules.start_grid_minutes;
  let minutes=Math.round(((clientX-rect.left)/rect.width*totalMinutes)/step)*step;minutes=Math.max(0,Math.min(totalMinutes-jobMinutes,minutes));
  const nextStart=new Date(windowStart+minutes*60000).toISOString();
  if(new Date(nextStart).getTime()===new Date(allocation.start).getTime())return;
  const previousPlan=clonePlan(),previous={...allocation},previousIssues=state.issues;
  allocation.start=nextStart;allocation.end=endAt(allocation.start,jobMinutes);state.proposal=null;
  render();
  return run(async()=>{try{const result=await checkManualPlan();recordPlanHistory(previousPlan);if(!result.valid){const count=conflictCount(result.issues),warning=new Error(`${id} moved. ${count} conflict${count===1?'':'s'} need attention.`);warning.keepMove=true;throw warning;}return `${id} moved. The plan is conflict-free.`;}catch(error){if(!error.keepMove){state.manualPlan=state.manualPlan.map(a=>a.request_id===id?previous:a);state.issues=previousIssues;}throw error;}});
}
function bestStartOnDate(id,date){
  const allocation=state.manualPlan.find(a=>a.request_id===id),request=state.snapshot.requests.find(r=>r.id===id),step=state.snapshot.planning_rules.start_grid_minutes,minutes=duration(request),start=new Date(`${date}T01:00:00+08:00`).getTime(),finish=new Date(`${date}T04:30:00+08:00`).getTime(),others=state.manualPlan.filter(a=>a.request_id!==id),requests=Object.fromEntries(state.snapshot.requests.map(r=>[r.id,r]));
  const preferred=new Date(request.preferred_start),preferredMinute=preferred.getHours()*60+preferred.getMinutes();let best=null;
  for(let tick=start;tick+minutes*60000<=finish;tick+=step*60000){const end=tick+minutes*60000,conflicting=new Set();for(const other of others){const otherStart=new Date(other.start).getTime(),otherEnd=new Date(other.end).getTime();if(tick>=otherEnd||end<=otherStart)continue;const otherRequest=requests[other.request_id],sharesSector=request.protected_sectors.some(sector=>otherRequest.protected_sectors.includes(sector));if(sharesSector||allocation.engineer_id===other.engineer_id||allocation.equipment_ids.some(q=>other.equipment_ids.includes(q)))conflicting.add(other.request_id);}const local=new Date(tick),minute=local.getHours()*60+local.getMinutes(),score=conflicting.size*100000+Math.abs(minute-preferredMinute);if(!best||score<best.score)best={tick,score};}
  return new Date(best.tick).toISOString();
}
async function moveManualJobToDate(id,date){
  const allocation=state.manualPlan?.find(a=>a.request_id===id);if(!allocation||allocation.locked)return;
  const previousPlan=clonePlan(),previousDate=state.date,previousWeekStart=state.weekStart,previousIssues=state.issues,previous={...allocation},nextStart=bestStartOnDate(id,date);if(new Date(nextStart).getTime()===new Date(allocation.start).getTime())return;
  allocation.start=nextStart;allocation.end=endAt(nextStart,duration(state.snapshot.requests.find(r=>r.id===id)));state.date=date;state.weekStart=mondayOf(date);state.proposal=null;render();
  return run(async()=>{try{const result=await checkManualPlan();recordPlanHistory(previousPlan,previousDate,previousWeekStart);if(!result.valid){const count=conflictCount(result.issues),warning=new Error(`${id} moved to ${date}. ${count} conflict${count===1?'':'s'} need attention.`);warning.keepMove=true;throw warning;}return `${id} moved to the best available time on ${date}.`;}catch(error){if(!error.keepMove){state.manualPlan=state.manualPlan.map(a=>a.request_id===id?previous:a);state.date=previousDate;state.weekStart=previousWeekStart;state.issues=previousIssues;}throw error;}});
}
document.addEventListener('pointerdown',event=>{
  if(event.target.closest('input,button,label'))return;
  const block=event.target.closest('[data-drag-job]');if(!block||state.busy)return;
  const id=block.dataset.dragJob,blocks=[...document.querySelectorAll('[data-job-part]')].filter(node=>node.dataset.jobPart===id),links=[...document.querySelectorAll('.timeline-links path')].filter(node=>node.dataset.jobLink===id);
  const mask=document.createElement('div');mask.className='drag-mask';document.body.append(mask);document.body.classList.add('is-schedule-dragging');const overlay=document.createElement('div');overlay.className='drag-overlay';
  const rects=blocks.map(node=>node.getBoundingClientRect());blocks.forEach((node,index)=>{const rect=rects[index],ghost=node.cloneNode(true);ghost.classList.add('drag-ghost');ghost.style.cssText=`left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;height:${rect.height}px`;overlay.append(ghost);node.classList.add('drag-source');});
  if(rects.length>1){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),path=document.createElementNS('http://www.w3.org/2000/svg','path'),a=rects[0],b=rects.at(-1),x1=a.left+a.width/2,y1=a.bottom,x2=b.left+b.width/2,y2=b.top,mid=(y1+y2)/2;svg.classList.add('drag-link-overlay');path.classList.add(block.classList.contains('locked')?'locked':'unlocked');path.setAttribute('d',`M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`);svg.append(path);overlay.append(svg);}
  document.body.append(overlay);pointerDrag={id,block,blocks,links,overlay,mask,startX:event.clientX,startY:event.clientY,offsetX:event.clientX-block.getBoundingClientRect().left,weekHover:null,weekTimer:null};block.setPointerCapture?.(event.pointerId);event.preventDefault();
});
document.addEventListener('pointermove',event=>{
  if(!pointerDrag)return;const dx=event.clientX-pointerDrag.startX,dy=event.clientY-pointerDrag.startY,elements=document.elementsFromPoint(event.clientX,event.clientY);pointerDrag.overlay.style.transform=`translate(${dx}px,${dy}px)`;
  const pool=elements.find(node=>node.closest?.('[data-pool-drop]')),day=elements.map(node=>node.closest?.('[data-week-drop-date]')).find(Boolean),edge=elements.map(node=>node.closest?.('[data-week-shift]')).find(Boolean);document.querySelector('[data-pool-drop]')?.classList.toggle('drag-over',!!pool);document.querySelectorAll('[data-week-drop-date]').forEach(node=>node.classList.toggle('drag-over',node===day));
  const hover=edge?.dataset.weekShift||null;if(hover!==pointerDrag.weekHover){clearTimeout(pointerDrag.weekTimer);pointerDrag.weekHover=hover;if(hover)pointerDrag.weekTimer=setTimeout(()=>{if(!pointerDrag)return;const shift=Number(hover);state.weekDirection=Math.sign(shift);state.weekStart=addDays(state.weekStart,shift);state.date=state.weekStart;pointerDrag.weekHover=null;render();},650);}
  if(event.clientY>innerHeight-70)scrollBy(0,18);else if(event.clientY<90)scrollBy(0,-18);
});
document.addEventListener('pointerup',event=>{
  if(!pointerDrag)return;const current=pointerDrag,elements=document.elementsFromPoint(event.clientX,event.clientY),pool=elements.map(el=>el.closest?.('[data-pool-drop]')).find(Boolean),weekDay=elements.map(el=>el.closest?.('[data-week-drop-date]')).find(Boolean);pointerDrag=null;clearTimeout(current.weekTimer);current.overlay.remove();current.mask.classList.add('is-leaving');setTimeout(()=>current.mask.remove(),180);document.body.classList.remove('is-schedule-dragging');document.querySelectorAll('.drag-source,.drag-over').forEach(node=>node.classList.remove('drag-source','drag-over'));if(pool){unscheduleManualJob(current.id);return;}if(weekDay){moveManualJobToDate(current.id,weekDay.dataset.weekDropDate);return;}
  const lane=document.elementsFromPoint(event.clientX,event.clientY).map(el=>el.closest?.('[data-drop-lane]')).find(Boolean);
  if(lane) moveManualJob(current.id,lane,event.clientX-current.offsetX);
});

document.addEventListener('change',event=>{
  if(event.target.id==='date-picker') {state.date=event.target.value;render();}
  if(event.target.name==='required_skill'||event.target.name==='work_type') updateRequestRequirements();
  if(event.target.dataset.selectSchedule){event.target.checked?state.selectedSchedule.add(event.target.dataset.selectSchedule):state.selectedSchedule.delete(event.target.dataset.selectSchedule);render();}
  if(event.target.dataset.selectPool){event.target.checked?state.selectedPool.add(event.target.dataset.selectPool):state.selectedPool.delete(event.target.dataset.selectPool);render();}
});

document.addEventListener('pointerover',event=>{const sidebar=event.target.closest('.sidebar');if(sidebar){state.navExpanded=true;sidebar.classList.add('nav-expanded');}});
document.addEventListener('pointerout',event=>{const sidebar=event.target.closest('.sidebar');if(sidebar&&!sidebar.contains(event.relatedTarget)){state.navExpanded=false;sidebar.classList.remove('nav-expanded');}});
document.addEventListener('pointermove',event=>{const bar=event.target.closest('.week-bar');if(bar){const rect=bar.getBoundingClientRect();bar.style.setProperty('--tip-y',`${Math.max(10,Math.min(rect.height-10,event.clientY-rect.top))}px`);}});
window.addEventListener('resize',()=>requestAnimationFrame(drawScheduleLinks));

document.addEventListener('submit',event=>{
  event.preventDefault();
  const form=event.target;
  if(form.id==='login-form') {
    const data=new FormData(form);return run(async()=>{await signIn(data.get('email'),data.get('password'));await enter();});
  }
  if(form.id==='request-form') {
    const data=new FormData(form), date=data.get('date');
    const dates=[date];if(data.has('allow_next_night'))dates.push(nextDate(date));
    const sector=data.get('work_sector');
    const body={title:data.get('title'),work_type:data.get('work_type')||null,work_sector:sector,protected_sectors:[...new Set([sector,...data.getAll('protection')])],required_skill:data.get('required_skill'),
      preferred_engineer:data.get('preferred_engineer')||null,required_equipment_ids:data.getAll('equipment'),power_requirement:data.get('power_requirement'),technicians_required:Number(data.get('technicians_required')),
      phases:['setup','work','test','handback'].map(name=>({name,duration_minutes:Number(data.get(name))})),
      preferred_start:`${date}T${data.get('time')}:00+08:00`,earliest_start:`${date}T01:15:00+08:00`,deadline:`${dates.at(-1)}T04:25:00+08:00`,allowed_dates:dates,depends_on:data.get('depends_on')?[data.get('depends_on')]:[]};
    return run(async()=>{const result=await api('/requests',{method:'POST',body});state.page='my-requests';await reload();return `${result.id} submitted. It is demand, not a reservation.`;});
  }
});

try {
  state.config=await loadConfig();
  if(canRestoreDemo()) {try{await enter();}catch(_){await signOut();state.user=null;}}
  render();
} catch(error) {root.innerHTML=`<div class="boot"><h1>Cannot start the workspace</h1><p>${h(error.message)}</p><p>Start the server using the README, then reload this page.</p></div>`;}
