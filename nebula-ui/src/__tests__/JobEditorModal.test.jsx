import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import JobEditorModal from '../components/jobs/JobEditorModal';
import SpatialFootprintSelector from '../components/jobs/SpatialFootprintSelector';
import PreflightCheckDrawer from '../components/jobs/PreflightCheckDrawer';
import {
  calculateSafetyBuffer,
  validateJobForm,
  generateJobId,
  runClientSidePreflightHeuristic,
  JOB_SOURCES,
} from '../components/jobs/jobFormConstants';

describe('jobFormConstants & Validation Helpers', () => {
  it('generates proper job ID prefixes based on category', () => {
    const emgId = generateJobId(JOB_SOURCES.EMERGENCY, []);
    expect(emgId).toMatch(/^EMG-\d{8}-\d{2}$/);

    const prjId = generateJobId(JOB_SOURCES.PROJECT, [{ id: '1' }]);
    expect(prjId).toBe('PRJ-002');

    const mntId = generateJobId(JOB_SOURCES.ROUTINE, []);
    expect(mntId).toBe('MNT-001');
  });

  it('calculates safety buffer for HEAVY vs MEDIUM vs LIGHT work', () => {
    const heavyBuffer = calculateSafetyBuffer('HEAVY', 'BOTH', 'NSL', 'NS1', 'NS3');
    expect(heavyBuffer.bufferSectors).toBe(2);
    expect(heavyBuffer.mirrorOppositeBound).toBe(true);
    expect(heavyBuffer.badgeText).toContain('+2 buffer sectors');

    const mediumBuffer = calculateSafetyBuffer('MEDIUM', 'EB', 'NSL', 'NS1', 'NS3');
    expect(mediumBuffer.bufferSectors).toBe(1);
    expect(mediumBuffer.mirrorOppositeBound).toBe(false);

    const lightBuffer = calculateSafetyBuffer('LIGHT', 'EB', 'NSL', 'NS1', 'NS3');
    expect(lightBuffer.bufferSectors).toBe(0);
  });

  it('validates required fields and hard deadline rules for emergency jobs', () => {
    // Valid standard job
    const validJob = {
      id: 'PRJ-001',
      category: JOB_SOURCES.PROJECT,
      contract_number: 'C06',
      line_code: 'NSL',
      start_location_id: 'NS1',
      end_location_id: 'NS4',
      total_accesses: 3,
      max_accesses_per_week: 3,
      planned_start_date: '2027-02-01',
      planned_completion_date: '2027-02-28',
    };
    const res1 = validateJobForm(validJob);
    expect(res1.isValid).toBe(true);

    // Emergency job missing hard deadline
    const emgJobNoHard = {
      ...validJob,
      category: JOB_SOURCES.EMERGENCY,
      hard_completion_date: '',
    };
    const res2 = validateJobForm(emgJobNoHard);
    expect(res2.isValid).toBe(false);
    expect(res2.errors.hard_completion_date).toBeDefined();

    // Inverted start/end dates
    const invertedJob = {
      ...validJob,
      planned_start_date: '2027-03-01',
      planned_completion_date: '2027-02-01',
    };
    const res3 = validateJobForm(invertedJob);
    expect(res3.isValid).toBe(false);
    expect(res3.errors.planned_completion_date).toBeDefined();
  });

  it('triggers precedence warning when prerequisite completes after planned start', () => {
    const existingJobs = [
      { id: 'JOB-PRED', title: 'Civil Foundation', completionDate: '2027-02-15' },
    ];
    const jobWithPredConflict = {
      id: 'PRJ-002',
      category: JOB_SOURCES.PROJECT,
      contract_number: 'C06',
      line_code: 'NSL',
      start_location_id: 'NS1',
      end_location_id: 'NS4',
      total_accesses: 3,
      max_accesses_per_week: 3,
      planned_start_date: '2027-02-10', // Starts before prerequisite finishes!
      planned_completion_date: '2027-03-01',
      predecessor_job_id: 'JOB-PRED',
    };
    const res = validateJobForm(jobWithPredConflict, existingJobs);
    expect(res.warnings.precedence).toContain('Prerequisite completes after planned start date');
  });

  it('runs client-side preflight check heuristics', () => {
    const job = {
      id: 'PRJ-001',
      category: JOB_SOURCES.PROJECT,
      contract_number: 'C06',
      nature_of_works: 'HEAVY',
      line_code: 'NSL',
      start_location_id: 'NS1',
      end_location_id: 'NS4',
      total_accesses: 4,
      planned_start_date: '2027-02-01',
      planned_completion_date: '2027-03-01',
    };
    const check = runClientSidePreflightHeuristic(job);
    expect(check.status).toBe('PASSED');
    expect(check.ruleBreakdown.length).toBeGreaterThan(0);
    expect(check.metrics.bufferHaloSectors).toBe(2);
  });
});

describe('SpatialFootprintSelector Component', () => {
  it('renders line selector, station dropdowns, and dynamic buffer alert box', () => {
    const formData = {
      line_code: 'NSL',
      start_location_id: 'NS1',
      end_location_id: 'NS4',
      track_bound: 'BOTH',
      access_mode: 'EXCLUSIVE',
      nature_of_works: 'HEAVY',
    };
    const handleChange = vi.fn();
    const handleSelectOnMap = vi.fn();

    render(
      <SpatialFootprintSelector
        formData={formData}
        onChange={handleChange}
        onSelectOnMap={handleSelectOnMap}
      />
    );

    expect(screen.getByText(/Railway Line Corridor/i)).toBeDefined();
    expect(screen.getByText(/Possession Geographical Extents/i)).toBeDefined();
    expect(screen.getByText(/Dual-bound lockout active/i)).toBeDefined();
    expect(screen.getByText(/Eastbound \(EB\)/i)).toBeDefined();
    expect(screen.getByText(/Westbound \(WB\)/i)).toBeDefined();
  });

  it('calls onSelectOnMap when Pick on Map is clicked', () => {
    const formData = {
      line_code: 'NSL',
      start_location_id: 'NS1',
      end_location_id: 'NS4',
      track_bound: 'BOTH',
      access_mode: 'EXCLUSIVE',
      nature_of_works: 'LIGHT',
    };
    const handleChange = vi.fn();
    const handleSelectOnMap = vi.fn();

    render(
      <SpatialFootprintSelector
        formData={formData}
        onChange={handleChange}
        onSelectOnMap={handleSelectOnMap}
      />
    );

    const mapPickButtons = screen.getAllByText(/Pick on Map/i);
    expect(mapPickButtons.length).toBe(2);
    fireEvent.click(mapPickButtons[0]);
    expect(handleSelectOnMap).toHaveBeenCalledWith('start_location_id');
  });
});

describe('PreflightCheckDrawer Component', () => {
  it('renders passed status and metric cards', () => {
    const result = {
      status: 'PASSED',
      timestamp: '14:20:00',
      metrics: {
        disruptionScore: 4.2,
        displacedVisits: 0,
        bufferHaloSectors: 2,
        capacityPeakRatio: '42%',
      },
      ruleBreakdown: [
        { rule: 'Capacity Check', severity: 'success', detail: 'Sufficient possession capacity' },
        { rule: 'Buffer Conflict', severity: 'success', detail: 'No overlapping heavy works' },
      ],
    };

    render(<PreflightCheckDrawer result={result} isOpen={true} />);

    expect(screen.getByText(/SCHEDULE INSERTION FEASIBLE/i)).toBeDefined();
    expect(screen.getByText('4.2 pts')).toBeDefined();
    expect(screen.getByText('+2 Sectors')).toBeDefined();
    expect(screen.getByText(/Sufficient possession capacity/i)).toBeDefined();
  });

  it('renders hard conflict notice and error styling when conflict occurs', () => {
    const result = {
      status: 'HARD CONFLICT',
      hardConflictReason: 'Prerequisite completes after proposed start date.',
      ruleBreakdown: [
        { rule: 'Precedence Check', severity: 'error', detail: 'HARD CONFLICT: Dependency violation' },
      ],
    };

    render(<PreflightCheckDrawer result={result} isOpen={true} />);

    expect(screen.getByText(/HARD CONFLICT DETECTED/i)).toBeDefined();
    expect(screen.getByText(/Blocker Notice/i)).toBeDefined();
    expect(screen.getByText(/Prerequisite completes after proposed start date/i)).toBeDefined();
  });
});

describe('JobEditorModal Component', () => {
  it('renders modal dialog when isOpen is true and switches tabs', () => {
    const onClose = vi.fn();
    const onSubmit = vi.fn();

    render(
      <JobEditorModal
        isOpen={true}
        onClose={onClose}
        onSubmit={onSubmit}
        existingJobs={[]}
      />
    );

    expect(screen.getByText(/New Track Possession Job/i)).toBeDefined();
    expect(screen.getAllByText(/PROJECT ADDITION/i).length).toBeGreaterThan(0);

    // Switch to Spatial tab
    fireEvent.click(screen.getByText(/2\. Spatial Footprint/i));
    expect(screen.getByText(/Railway Line Corridor/i)).toBeDefined();

    // Switch to Timing tab
    fireEvent.click(screen.getByText(/3\. Timing & Workload/i));
    expect(screen.getByText(/Earliest Start Date/i)).toBeDefined();

    // Switch to Dependencies tab
    fireEvent.click(screen.getByText(/4\. Precedence/i));
    expect(screen.getByText(/Prerequisite Job/i)).toBeDefined();

    // Switch to Priority tab
    fireEvent.click(screen.getByText(/5\. Priority & Impact/i));
    expect(screen.getByText(/Activity Operational Priority/i)).toBeDefined();
  });

  it('switches to urgent theme and requires hard deadline when Emergency Repair selected', () => {
    render(
      <JobEditorModal
        isOpen={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    const emergencyButton = screen.getByRole('button', { name: /Emergency Repair/i });
    fireEvent.click(emergencyButton);

    expect(screen.getByText(/Urgent Emergency Mode Active/i)).toBeDefined();
    expect(screen.getAllByText(/EMERGENCY REPAIR/i).length).toBeGreaterThan(0);
  });


  it('runs preflight check when Run Preflight Check is clicked', async () => {
    render(
      <JobEditorModal
        isOpen={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    const runCheckBtn = screen.getByRole('button', { name: /Run Preflight Check/i });
    fireEvent.click(runCheckBtn);

    await waitFor(() => {
      expect(screen.getByText(/PREFLIGHT ENGINE CHECK/i)).toBeDefined();
    });
  });
});
