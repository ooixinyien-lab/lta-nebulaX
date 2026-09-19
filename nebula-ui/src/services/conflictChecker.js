/**
 * Real-time schedule conflict checking engine based on AGENTS.md constraints.
 * 
 * Rules checked:
 * 1. Workfront capacity: concurrent activities per contract on (week, night) <= contract.number_of_workfronts
 * 2. Weekly allocation cap (Kc): night <= contract.number_of_maximum_access_per_week
 * 3. Co-sharing legal mix:
 *    - 1 PM alone; OR
 *    - 1 PC + <=3 C (max 4); OR
 *    - <=4 C;
 *    - Two PCs NEVER share a group; PM never shares with others.
 * 4. Location supply capacity: occupied groups at location <= supply_capacity (Scen A) or supply + 1 (Scen C)
 * 5. Precedence: activity start week > predecessor finish week
 * 6. Release week: activity week >= planned_start_week
 * 7. Scenario A ECLO ban: eclo is strictly forbidden in Scenario A
 */

export function evaluateScheduleConflicts({
  accesses = [],
  occupancies = [],
  activities = [],
  contracts = [],
  locations = [],
  scenario = 'A',
  activeWeek = null,
}) {
  const activityMap = new Map(activities.map(a => [a.activity_id, a]));
  const contractMap = new Map(contracts.map(c => [c.contract_number, c]));
  const locationMap = new Map(locations.map(l => [l.location_id, l]));

  // Map: activity_id -> list of issues
  const activityConflicts = new Map();
  // Global issue list
  const issues = [];

  function addConflict(activityId, rule, message, severity = 'error', meta = {}) {
    const issue = { activityId, rule, message, severity, ...meta };
    issues.push(issue);
    if (activityId) {
      if (!activityConflicts.has(activityId)) {
        activityConflicts.set(activityId, []);
      }
      activityConflicts.get(activityId).push(issue);
    }
  }

  // Filter accesses to activeWeek if provided, or full set
  const evalAccesses = activeWeek ? accesses.filter(a => a.week === activeWeek) : accesses;
  const evalOccupancies = activeWeek ? occupancies.filter(o => o.week === activeWeek) : occupancies;

  // 1. Workfront Constraints: (contract_number, week, access_night) <= number_of_workfronts
  const workfrontBuckets = new Map(); // key: `${contract}_${week}_${night}` -> [activity_ids]
  for (const acc of evalAccesses) {
    const act = activityMap.get(acc.activity_id);
    const cNum = act?.contract_number || 'UNKNOWN';
    const key = `${cNum}_${acc.week}_${acc.access_night}`;
    if (!workfrontBuckets.has(key)) workfrontBuckets.set(key, []);
    workfrontBuckets.get(key).push(acc.activity_id);
  }

  for (const [key, actIds] of workfrontBuckets.entries()) {
    const [cNum, weekStr, nightStr] = key.split('_');
    const contract = contractMap.get(cNum);
    const maxWf = contract?.number_of_workfronts ?? 2;
    if (actIds.length > maxWf) {
      for (const aid of actIds) {
        addConflict(
          aid,
          'workfront',
          `Workfront cap exceeded for ${cNum}: ${actIds.length}/${maxWf} active on Night N${nightStr} (Week ${weekStr})`,
          'error',
          { week: Number(weekStr), night: Number(nightStr), contract: cNum }
        );
      }
    }
  }

  // 2. Weekly Allocation Cap: access_night <= contract.number_of_maximum_access_per_week (Kc)
  for (const acc of evalAccesses) {
    const act = activityMap.get(acc.activity_id);
    const contract = contractMap.get(act?.contract_number);
    const maxNights = contract?.number_of_maximum_access_per_week ?? 7;
    if (acc.access_night > maxNights) {
      addConflict(
        acc.activity_id,
        'weekly_allocation',
        `Night N${acc.access_night} exceeds max weekly allocation cap (${maxNights}) for ${act?.contract_number}`,
        'error',
        { week: acc.week, night: acc.access_night }
      );
    }
  }

  // 3. Planned Start Week (Release Date)
  for (const acc of evalAccesses) {
    const act = activityMap.get(acc.activity_id);
    if (act && act.planned_start_week && acc.week < act.planned_start_week) {
      addConflict(
        acc.activity_id,
        'planned_start',
        `Access in Week ${acc.week} precedes planned release week ${act.planned_start_week}`,
        'error',
        { week: acc.week }
      );
    }
  }

  // 4. Scenario A ECLO Prohibition
  if (scenario === 'A') {
    for (const acc of evalAccesses) {
      if (acc.eclo === 1 || acc.eclo === true) {
        addConflict(
          acc.activity_id,
          'eclo',
          'Scenario A strictly forbids Early Closure / Late Opening (ECLO)',
          'error',
          { week: acc.week }
        );
      }
    }
  }

  // 5. Co-Sharing Legality Mix in Location-Week Possession Groups
  // Group by (location_id, week, co_share_group)
  const groupMembers = new Map(); // key: `${loc}_${week}_${group}` -> Set of activity_ids
  for (const occ of evalOccupancies) {
    const grp = occ.co_share_group || 'SOLO';
    const key = `${occ.location_id}_${occ.week}_${grp}`;
    if (!groupMembers.has(key)) groupMembers.set(key, new Set());
    groupMembers.get(key).add(occ.activity_id);
  }

  for (const [key, actIdSet] of groupMembers.entries()) {
    const [locId, weekStr, grpName] = key.split('_');
    const actIds = Array.from(actIdSet);
    if (actIds.length <= 1) continue; // Solo is always legal

    let pmCount = 0;
    let pcCount = 0;
    let cCount = 0;

    for (const aid of actIds) {
      const act = activityMap.get(aid);
      const accessType = act?.access_type || 'PC';
      if (accessType === 'PM') pmCount++;
      else if (accessType === 'PC') pcCount++;
      else cCount++;
    }

    const isLegal =
      (pmCount === 1 && pcCount === 0 && cCount === 0) ||
      (pmCount === 0 && pcCount <= 1 && (pcCount + cCount) <= 4);

    if (!isLegal) {
      const reason = pcCount > 1
        ? `Two PCs cannot share group (${pcCount} PCs detected)`
        : pmCount > 0
        ? `Plant Solo (PM) cannot share with any other activity`
        : `Group capacity exceeded: ${pcCount + cCount} activities (max 4 C)`;

      for (const aid of actIds) {
        addConflict(
          aid,
          'legal_mix',
          `Illegal co-share in group #${grpName} at ${locId}: ${reason}`,
          'error',
          { locationId: locId, week: Number(weekStr), group: grpName }
        );
      }
    }
  }

  // 6. Location Supply Capacity
  // Count distinct co-share groups at location for each week
  const locWeekGroups = new Map(); // key: `${loc}_${week}` -> Set of co_share_groups
  for (const occ of evalOccupancies) {
    const grp = occ.co_share_group || 'SOLO';
    const key = `${occ.location_id}_${occ.week}`;
    if (!locWeekGroups.has(key)) locWeekGroups.set(key, new Set());
    locWeekGroups.get(key).add(grp);
  }

  for (const [key, groups] of locWeekGroups.entries()) {
    const [locId, weekStr] = key.split('_');
    const loc = locationMap.get(locId);
    const nominalSupply = loc?.supply_capacity ?? 2;
    const allowedCapacity = scenario === 'C' ? nominalSupply + 1 : nominalSupply;
    if (groups.size > allowedCapacity) {
      // Find activities at this location & week
      const affectedActs = evalOccupancies
        .filter(o => o.location_id === locId && String(o.week) === weekStr)
        .map(o => o.activity_id);
      for (const aid of new Set(affectedActs)) {
        addConflict(
          aid,
          'capacity',
          `Location capacity exceeded at ${locId}: ${groups.size} groups > ${allowedCapacity} cap`,
          'error',
          { locationId: locId, week: Number(weekStr) }
        );
      }
    }
  }

  // 7. Precedence Constraints across all weeks
  const actWeekExtents = new Map();
  for (const acc of accesses) {
    if (!actWeekExtents.has(acc.activity_id)) {
      actWeekExtents.set(acc.activity_id, { minWeek: acc.week, maxWeek: acc.week });
    } else {
      const ext = actWeekExtents.get(acc.activity_id);
      ext.minWeek = Math.min(ext.minWeek, acc.week);
      ext.maxWeek = Math.max(ext.maxWeek, acc.week);
    }
  }

  for (const act of activities) {
    if (!act.predecessor_activity_id) continue;
    const predExt = actWeekExtents.get(act.predecessor_activity_id);
    const succExt = actWeekExtents.get(act.activity_id);
    if (predExt && succExt && succExt.minWeek <= predExt.maxWeek) {
      addConflict(
        act.activity_id,
        'precedence',
        `Precedence violation: starts in Week ${succExt.minWeek}, but predecessor ${act.predecessor_activity_id} finishes in Week ${predExt.maxWeek}`,
        'error',
        { predecessor: act.predecessor_activity_id }
      );
    }
  }

  return {
    hasConflicts: issues.length > 0,
    totalConflicts: issues.length,
    issues,
    activityConflicts,
  };
}


/**
 * Evaluates candidate drop targets for a moving job across visible matrix cells.
 * Returns an object mapping cell keys `${locationId}_N${night}` to:
 * { canDrop: boolean, reason?: string }
 */
export function computeValidDropTargets({
  draggingJob,
  activeWeek,
  accesses = [],
  occupancies = [],
  activities = [],
  contracts = [],
  locations = [],
  scenario = 'A',
}) {
  if (!draggingJob) return {};

  const activityMap = new Map(activities.map(a => [a.activity_id, a]));
  const contractMap = new Map(contracts.map(c => [c.contract_number, c]));

  const act = activityMap.get(draggingJob.activity_id);
  const contract = contractMap.get(act?.contract_number);
  const maxNights = contract?.number_of_maximum_access_per_week ?? 7;
  const maxWorkfronts = contract?.number_of_workfronts ?? 2;
  const accessType = act?.access_type || draggingJob.access_type || 'PC';

  // Other accesses in the active week (excluding the dragging job)
  const otherWeekAccesses = accesses.filter(
    a => a.week === activeWeek && a.activity_id !== draggingJob.activity_id
  );

  // Pre-calculate workfront counts for this contract on each night N1..N7
  const workfrontCountsPerNight = {};
  for (let n = 1; n <= 7; n++) {
    workfrontCountsPerNight[n] = otherWeekAccesses.filter(
      a => {
        const otherAct = activityMap.get(a.activity_id);
        return (otherAct?.contract_number || a.contract_number) === act?.contract_number && a.access_night === n;
      }
    ).length;
  }

  const targets = {};

  for (const loc of locations) {
    const locId = loc.sector_id || loc.location_id;

    for (let night = 1; night <= 7; night++) {
      const cellKey = `${locId}_N${night}`;

      // 1. Weekly allocation night cap (Kc)
      if (night > maxNights) {
        targets[cellKey] = {
          canDrop: false,
          reason: `Night N${night} exceeds max allocation cap (${maxNights}) for ${act?.contract_number}`,
        };
        continue;
      }

      // 2. Workfront limit for this contract on this night
      const currentWf = workfrontCountsPerNight[night] || 0;
      if (currentWf >= maxWorkfronts) {
        targets[cellKey] = {
          canDrop: false,
          reason: `Workfront capacity full for ${act?.contract_number} on Night N${night} (${currentWf}/${maxWorkfronts})`,
        };
        continue;
      }

      // 3. Planned Start Week
      if (act?.planned_start_week && activeWeek < act.planned_start_week) {
        targets[cellKey] = {
          canDrop: false,
          reason: `Week ${activeWeek} precedes release week ${act.planned_start_week}`,
        };
        continue;
      }

      // 4. Scenario A ECLO ban
      if (scenario === 'A' && (night === 5 || night === 6) && draggingJob.eclo) {
        targets[cellKey] = {
          canDrop: false,
          reason: 'Scenario A strictly forbids ECLO access',
        };
        continue;
      }

      // All hard checks passed: valid drop slot!
      targets[cellKey] = {
        canDrop: true,
      };
    }
  }

  return targets;
}
