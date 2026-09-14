import { h, time, duration, endOf, badge } from '../lib/format.js';

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
      label: r.id, start: r.preferred_start || r.earliest_start, end: endOf(r.preferred_start || r.earliest_start, duration(r)),
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

const MAP_STATUSES=new Set(['clear','booked','transit','conflict']);
const mapStatus=value=>MAP_STATUSES.has(value)?value:'clear';
const WORKFLOW_TYPES=new Set(['approved','scheduled','submitted','pending','cancelled','draft','locked','unlocked','booked','transit','clear','conflict']);
const workflowType=value=>{
  const key=String(value||'').toLowerCase().replace(/[^a-z0-9_-]/g,'');
  return WORKFLOW_TYPES.has(key)?key:'neutral';
};
const currentDate=iso=>{try{return iso?sgtDate(iso):'';}catch{return '';}};
const hasCurrentDate=(record,date)=>currentDate(record?.start)===date;
const array=value=>Array.isArray(value)?value:[];

export function networkMap(state={}) {
  const snapshot=state.snapshot;
  if (!snapshot) return '';
  const stations=array(snapshot.stations).map((station,index)=>({
    ...station,
    _index:index,
    _schematic:station?.schematic_x===null||station?.schematic_x===undefined||station?.schematic_x===''?NaN:Number(station.schematic_x)
  })).sort((a,b)=>{
    const aFinite=Number.isFinite(a._schematic),bFinite=Number.isFinite(b._schematic);
    if (aFinite&&bFinite&&a._schematic!==b._schematic) return a._schematic-b._schematic;
    if (aFinite!==bFinite) return aFinite?-1:1;
    return a._index-b._index;
  });
  const margin=72,viewWidth=920,stationSpan=Math.max(0,viewWidth-margin*2);
  const stationCenterY=120,stationCodeRadius=20,depotConnectorStartY=140,depotLabelTopY=188,stationRingRadius=24;
  const sectorBadgeY=94,vehicleMarkerY=30,vehicleMarkerBottomY=40;
  const indexX=index=>stations.length>1?margin+stationSpan*index/(stations.length-1):viewWidth/2;
  const finiteValues=stations.map(st=>st._schematic).filter(Number.isFinite);
  const minSchematic=Math.min(...finiteValues),maxSchematic=Math.max(...finiteValues);
  const schematicRange=maxSchematic-minSchematic;
  const stationPoints=stations.map((station,index)=>({
    station,
    x:Number.isFinite(station._schematic)&&schematicRange>0
      ? margin+stationSpan*(station._schematic-minSchematic)/schematicRange
      : indexX(index)
  }));
  const stationById=new Map(stationPoints.map(point=>[String(point.station?.id??''),point]));
  const sectors=array(snapshot.sectors);
  const validSectors=sectors.map((sector,index)=>{
    const from=stationById.get(String(sector?.from_station??'')),to=stationById.get(String(sector?.to_station??''));
    return from&&to?{sector,from,to,index}:null;
  }).filter(Boolean);
  const validSectorById=new Map(validSectors.map(row=>[String(row.sector?.id??''),row]));
  const allRequests=array(snapshot.requests);
  const requests=state.user?.role==='officer'
    ? allRequests
    : state.user?.id===undefined||state.user?.id===null
      ? []
      : allRequests.filter(request=>String(request?.owner_id??'')===String(state.user.id));
  const requestById=new Map(requests.map(request=>[String(request?.id??''),request]));
  const allRequestById=new Map(allRequests.map(request=>[String(request?.id??''),request]));
  const issues=array(state.issues);
  const date=state.date||snapshot.metadata?.planning_date||array(snapshot.engineering_windows)[0]?.date||'';
  const commitments=array(snapshot.committed_allocations).filter(allocation=>hasCurrentDate(allocation,date)&&(state.user?.role==='officer'||requestById.has(String(allocation?.request_id??''))));
  const occupancy=array(snapshot.occupancy).filter(record=>hasCurrentDate(record,date));
  const bookingsBySector=new Map();
  const addBooking=(sectorId,entry)=>{
    if (!bookingsBySector.has(sectorId)) bookingsBySector.set(sectorId,[]);
    bookingsBySector.get(sectorId).push(entry);
  };
  commitments.forEach(allocation=>{
    const request=requestById.get(String(allocation?.request_id??''));
    const footprint=array(request?.protected_sectors).length?array(request.protected_sectors):array(allocation?.protected_sectors);
    footprint.forEach(sectorId=>addBooking(String(sectorId),{allocation,request}));
  });
  occupancy.forEach(record=>array(record?.protected_sectors).forEach(sectorId=>addBooking(String(sectorId),{occupancy:record,request:requestById.get(String(record?.request_id??''))})));
  const currentActivityRequestIds=new Set(commitments.map(allocation=>String(allocation?.request_id??'')));
  occupancy.forEach(record=>{
    const label=String(record?.label??''),requestId=record?.request_id??(label&&label!=='Reserved'?label:null);
    if (requestId!==null&&requestId!==undefined&&String(requestId)!=='') currentActivityRequestIds.add(String(requestId));
  });
  const issueAffects=(issue,sector)=>{
    if (!sector) return false;
    const requestIds=array(issue?.request_ids).map(id=>String(id));
    const activeRequestIds=requestIds.filter(id=>currentActivityRequestIds.has(id));
    if (requestIds.length&&!activeRequestIds.length) return false;
    if (activeRequestIds.some(id=>{
      const request=allRequestById.get(id);
      return request&&(String(request.work_sector)===String(sector.id)||array(request.protected_sectors).map(value=>String(value)).includes(String(sector.id)));
    })) return true;
    const tokens=String(issue?.resource??'').split(/[^A-Za-z0-9_-]+/).filter(Boolean);
    return tokens.includes(String(sector.id));
  };
  const scheduleSectorIds=schedule=>{
    const direct=schedule?.sector_id;
    if (direct!==undefined&&direct!==null&&String(direct)!=='') return [String(direct)];
    return array(schedule?.segments).map(segment=>segment?.sector_id).filter(value=>value!==undefined&&value!==null&&String(value)!=='').map(value=>String(value));
  };
  const transitBySector=new Map();
  array(snapshot.transit_schedules).forEach(schedule=>{
    if (!hasCurrentDate(schedule,date)) return;
    scheduleSectorIds(schedule).forEach(sectorId=>{
      if (!transitBySector.has(sectorId)) transitBySector.set(sectorId,[]);
      transitBySector.get(sectorId).push({schedule,sectorId});
    });
  });
  transitBySector.forEach(entries=>entries.sort((a,b)=>new Date(a.schedule.start)-new Date(b.schedule.start)));
  const issueAffectsForSector=sector=>issues.some(issue=>issueAffects(issue,sector));
  const statusFor=sector=>{
    if (issueAffectsForSector(sector)) return 'conflict';
    if ((bookingsBySector.get(String(sector.id))||[]).length) return 'booked';
    if ((transitBySector.get(String(sector.id))||[]).length) return 'transit';
    return 'clear';
  };
  const visibleRequestForSector=(request,sectorId)=>request&&request.status!=='cancelled'&&array(request.protected_sectors).map(value=>String(value)).includes(String(sectorId));
  const committedRequestIds=new Set(array(snapshot.committed_allocations).map(allocation=>String(allocation?.request_id??'')));
  const workflowLabel=value=>{
    const label=String(value??'');
    return label?`${label.slice(0,1).toUpperCase()}${label.slice(1)}`:'';
  };
  const statusBadge=(label,status)=>badge(label,workflowType(status));
  const activityTone=status=>{
    const key=String(status??'').toLowerCase();
    if (['scheduled','booked','locked'].includes(key)) return 'scheduled';
    if (['submitted','pending','draft','unlocked'].includes(key)) return 'submitted';
    if (key==='approved') return 'approved';
    if (key==='transit') return 'transit';
    if (key==='conflict') return 'conflict';
    return 'neutral';
  };
  const activityRow=(label,value)=>value===undefined||value===null||value===''?'':`<div><dt>${h(label)}</dt><dd>${value}</dd></div>`;
  const activityCard=({tone,id,title,rows})=>{
    const cardTone=activityTone(tone);
    return `<article class="network-map-activity-card ${h(cardTone)}"><h5 class="network-map-job-title">${id!==undefined&&id!==null&&id!==''?`<span class="network-map-job-id">${h(id)}</span>`:''}<span>${h(title)}</span></h5><dl class="network-map-job-details">${rows.filter(Boolean).join('')}</dl></article>`;
  };
  const windowValue=(start,end)=>{
    if (!start&&!end) return '';
    if (!start) return h(time(end));
    if (!end) return h(time(start));
    return `${h(time(start))} – ${h(time(end))}`;
  };
  const allocationWindow=allocation=>windowValue(allocation?.start,allocation?.end);
  const preferredWindow=request=>{
    if (!request?.preferred_start) return '';
    let preferredEnd='';
    try {
      if (array(request.phases).length) preferredEnd=endOf(request.preferred_start,duration(request));
    } catch {}
    return windowValue(request.preferred_start,preferredEnd);
  };
  const metadata=sector=>{
    const from=stationById.get(String(sector.from_station??''))?.station;
    const to=stationById.get(String(sector.to_station??''))?.station;
    const optional=(label,value)=>value===undefined||value===null||value===''?'':`<div><dt>${h(label)}</dt><dd>${h(value)}</dd></div>`;
    return `<dl class="network-map-metadata"><div><dt>From</dt><dd>${h(from?.name||sector.from_station)}</dd></div><div><dt>To</dt><dd>${h(to?.name||sector.to_station)}</dd></div>${optional('Power zone',sector.power_zone)}${optional('Direction',sector.direction)}<div><dt>Exclusive protection</dt><dd>${sector.exclusive_protection?'Active':'Not active'}</dd></div></dl>`;
  };
  const renderActivity=sector=>{
    const sectorId=String(sector.id);
    const bookingEntries=bookingsBySector.get(sectorId)||[];
    const visibleRequestIds=new Set();
    const cards=[];
    bookingEntries.forEach(entry=>{
      const request=entry.request;
      if (entry.allocation&&request&&request.status!=='cancelled') {
        visibleRequestIds.add(String(request.id));
        const rows=[
          activityRow('Window',allocationWindow(entry.allocation)),
          request.power_requirement?activityRow('Power',h(request.power_requirement)):'',
          activityRow('Status',statusBadge('Scheduled','scheduled')),
          entry.allocation.locked!==undefined?activityRow('Lock',entry.allocation.locked?'Locked':'Unlocked'):''
        ];
        cards.push(activityCard({tone:'scheduled',id:request.id,title:request.title||request.id,rows}));
      }
    });
    requests.filter(request=>visibleRequestForSector(request,sectorId)&&!committedRequestIds.has(String(request.id))&&array(request.allowed_dates).includes(date)).forEach(request=>{
      visibleRequestIds.add(String(request.id));
      const rows=[
        activityRow('Window',windowValue(request.earliest_start,request.deadline)),
        request.preferred_start?activityRow('Preferred',preferredWindow(request)):'',
        request.power_requirement?activityRow('Power',h(request.power_requirement)):'',
        request.status?activityRow('Status',statusBadge(workflowLabel(request.status),request.status)):''
      ];
      cards.push(activityCard({tone:request.status,id:request.id,title:request.title||request.id,rows}));
    });
    bookingEntries.forEach(entry=>{
      const record=entry.occupancy;
      if (!record||String(record.label||'')!=='Reserved'||visibleRequestIds.has(String(record.request_id??''))) return;
      cards.push(activityCard({tone:'booked',title:'Reserved allocation',rows:[
        activityRow('Window',allocationWindow(record)),
        activityRow('Status',statusBadge('Reserved','booked'))
      ]}));
    });
    (transitBySector.get(sectorId)||[]).forEach(({schedule})=>{
      const vehicleId=String(schedule?.vehicle_id??'');
      const vehicle=array(snapshot.vehicles).find(item=>String(item?.id??'')===vehicleId);
      const vehicleLabel=vehicle?.home_depot?`${vehicleId} · ${vehicle.home_depot}`:vehicleId;
      cards.push(activityCard({tone:'transit',id:vehicleId,title:`Transit ${vehicleLabel}`,rows:[
        activityRow('Window',allocationWindow(schedule)),
        activityRow('Status',statusBadge('Transit','transit'))
      ]}));
    });
    return cards.length?cards.join(''):issueAffectsForSector(sector)?'':`<p class="network-map-empty">Clear — no active possession for this sector on ${h(date)}.</p>`;
  };
  const renderSectorActivity=sector=>`<div class="network-map-activity"><h4>Sector ${h(sector.id)}</h4>${metadata(sector)}<div class="network-map-activity-list">${renderActivity(sector)}</div></div>`;
  const renderConflicts=sector=>{
    const affecting=issues.filter(issue=>issueAffects(issue,sector));
    return affecting.map(issue=>`<div class="network-map-conflict"><strong>${h(issue.code||'Conflict')}</strong><span>${h(issue.message||issue.explanation||'Conflict affecting this sector.')}</span></div>`).join('');
  };
  const selected=state.networkMapSelection;
  const selectedStation=selected?.type==='station'?stationById.get(String(selected.id)):null;
  const selectedSector=selected?.type==='sector'?validSectors.find(row=>String(row.sector.id)===String(selected.id)):null;
  const inspectorBody=selectedSector
    ? `<h3>Sector ${h(selectedSector.sector.id)}</h3>${renderSectorActivity(selectedSector.sector)}${renderConflicts(selectedSector.sector)}`
    : selectedStation
      ? `<h3>Station ${h(selectedStation.station.id)} · ${h(selectedStation.station.name)}</h3>${(()=>{const adjacent=validSectors.filter(row=>String(row.sector.from_station)===String(selectedStation.station.id)||String(row.sector.to_station)===String(selectedStation.station.id));return adjacent.length?adjacent.map(row=>renderSectorActivity(row.sector)+renderConflicts(row.sector)).join(''):`<p class="network-map-empty">No adjacent sectors available for this station.</p>`;})()}`
      : `<p class="network-map-empty">Select a station or sector to inspect</p>`;
  const zoneGroups=[];
  const zonesById=new Map();
  sectors.forEach(sector=>{
    const zone=String(sector?.power_zone??'').trim();
    if (!zone) return;
    if (!zonesById.has(zone)) {
      const group={zone,sectors:[]};
      zonesById.set(zone,group);
      zoneGroups.push(group);
    }
    zonesById.get(zone).sectors.push(sector);
  });
  const zones=zoneGroups.map(group=>{
    const sectorIds=group.sectors.map(sector=>String(sector?.id??'')).filter(Boolean);
    const sectorIdSet=new Set(sectorIds);
    const requestIds=[...new Set(requests.filter(request=>request.status!=='cancelled'&&sectorIdSet.has(String(request?.work_sector??''))).map(request=>String(request?.id??'')).filter(Boolean))];
    const conflict=group.sectors.some(issueAffectsForSector);
    return `<div class="network-map-zone ${conflict?'conflict':'clear'}"><div class="network-map-zone-head"><strong>${h(group.zone)}</strong><b class="network-map-zone-status">${conflict?'CONFLICT':'CLEAR'}</b></div><span class="network-map-zone-sectors">Sectors ${h(sectorIds.join(', '))}</span><small>${h(`${sectorIds.length} sector${sectorIds.length===1?'':'s'}`)}</small>${requestIds.length?`<small>${h(`${requestIds.length} request${requestIds.length===1?'':'s'}`)}</small>`:''}</div>`;
  }).join('');
  const zonePanel=`<section class="panel network-map-zones-panel" aria-labelledby="network-map-power-zones-heading"><div class="network-map-zones-head"><div><h2 id="network-map-power-zones-heading">Power zones</h2><p>Each banner groups the sectors assigned to one shared power zone; status reflects active conflicts for the selected date.</p></div></div>${zones?`<div class="network-map-zones">${zones}</div>`:'<p class="network-map-zones-empty">No power zones are defined for this network snapshot.</p>'}</section>`;
  const stationSvg=stationPoints.map(({station,x})=>{
    const selectedStationClass=selected?.type==='station'&&String(selected.id)===String(station.id)?' selected':'';
    return `<g class="network-map-station${selectedStationClass}" data-map-station="${h(station.id)}" role="button" tabindex="0" aria-pressed="${selectedStationClass?'true':'false'}" aria-label="Station ${h(station.id)} ${h(station.name)}"><circle class="network-map-station-code" cx="${x}" cy="${stationCenterY}" r="${stationCodeRadius}"></circle><text x="${x}" y="${stationCenterY+5}" text-anchor="middle">${h(station.id)}</text><text class="network-map-station-name" x="${x}" y="${stationCenterY+40}" text-anchor="middle">${h(station.name)}</text></g>`;
  }).join('');
  const sectorSvg=validSectors.map(({sector,from,to})=>{
    const status=mapStatus(statusFor(sector)),selectedSectorClass=selected?.type==='sector'&&String(selected.id)===String(sector.id)?' selected':'';
    const midpoint=(from.x+to.x)/2;
    return `<g class="network-map-track ${status} network-map-sector${selectedSectorClass}" data-map-sector="${h(sector.id)}" role="button" tabindex="0" aria-pressed="${selectedSectorClass?'true':'false'}" aria-label="Sector ${h(sector.id)} from ${h(from.station.name)} to ${h(to.station.name)}"><g class="network-map-sector-content"><line class="network-map-sector-line ${status}" x1="${from.x}" y1="${stationCenterY}" x2="${to.x}" y2="${stationCenterY}"></line><line class="network-map-sector-hit" x1="${from.x}" y1="${stationCenterY}" x2="${to.x}" y2="${stationCenterY}"></line><g class="network-map-sector-badge ${status}" transform="translate(${midpoint} ${sectorBadgeY})"><rect x="-25" y="-13" width="50" height="26" rx="13"></rect><text y="5" text-anchor="middle">${h(sector.id)}</text></g></g></g>`;
  }).join('');
  const depot=array(snapshot.vehicles)[0],depotAnchor=stationPoints[Math.floor(stationPoints.length/2)],depotLabel=[depot?.home_depot,depot?.id].filter(value=>value!==undefined&&value!==null&&value!=='').join(' · ');
  const depotSvg=depot&&depotAnchor?`<g class="network-map-depot" aria-label="${h(depot.home_depot?`Depot ${depot.home_depot} vehicle ${depot.id||''}`:`Vehicle ${depot.id||''}`)}"><circle class="network-map-depot-station-ring" cx="${depotAnchor.x}" cy="${stationCenterY}" r="${stationRingRadius}"></circle><line class="network-map-depot-line" x1="${depotAnchor.x}" y1="${depotConnectorStartY}" x2="${depotAnchor.x}" y2="${depotLabelTopY}"></line><rect x="${depotAnchor.x-82}" y="${depotLabelTopY}" width="164" height="25" rx="7"></rect><text x="${depotAnchor.x}" y="${depotLabelTopY+17}" text-anchor="middle">${h(depotLabel)}</text></g>`:'';
  const vehicles=array(snapshot.transit_schedules).filter(schedule=>hasCurrentDate(schedule,date)).reduce((groups,schedule)=>{
    const sectorIds=scheduleSectorIds(schedule),vehicleId=String(schedule?.vehicle_id??'');
    if (!sectorIds.length) return groups;
    if (!groups.has(vehicleId)) groups.set(vehicleId,[]);
    sectorIds.forEach(sectorId=>groups.get(vehicleId).push({schedule,sectorId}));
    return groups;
  },new Map());
  const vehicleSvg=[...vehicles].map(([vehicleId,entries])=>{
    if (!vehicleId) return '';
    const first=entries.slice().sort((a,b)=>new Date(a.schedule.start)-new Date(b.schedule.start)).find(entry=>validSectorById.has(entry.sectorId));
    if (!first) return '';
    const row=validSectorById.get(first.sectorId),x=(row.from.x+row.to.x)/2;
    const vehicle=array(snapshot.vehicles).find(item=>String(item?.id??'')===vehicleId),label=vehicle?.home_depot?`${vehicleId} · ${vehicle.home_depot}`:vehicleId;
    return `<line class="network-map-transit-link" x1="${x}" y1="${vehicleMarkerBottomY}" x2="${x}" y2="${stationCenterY}" stroke="#c88719" stroke-dasharray="2 4" stroke-linecap="round" pointer-events="none"></line><g class="network-map-vehicle" transform="translate(${x} ${vehicleMarkerY})" aria-label="Transit vehicle ${h(label)}"><rect x="-52" y="-14" width="104" height="24" rx="8"></rect><text y="3" text-anchor="middle">${h(label)}</text></g>`;
  }).join('');
  const startStation=stations[0],endStation=stations.at(-1);
  const routeSubtitle=startStation&&endStation?`${startStation.name} to ${endStation.name} · ${date}`:`${date}`;
  return `<div class="network-map-stack">${zonePanel}<section class="panel network-map"><div class="network-map-head"><div><div class="network-map-line-marker">EWL</div><h2>East-West Line</h2><p>${h(routeSubtitle)}</p></div><div class="network-map-legend" aria-label="Map status legend"><span><i class="clear"></i>Clear</span><span><i class="booked"></i>Committed</span><span><i class="transit"></i>Transit</span><span><i class="conflict"></i>Conflict</span></div></div><div class="network-map-canvas"><svg class="network-map-svg" viewBox="0 0 920 220" width="100%" role="img" aria-label="East-West Line network map"><line class="network-map-track-base" x1="${margin}" y1="${stationCenterY}" x2="${viewWidth-margin}" y2="${stationCenterY}"></line>${depotSvg}${vehicleSvg}${sectorSvg}${stationSvg}</svg></div><section class="network-map-inspector" aria-live="polite"><div class="network-map-inspector-body">${inspectorBody}</div></section></section></div>`;
}
