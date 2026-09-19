import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ScheduleDashboard from '../ScheduleDashboard';
import { computeValidDropTargets } from '../services/conflictChecker';

const sampleDisplayData = {
  identity: { mode: 'requirements', scenario: 'A' },
  horizon_start: '2027-01-04',
  locations: [
    { location_id: 'SEC:BET:S01_S02', sector_id: 'SEC:BET:S01_S02', supply_capacity: 4 },
  ],
  sectors: [
    { sector_id: 'SEC:BET:S01_S02', line_code: 'BET', from_station_id: 'S01', to_station_id: 'S02' },
  ],
  activities: [
    { activity_id: 'ACT-001', contract_number: 'C001', start_location_id: 'SEC:BET:S01_S02', access_type: 'PM' },
    { activity_id: 'ACT-002', contract_number: 'C001', start_location_id: 'SEC:BET:S01_S02', access_type: 'PM' },
    { activity_id: 'ACT-003', contract_number: 'C001', start_location_id: 'SEC:BET:S01_S02', access_type: 'PM' },
    { activity_id: 'ACT-THU', contract_number: 'C002', start_location_id: 'SEC:BET:S01_S02', access_type: 'PM' },
    { activity_id: 'ACT-SUN', contract_number: 'C002', start_location_id: 'SEC:BET:S01_S02', access_type: 'PM' },
  ],
  contracts: [
    { contract_number: 'C001', number_of_maximum_access_per_week: 3, number_of_workfronts: 2, access_type: 'PM' },
    { contract_number: 'C002', number_of_maximum_access_per_week: 3, number_of_workfronts: 2, access_type: 'PM' },
  ],
  accesses: [
    { activity_id: 'ACT-001', access_seq: 1, week: 1, access_night: 1, eclo: 0, service_date: '2027-01-04', day_of_week: 1 },
    { activity_id: 'ACT-002', access_seq: 1, week: 1, access_night: 2, eclo: 0, service_date: '2027-01-05', day_of_week: 2 },
    { activity_id: 'ACT-003', access_seq: 1, week: 1, access_night: 3, eclo: 0, service_date: '2027-01-06', day_of_week: 3 },
    { activity_id: 'ACT-THU', access_seq: 1, week: 1, access_night: 1, eclo: 0, service_date: '2027-01-07', day_of_week: 4 },
    { activity_id: 'ACT-SUN', access_seq: 1, week: 1, access_night: 2, eclo: 0, service_date: '2027-01-10', day_of_week: 7 },
  ],
  occupancies: [
    { activity_id: 'ACT-001', week: 1, location_id: 'SEC:BET:S01_S02', co_share_group: 'G1' },
    { activity_id: 'ACT-002', week: 1, location_id: 'SEC:BET:S01_S02', co_share_group: 'G2' },
    { activity_id: 'ACT-003', week: 1, location_id: 'SEC:BET:S01_S02', co_share_group: 'G3' },
    { activity_id: 'ACT-THU', week: 1, location_id: 'SEC:BET:S01_S02', co_share_group: 'G4' },
    { activity_id: 'ACT-SUN', week: 1, location_id: 'SEC:BET:S01_S02', co_share_group: 'G5' },
  ],
};

describe('ScheduleDashboard Calendar Grid Requirements', () => {
  it('renders 3 access night columns in PS1 Requirements view', () => {
    render(
      <ScheduleDashboard
        displayData={sampleDisplayData}
        mode="requirements"
        week={1}
      />
    );

    // Header checks
    expect(screen.getByText('Access night 1')).toBeInTheDocument();
    expect(screen.getByText('Access night 2')).toBeInTheDocument();
    expect(screen.getByText('Access night 3')).toBeInTheDocument();
    expect(screen.queryByText('Thursday (N4)')).toBeNull();
    expect(screen.queryByText('Sunday (N7)')).toBeNull();
    expect(screen.getAllByText('Contract/type weekly index — not a weekday')).toHaveLength(3);

    // In PS1 mode, activities are filtered by access_night (1, 2, 3)
    expect(screen.getByText('ACT-001')).toBeInTheDocument();
    expect(screen.getByText('ACT-002')).toBeInTheDocument();
    expect(screen.getByText('ACT-003')).toBeInTheDocument();
  });

  it('renders 7 weekday columns with balanced distribution in Operations view', () => {
    const operationalData = {
      ...sampleDisplayData,
      identity: { mode: 'operations', scenario: 'A' },
    };

    render(
      <ScheduleDashboard
        displayData={operationalData}
        mode="operations"
        week={1}
      />
    );

    // Header checks: all 7 days of the week are visible
    expect(screen.getByText('Monday (N1)')).toBeInTheDocument();
    expect(screen.getByText('Tuesday (N2)')).toBeInTheDocument();
    expect(screen.getByText('Wednesday (N3)')).toBeInTheDocument();
    expect(screen.getByText('Thursday (N4)')).toBeInTheDocument();
    expect(screen.getByText('Friday (N5)')).toBeInTheDocument();
    expect(screen.getByText('Saturday (N6)')).toBeInTheDocument();
    expect(screen.getByText('Sunday (N7)')).toBeInTheDocument();
    expect(screen.getAllByText('Operational service day')).toHaveLength(7);

    // In operations mode, activities scheduled on Thursday and Sunday appear under those days
    expect(screen.getByText('ACT-THU')).toBeInTheDocument();
    expect(screen.getByText('ACT-SUN')).toBeInTheDocument();

    // Clicking an activity opens the Inspector drawer with weekday details
    fireEvent.click(screen.getByText('ACT-THU'));
    expect(screen.getByText('Scheduled Day:')).toBeInTheDocument();
    expect(screen.getByText(/2027-01-07 \(Thursday\)/)).toBeInTheDocument();
  });
});

describe('conflictChecker drop target validation', () => {
  it('disallows drop on night > maxNights in PS1 requirements mode', () => {
    const targets = computeValidDropTargets({
      draggingJob: sampleDisplayData.activities[0],
      activeWeek: 1,
      accesses: sampleDisplayData.accesses,
      activities: sampleDisplayData.activities,
      contracts: sampleDisplayData.contracts,
      locations: sampleDisplayData.locations,
      scenario: 'A',
      isPs1Schedule: true,
    });

    // Contract C001 has maxNights = 3
    expect(targets['SEC:BET:S01_S02_N1'].canDrop).toBe(true);
    expect(targets['SEC:BET:S01_S02_N3'].canDrop).toBe(true);
    expect(targets['SEC:BET:S01_S02_N4'].canDrop).toBe(false);
    expect(targets['SEC:BET:S01_S02_N4'].reason).toContain('exceeds max allocation cap');
  });

  it('allows drop on Thursday..Sunday in Operations mode', () => {
    const targets = computeValidDropTargets({
      draggingJob: sampleDisplayData.activities[0],
      activeWeek: 1,
      accesses: sampleDisplayData.accesses,
      activities: sampleDisplayData.activities,
      contracts: sampleDisplayData.contracts,
      locations: sampleDisplayData.locations,
      scenario: 'A',
      isPs1Schedule: false,
    });

    // In operations mode, day 4 (Thursday), day 5 (Friday), day 7 (Sunday) can be dropped onto
    expect(targets['SEC:BET:S01_S02_N4'].canDrop).toBe(true);
    expect(targets['SEC:BET:S01_S02_N5'].canDrop).toBe(true);
    expect(targets['SEC:BET:S01_S02_N7'].canDrop).toBe(true);
  });
});
