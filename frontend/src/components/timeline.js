import { h, time, duration, endOf } from '../lib/format.js';

export function timeline(state) {
  const { snapshot: s, date, viewMode, proposal } = state;
  const day = s.engineering_windows.find((w) => w.date === date);
  if (!day) return '';
  const start = new Date(day.start).getTime(), end = new Date(day.end).getTime();
  const percent = (iso) => Math.max(0, Math.min(100, (new Date(iso).getTime() - start) / (end - start) * 100));
  const requests = Object.fromEntries(s.requests.map((r) => [r.id, r]));
  let jobs = s.occupancy.map((a) => ({ ...a, kind: 'booked' }));
  if (viewMode === 'requested' && state.user.role === 'officer') {
    jobs = [...jobs, ...s.requests.filter((r) => r.status === 'submitted').map((r) => ({
      label: r.id, start: r.preferred_start, end: endOf(r.preferred_start, duration(r)),
      protected_sectors: r.protected_sectors, kind: 'pending'
    }))];
  }
  if (viewMode === 'proposal' && proposal?.allocations?.length) {
    const booked = new Set(s.committed_allocations.map((a) => a.request_id));
    jobs = proposal.allocations.map((a) => ({ ...a, label: a.request_id,
      protected_sectors: requests[a.request_id]?.protected_sectors || [],
      kind: booked.has(a.request_id) ? 'booked' : 'proposed' }));
  }
  const ticks = Array.from({ length: 8 }, (_, i) => `<span style="left:${i / 7 * 100}%">${time(new Date(start + i * 30 * 60000).toISOString())}</span>`).join('');
  const rows = s.sectors.map((sector) => {
    const relevant = jobs.filter((j) => j.protected_sectors.includes(sector.id) && new Date(j.start).getTime() < end && new Date(j.end).getTime() > start);
    const blocks = relevant.map((j, i) => {
      const left = percent(j.start), width = percent(j.end) - left;
      const isProtection = requests[j.label] && requests[j.label].work_sector !== sector.id;
      const label = `${j.label}${isProtection ? " protection" : ""}`;
      const title = `${label} | ${time(j.start)}-${time(j.end)} | ${j.kind}`;
      return `<div class="time-block ${h(j.kind)} ${isProtection?"protection":""}" style="left:${left}%;width:${width}%;top:${8+i*31}px" title="${h(title)}"><b>${h(label)}</b><span>${time(j.start)} - ${time(j.end)}</span></div>`;
    }).join('');
    const blackouts = s.blackouts.filter((b) => b.sector_ids.includes(sector.id) && new Date(b.start).getTime() < end && new Date(b.end).getTime() > start).map((b) =>
      `<div class="blackout" style="left:${percent(b.start)}%;width:${percent(b.end)-percent(b.start)}%" title="${h(b.reason)}"><span>Restricted</span></div>`).join('');
    return `<div class="timeline-row"><div class="row-label"><strong>${h(sector.id)}</strong><small>${h(sector.power_zone)}</small></div><div class="track-lane" style="min-height:${Math.max(48,relevant.length*31+16)}px">${blackouts}${blocks}</div></div>`;
  }).join('');
  return `<section class="panel"><div class="panel-head"><div><h2>Engineering window</h2><p>Occupancy, not blanket permission to work. All times SGT.</p></div><div class="segmented"><button data-view="booked" class="${viewMode==='booked'?'active':''}">Booked</button>${state.user.role==='officer'?`<button data-view="requested" class="${viewMode==='requested'?'active':''}">Requested</button><button data-view="proposal" class="${viewMode==='proposal'?'active':''}" ${!proposal?.allocations?.length?'disabled':''}>Proposed</button>`:''}</div></div><div class="timeline-scroll"><div class="timeline"><div class="timeline-axis"><div>Sector / power</div><div class="ticks">${ticks}</div></div>${rows}</div></div><div class="legend"><span><i class="key booked"></i>Committed</span><span><i class="key pending"></i>Requested, not reserved</span><span><i class="key proposed"></i>Proposed</span><span><i class="key restricted"></i>Restriction</span></div></section>`;
}

export function corridor(snapshot) {
  return `<section class="corridor panel"><div class="corridor-label"><strong>Demo corridor</strong><span>Fictional, one direction</span></div><div class="rail-route">${snapshot.sectors.map((s,i)=>`<span class="rail-node">${String.fromCharCode(65+i)}</span><span class="rail-edge"><b>${h(s.id)}</b><small>${h(s.power_zone)}</small></span>`).join('')}<span class="rail-node">G</span></div></section>`;
}
