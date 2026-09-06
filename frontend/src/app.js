import { loadConfig, chooseDemo, signIn, signOut, canRestoreDemo } from './auth/session.js';
import { api } from './lib/api.js';
import { h, badge, nextDate } from './lib/format.js';
import { loginPage } from './pages/login.js';
import { requesterPage, newRequestPage } from './pages/requester.js';
import { officerPage, resourcesPage } from './pages/officer.js';

const state = { config:null, user:null, snapshot:null, issues:[], proposal:null, audit:[], date:'2026-09-14', page:'', viewMode:'requested', busy:false };
const root = document.getElementById('app');

function notice(message, error=false) {
  const target=document.getElementById('notice');
  if (target) target.innerHTML=`<div class="notice ${error?'warning':'success'}" role="status">${h(message)}</div>`;
}
async function reload() {
  state.snapshot=await api('/planning-snapshot');
  if (!state.snapshot.engineering_windows.some(w=>w.date===state.date)) state.date=state.snapshot.engineering_windows[0].date;
  if (state.user.role==='officer') {
    const [checks, proposals, audit]=await Promise.all([api('/conflicts/check',{method:'POST'}),api('/proposals'),api('/audit')]);
    state.issues=checks.issues; state.audit=audit;
    if (!state.proposal || state.proposal.status_workflow==='committed') state.proposal=proposals.find(p=>p.status_workflow==='draft')||null;
  }
}
async function enter() {
  state.user=await api('/me');
  state.page=state.user.role==='officer'?'planner':'my-requests';
  state.viewMode=state.user.role==='officer'?'requested':'booked';
  state.proposal=null;
  await reload();
}
function render() {
  if (!state.user) { root.innerHTML=loginPage(state.config); return; }
  const officer=state.user.role==='officer';
  const titles={'planner':['Planning workspace','Review competing work. Publish one coordinated plan.'],'my-requests':['Your maintenance requests','Submit work packages and track approved allocations.'],'new-request':['Request track time','Tell the planner what you need, not just when you want it.'],'resources':['Resources & activity','Availability changes are planning changes.']};
  const [title,subtitle]=titles[state.page]||titles[officer?'planner':'my-requests'];
  const dates=[...new Set(state.snapshot.engineering_windows.map(w=>w.date))];
  const nav=officer?[['planner','Planning workspace','01'],['resources','Resources & activity','02']]:[['my-requests','My requests','01'],['new-request','New request','02']];
  let content=state.page==='new-request'?newRequestPage(state.snapshot):state.page==='resources'?resourcesPage(state):officer?officerPage(state):requesterPage(state);
  root.innerHTML=`<div class="app-shell"><aside class="sidebar"><a class="brand" href="#"><span class="brand-mark">R</span>RailPlan</a><div class="sidebar-kicker">MAINTENANCE WORKSPACE</div><nav>${nav.map(([id,label,num])=>`<button class="nav-item ${state.page===id?'active':''}" data-nav="${id}"><span>${num}</span>${label}</button>`).join('')}</nav><div class="sidebar-note"><span class="status-dot"></span><strong>Fictional corridor</strong><p>Planning support only.<br>No live track access.</p></div><div class="sidebar-user"><div class="avatar">${officer?'O':'R'}</div><div><strong>${h(state.user.name)}</strong><small>${officer?'Planning officer':'Requester'}</small></div><button data-action="logout" title="Sign out" aria-label="Sign out">&rarr;</button></div></aside><div class="app-main"><header class="topbar"><span>NEBULA / Track 1 <span class="crumb">/ Team starter</span></span><div>${badge('SYNTHETIC DATA','neutral')}${badge(state.config.auth_mode==='demo'?'LOCAL DEMO':'SUPABASE AUTH',state.config.auth_mode==='demo'?'warning':'success')}</div></header><main class="content"><div class="page-heading"><div><div class="eyebrow dark">${officer?'OFFICER CONSOLE':'REQUESTER PORTAL'}</div><h1>${title}</h1><p>${subtitle}</p></div><div class="page-actions"><select id="date-picker" aria-label="Planning date">${dates.map(d=>`<option value="${d}" ${state.date===d?'selected':''}>${d}</option>`).join('')}</select><button class="button secondary" data-action="refresh">Refresh</button>${officer&&state.page==='planner'?'<button class="button primary" data-action="generate">Generate proposal &rarr;</button>':''}</div></div><div id="notice" role="alert"></div>${content}<footer class="app-footer"><span>Revision ${state.snapshot.metadata.planning_version} &middot; ${state.config.solver_engine==='cp_sat'?'CP-SAT configured':'Tiny-demo search / not CP-SAT'}</span><span>All constraints are prototype assumptions.</span>${officer&&state.config.auth_mode==='demo'?'<button class="text-button" data-action="reset">Reset synthetic demo</button>':''}</footer></main></div></div>`;
  if (state.page==='new-request') updateEngineers();
}
function updateEngineers() {
  const form=document.getElementById('request-form'); if (!form) return;
  const skill=form.elements.required_skill.value;
  document.getElementById('engineer-select').innerHTML='<option value="">No preference</option>'+state.snapshot.engineers.filter(e=>e.skills.includes(skill)).map(e=>`<option value="${h(e.id)}">${h(e.id)} - ${h(e.name)}</option>`).join('');
}
async function run(task) {
  if (state.busy) return;
  state.busy=true;
  document.body.classList.add('is-busy');
  document.querySelectorAll('button').forEach(b=>b.disabled=true);
  try { const message=await task(); render(); if(message) notice(message); }
  catch(error) { if(error.status===401) { await signOut(); state.user=null; } render(); notice(error.message,true); }
  finally { state.busy=false; document.body.classList.remove('is-busy'); }
}

document.addEventListener('click',event=>{
  const el=event.target.closest('button'); if(!el||state.busy) return;
  if(el.dataset.demo) return run(async()=>{ chooseDemo(el.dataset.demo); await enter(); });
  if(el.dataset.nav) { state.page=el.dataset.nav; render(); return; }
  if(el.dataset.view) { state.viewMode=el.dataset.view; render(); return; }
  if(el.dataset.cancel) return run(async()=>{ if(!confirm('Withdraw this unbooked request?')) return; await api(`/requests/${encodeURIComponent(el.dataset.cancel)}/cancel`,{method:'POST'}); await reload(); return 'Request withdrawn.'; });
  if(el.dataset.equipment) return run(async()=>{ await api('/resources',{method:'PATCH',body:{kind:'equipment',id:el.dataset.equipment,serviceable:el.dataset.serviceable==='true'}}); await reload(); return 'Equipment updated. Previous proposals are now stale.'; });
  if(el.dataset.action==='logout') return run(async()=>{ await signOut(); state.user=null;state.snapshot=null;state.proposal=null; });
  if(el.dataset.action==='refresh') return run(async()=>{ await reload();return 'Latest planning data loaded.'; });
  if(el.dataset.action==='generate') return run(async()=>{ state.proposal=await api('/schedule/proposals',{method:'POST'}); if(state.proposal.allocations?.length) state.viewMode='proposal'; return state.proposal.allocations?.length?'Proposal calculated and independently checked. No bookings have changed yet.':state.proposal.message; });
  if(el.dataset.action==='commit') return run(async()=>{ if(!confirm('Approve and publish this synthetic plan? This does not authorise real railway access.')) return; const p=state.proposal; await api(`/proposals/${p.id}/commit`,{method:'POST',body:{expected_version:p.planning_version}});p.status_workflow='committed';state.viewMode='booked';await reload();return 'Plan published. Requesters can refresh to see their bookings.'; });
  if(el.dataset.action==='absence') return run(async()=>{ const date=state.snapshot.engineering_windows[0].date;await api('/resources',{method:'PATCH',body:{kind:'engineers',id:'E01',unavailable_from:`${date}T02:20:00+08:00`,unavailable_to:`${date}T04:30:00+08:00`}});await reload();return 'E01 is unavailable after 02:20 on the first demo night. Recalculate the pending plan.'; });
  if(el.dataset.action==='reset') return run(async()=>{ if(!confirm('Delete demo edits and proposals, and restore the fictional seed?'))return;await api('/demo/reset',{method:'POST'});state.proposal=null;state.viewMode='requested';await reload();return 'Synthetic fixture restored.'; });
});

document.addEventListener('change',event=>{
  if(event.target.id==='date-picker') {state.date=event.target.value;render();}
  if(event.target.name==='required_skill') updateEngineers();
});

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
    const body={title:data.get('title'),work_sector:sector,protected_sectors:[...new Set([sector,...data.getAll('protection')])],required_skill:data.get('required_skill'),
      preferred_engineer:data.get('preferred_engineer')||null,required_equipment_ids:data.getAll('equipment'),power_requirement:data.get('power_requirement'),technicians_required:Number(data.get('technicians_required')),
      phases:['setup','work','test','handback'].map(name=>({name,duration_minutes:Number(data.get(name))})),
      preferred_start:`${date}T${data.get('time')}:00+08:00`,earliest_start:`${date}T01:00:00+08:00`,deadline:`${dates.at(-1)}T04:30:00+08:00`,allowed_dates:dates,depends_on:data.get('depends_on')?[data.get('depends_on')]:[]};
    return run(async()=>{const result=await api('/requests',{method:'POST',body});state.page='my-requests';await reload();return `${result.id} submitted. It is demand, not a reservation.`;});
  }
});

try {
  state.config=await loadConfig();
  if(canRestoreDemo()) {try{await enter();}catch(_){await signOut();state.user=null;}}
  render();
} catch(error) {root.innerHTML=`<div class="boot"><h1>Cannot start the workspace</h1><p>${h(error.message)}</p><p>Start the server using the README, then reload this page.</p></div>`;}
