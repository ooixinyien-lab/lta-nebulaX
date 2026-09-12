import { h, time, duration, endOf } from '../lib/format.js';

const SGT_DATE=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Singapore',year:'numeric',month:'2-digit',day:'2-digit'});
const sgtDate=iso=>{const parts=Object.fromEntries(SGT_DATE.formatToParts(new Date(iso)).map(p=>[p.type,p.value]));return `${parts.year}-${parts.month}-${parts.day}`;};
const hours=minutes=>`${(minutes/60).toFixed(minutes%60?1:0)}h`;
const addDays=(date,days)=>{const value=new Date(`${date}T00:00:00Z`);value.setUTCDate(value.getUTCDate()+days);return value.toISOString().slice(0,10);};
const virtualWindow=(snapshot,date)=>snapshot.engineering_windows.find(w=>w.date===date)||{date,sector_ids:snapshot.sectors.map(s=>s.id),start:`${date}T01:00:00+08:00`,end:`${date}T04:30:00+08:00`,virtual:true};

export function weekOverview(state) {
  const days=Array.from({length:7},(_,index)=>virtualWindow(state.snapshot,addDays(state.weekStart||state.date,index)));
  const arrow=direction=>`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${direction<0?'M15 5l-7 7 7 7':'M9 5l7 7-7 7'}"/></svg>`;
  return `<section class="panel week-overview ${state.weekDirection>0?'week-next':state.weekDirection<0?'week-previous':''}"><div class="week-overview-head"><div class="week-overview-title"><h2>7-day overview</h2><div class="week-legend"><span><i class="week-key locked"></i>Locked</span><span><i class="week-key unlocked"></i>Unlocked</span><span><i class="week-key unused"></i>Unused</span></div></div></div><div class="week-overview-body"><button class="icon-button week-shift" data-week-shift="-7" aria-label="Previous 7 days" title="Previous 7 days">${arrow(-1)}</button><div class="week-bars">${days.map(day=>{
    const windowStart=new Date(day.start).getTime(),windowEnd=new Date(day.end).getTime();
    const total=(windowEnd-windowStart)/60000;
    const allocations=(state.manualPlan||[]).filter(a=>sgtDate(a.start)===day.date);
    let locked=0,unlocked=0;
    for(let tick=windowStart;tick<windowEnd;tick+=5*60000){
      const active=allocations.filter(a=>new Date(a.start).getTime()<tick+5*60000&&new Date(a.end).getTime()>tick);
      if(active.some(a=>a.locked))locked+=5;else if(active.length)unlocked+=5;
    }
    const unused=Math.max(0,total-locked-unlocked);
    const lockedPct=Math.min(100,locked/total*100),unlockedPct=Math.min(100-lockedPct,unlocked/total*100),unusedPct=Math.max(0,100-lockedPct-unlockedPct);
    const label=new Intl.DateTimeFormat('en-SG',{weekday:'short',day:'numeric',month:'short',timeZone:'Asia/Singapore'}).format(new Date(day.start));
    const visibleKinds=[['locked',locked],['unlocked',unlocked],['unused',unused]].filter(([,minutes])=>minutes>0).map(([kind])=>kind);
    const segment=(kind,minutes,pct)=>`<i class="week-used ${kind} ${kind===visibleKinds[0]?'is-bottom':''} ${kind===visibleKinds.at(-1)?'is-top':''}" style="height:${pct}%"><span class="week-tooltip"><b>${kind[0].toUpperCase()+kind.slice(1)}</b><span>${hours(minutes)}</span></span></i>`;
    return `<button class="week-day ${state.date===day.date?'active':''} ${day.virtual?'virtual':''}" data-schedule-date="${h(day.date)}" data-week-drop-date="${h(day.date)}" aria-label="Open ${h(label)} schedule"><span class="week-date"><strong>${h(label)}</strong></span><span class="week-bar ${locked+unlocked===0?'capacity-empty':''}">${segment('locked',locked,lockedPct)}${segment('unlocked',unlocked,unlockedPct)}${segment('unused',unused,unusedPct)}</span></button>`;
  }).join('')}</div><button class="icon-button week-shift" data-week-shift="7" aria-label="Next 7 days" title="Next 7 days">${arrow(1)}</button></div></section>`;
}

export function timeline(state, options={}) {
  const { snapshot: s, date, viewMode, proposal } = state;
  const editable=!!options.editable;
  const day = virtualWindow(s,date);
  if (!day) return '';
  const start = new Date(day.start).getTime(), end = new Date(day.end).getTime();
  const percent = (iso) => Math.max(0, Math.min(100, (new Date(iso).getTime() - start) / (end - start) * 100));
  const requests = Object.fromEntries(s.requests.map((r) => [r.id, r]));
  let jobs = editable ? (state.manualPlan||[]).map(a=>({...a,label:a.request_id,protected_sectors:requests[a.request_id]?.protected_sectors||[],kind:a.locked?'locked':'manual'})) : s.occupancy.map((a) => ({ ...a, kind: 'booked' }));
  if (!editable && viewMode === 'requested' && state.user.role === 'officer') {
    jobs = [...jobs, ...s.requests.filter((r) => r.status === 'submitted').map((r) => ({
      label: r.id, start: r.preferred_start, end: endOf(r.preferred_start, duration(r)),
      protected_sectors: r.protected_sectors, kind: 'pending'
    }))];
  }
  if (!editable && viewMode === 'proposal' && proposal?.allocations?.length) {
    const booked = new Set(s.committed_allocations.map((a) => a.request_id));
    jobs = proposal.allocations.map((a) => ({ ...a, label: a.request_id,
      protected_sectors: requests[a.request_id]?.protected_sectors || [],
      kind: booked.has(a.request_id) ? 'booked' : 'proposed' }));
  }
  const ticks = Array.from({ length: 8 }, (_, i) => `<span style="left:${i / 7 * 100}%">${time(new Date(start + i * 30 * 60000).toISOString())}</span>`).join('');
  const selectedAllocations=(state.manualPlan||[]).filter(a=>state.selectedSchedule?.has(a.request_id));
  const hasLockedSelection=selectedAllocations.some(a=>a.locked),hasUnlockedSelection=selectedAllocations.some(a=>!a.locked),hasNonUnlockableSelection=selectedAllocations.some(a=>a.unlockable===false);
  const canAutoSchedule=(state.manualPlan||[]).some(a=>!a.locked);
  const actions=editable?`<div class="daily-actions"><div class="history-actions"><button class="icon-button history-button" data-action="undo-plan" title="Undo schedule change" aria-label="Undo schedule change" ${state.planHistoryPast?.length?'':'disabled'}>&#8630;</button><button class="icon-button history-button" data-action="redo-plan" title="Redo schedule change" aria-label="Redo schedule change" ${state.planHistoryFuture?.length?'':'disabled'}>&#8631;</button></div><button class="button primary small" data-action="generate" ${canAutoSchedule?'':'disabled'}>Auto-schedule</button>${state.config?.ui_demo?'<button class="button secondary small" data-action="save-demo">Save demo schedule</button>':''}${state.selectedSchedule?.size?`<div class="selection-actions"><b>${state.selectedSchedule.size} selected</b><button class="button quiet-action" data-action="select-all-schedule">Select all</button><button class="button secondary small" data-action="batch-unlock" ${!hasLockedSelection||hasNonUnlockableSelection?'disabled':''}>Unlock</button><button class="button primary small" data-action="batch-lock" ${!hasUnlockedSelection?'disabled':''}>Lock</button><button class="icon-button" data-action="clear-schedule-selection" aria-label="Clear selection">&times;</button></div>`:''}</div>`:'';
  const rows = s.sectors.map((sector) => {
    const relevant = jobs.filter((j) => j.protected_sectors.includes(sector.id) && new Date(j.start).getTime() < end && new Date(j.end).getTime() > start);
    const blocks = relevant.map((j, i) => {
      const left = percent(j.start), width = percent(j.end) - left;
      const isProtection = requests[j.label] && requests[j.label].work_sector !== sector.id;
      const label = `${j.label}${isProtection ? " protection" : ""}`;
      const title = `${label} | ${time(j.start)}-${time(j.end)} | ${j.kind}`;
      const canDrag=editable&&!j.locked&&!isProtection;
      const conflict=editable&&state.issues.some(issue=>issue.request_ids.includes(j.label));
      const selected=state.selectedSchedule?.has(j.label);
      const select=editable&&!isProtection?`<label class="timeline-select"><input type="checkbox" data-select-schedule="${h(j.label)}" ${selected?'checked':''}/><span class="sr-only">Select ${h(j.label)}</span></label>`:'';
      const lockStatus=editable&&!isProtection?`<span class="lock-status ${j.locked?'locked':'unlocked'}" title="${j.locked?'Locked':'Unlocked'}" aria-label="${j.locked?'Locked':'Unlocked'}"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="10" width="12" height="10" rx="2"/><path d="M9 10V7a3 3 0 0 1 ${j.locked?'6 0v3':'6-1'}"/></svg></span>`:'';
      return `<div class="time-block ${h(j.kind)} ${isProtection?"protection":""} ${canDrag?'draggable':''} ${conflict?'conflict':''} ${selected?'selected':''}" data-job-part="${h(j.label)}" ${canDrag?`data-drag-job="${h(j.label)}"`:''} style="left:${left}%;width:${width}%;top:${8+i*39}px" title="${h(title)}">${select}<div class="job-copy"><b>${h(label)}</b><span>${time(j.start)} - ${time(j.end)}${editable&&!isProtection?` &middot; ${h(j.engineer_id)}`:''}</span></div>${lockStatus}</div>`;
    }).join('');
    const blackouts = s.blackouts.filter((b) => b.sector_ids.includes(sector.id) && new Date(b.start).getTime() < end && new Date(b.end).getTime() > start).map((b) =>
      `<div class="blackout" style="left:${percent(b.start)}%;width:${percent(b.end)-percent(b.start)}%" title="${h(b.reason)}"><span>Restricted</span></div>`).join('');
    return `<div class="timeline-row"><div class="row-label"><strong>${h(sector.id)}</strong><small>${h(sector.power_zone)}</small></div><div class="track-lane ${editable?'drop-lane':''}" ${editable?`data-drop-lane="${h(sector.id)}" data-window-start="${h(day.start)}" data-window-end="${h(day.end)}"`:''} style="min-height:${Math.max(56,relevant.length*39+16)}px">${blackouts}${blocks}</div></div>`;
  }).join('');
  const dayLabel=new Intl.DateTimeFormat('en-SG',{weekday:'long',day:'numeric',month:'long',timeZone:'Asia/Singapore'}).format(new Date(day.start));
  return `<section class="panel timeline-panel ${editable?'editable-timeline':''}"><div class="panel-head"><div><h2>${editable?h(dayLabel):'Engineering window'}</h2>${editable?'':'<p>Occupancy, not blanket permission to work. All times SGT.</p>'}</div>${editable?actions:`<div class="segmented"><button data-view="booked" class="${viewMode==='booked'?'active':''}">Booked</button>${state.user.role==='officer'?`<button data-view="requested" class="${viewMode==='requested'?'active':''}">Requested</button><button data-view="proposal" class="${viewMode==='proposal'?'active':''}" ${!proposal?.allocations?.length?'disabled':''}>Proposed</button>`:''}</div>`}</div><div class="timeline-scroll"><div class="timeline"><div class="timeline-axis"><div>Sector / power</div><div class="ticks">${ticks}</div></div>${rows}</div></div><div class="legend"><span><i class="key booked"></i>Committed / locked</span><span><i class="key pending"></i>Requested, not reserved</span><span><i class="key proposed"></i>Proposed / manual</span><span><i class="key restricted"></i>Restriction</span></div></section>`;
}

export function corridor(snapshot) {
  const stations = snapshot.stations || [];
  const startName = stations[0]?.name || 'Pasir Ris';
  const endName = stations[stations.length - 1]?.name || 'Eunos';
  const nodes = stations.length
    ? stations.map((st) => `<span class="rail-node" title="${h(st.name)} (${h(st.id)})">${h(st.id)}</span>`)
    : snapshot.sectors.map((s, i) => `<span class="rail-node">${String.fromCharCode(65 + i)}</span>`).concat(['<span class="rail-node">G</span>']);

  const segments = snapshot.sectors.map((s, i) =>
    `${nodes[i]}<span class="rail-edge"><b>${h(s.id)}</b><small>${h(s.power_zone)}</small></span>`
  ).join('');
  const lastNode = nodes[snapshot.sectors.length] || '';

  return `<section class="corridor panel"><div class="corridor-label"><strong>East-West Line (EWL)</strong><span>${h(startName)} to ${h(endName)}</span></div><div class="rail-route">${segments}${lastNode}</div></section>`;
}
