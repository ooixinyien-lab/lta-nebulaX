import '@testing-library/jest-dom';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CalendarPage from '../pages/CalendarPage';
import * as calendarApi from '../services/calendarApi';

vi.mock('../services/calendarApi', () => ({
  getAuthConfig: vi.fn(),
  getCalendarPreviewContext: vi.fn(),
  autoAssignActualNights: vi.fn(),
  getCalendarisation: vi.fn(),
}));

const mockAssignment = {
  access_id: 'bundle-1:A001:1',
  activity_id: 'A001',
  access_seq: 1,
  week: 1,
  access_night: 1,
  eclo: false,
  service_date: '2027-01-06',
  global_night_id: 'calendar:2027-01-06',
  contract_number: 'C001',
  contract_description: 'Test contract',
  line_codes: ['ALP'],
  location_ids: ['SEC:ALP:S01_S02'],
};

const mockSucceededAttempt = {
  attempt_id: 'att-100',
  status: 'SUCCEEDED',
  solver_status: 'OPTIMAL',
  complete: true,
  bundle_id: 'bundle-1',
  calendar_revision_id: 'cal-1',
  horizon_start: '2027-01-04',
  horizon_end: '2027-08-01',
  horizon_weeks: 30,
  scenario: 'A',
  assumed_calendar: true,
  assumptions: ['Demo assumption 1'],
  conflicts: [],
  assignments: [mockAssignment],
};

describe('CalendarPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    calendarApi.getAuthConfig.mockResolvedValue({
      auth_mode: 'demo',
      demo_users: [
        { id: 'demo-track', name: 'Track team', role: 'requester' },
        { id: 'demo-officer', name: 'Planning officer', role: 'officer' },
      ],
    });
    calendarApi.getCalendarPreviewContext.mockResolvedValue({
      bundle: null,
      calendar: null,
      latest_attempt_id: null,
      last_complete_attempt_id: null,
    });
  });

  it('renders simplified workflow with Planning officer and scenario toggle controls', async () => {
    render(<CalendarPage onBack={vi.fn()} />);

    expect(await screen.findByText('Planning officer')).toBeInTheDocument();
    expect(screen.getByText('Source:')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /select \/outputs\/a/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /select \/outputs\/b/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /select \/outputs\/c/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /assign actual nights/i })).toBeEnabled();

    // Verify all removed setup inputs are absent
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/demo profile/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/instance revision/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/solver output csv/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/calendar json/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /import outputs/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /create demo calendar/i })).not.toBeInTheDocument();
  });

  it('assigns actual nights in one click and renders week calendar via polling', async () => {
    calendarApi.autoAssignActualNights.mockResolvedValue({
      attempt_id: 'att-100',
      status: 'QUEUED',
      bundle_id: 'bundle-1',
      calendar_revision_id: 'cal-1',
    });
    calendarApi.getCalendarisation.mockResolvedValue(mockSucceededAttempt);

    render(<CalendarPage onBack={vi.fn()} />);

    const assignButton = await screen.findByRole('button', { name: /assign actual nights/i });
    fireEvent.click(assignButton);

    await waitFor(() => {
      expect(calendarApi.autoAssignActualNights).toHaveBeenCalledWith('demo-officer', 'A');
    });

    expect(await screen.findByText('Actual nights assigned.')).toBeInTheDocument();
    expect(screen.getByText('A001')).toBeInTheDocument();
    expect(screen.getByText('C001')).toBeInTheDocument();
    expect(screen.getByText('Wednesday')).toBeInTheDocument();
    expect(screen.getByText('Optimal')).toBeInTheDocument();
    expect(screen.getByText('Assumed demo calendar')).toBeInTheDocument();
  });

  it('toggles between /outputs/A, /outputs/B, and /outputs/C and loads respective context', async () => {
    calendarApi.autoAssignActualNights.mockResolvedValue({
      attempt_id: 'att-200',
      status: 'QUEUED',
      bundle_id: 'bundle-2',
      calendar_revision_id: 'cal-2',
    });
    render(<CalendarPage onBack={vi.fn()} />);

    const btnB = await screen.findByRole('button', { name: /select \/outputs\/b/i });
    fireEvent.click(btnB);

    await waitFor(() => {
      expect(calendarApi.getCalendarPreviewContext).toHaveBeenCalledWith('demo-officer', null, 'B');
    });

    const assignButton = screen.getByRole('button', { name: /assign actual nights/i });
    fireEvent.click(assignButton);

    await waitFor(() => {
      expect(calendarApi.autoAssignActualNights).toHaveBeenCalledWith('demo-officer', 'B');
    });
  });

  it('restores previous successful calendar when a retry fails', async () => {
    calendarApi.autoAssignActualNights.mockResolvedValueOnce({
      attempt_id: 'att-100',
      status: 'QUEUED',
    });
    calendarApi.getCalendarisation.mockResolvedValueOnce(mockSucceededAttempt);

    render(<CalendarPage onBack={vi.fn()} />);

    const assignButton = await screen.findByRole('button', { name: /assign actual nights/i });
    fireEvent.click(assignButton);

    expect(await screen.findByText('A001')).toBeInTheDocument();

    // Now trigger a failed retry
    calendarApi.autoAssignActualNights.mockResolvedValueOnce({
      attempt_id: 'att-failed',
      status: 'QUEUED',
    });
    calendarApi.getCalendarisation.mockResolvedValueOnce({
      attempt_id: 'att-failed',
      status: 'SUCCEEDED',
      solver_status: 'PRECHECK_FAILED',
      complete: false,
      conflicts: [
        {
          rule_code: 'SHARING_EXCEEDS_WORKFRONTS',
          message: 'Workfront limit exceeded for contract C006',
        },
      ],
      assignments: [],
    });

    fireEvent.click(assignButton);

    await waitFor(() => {
      expect(screen.getByText(/Workfront limit exceeded/)).toBeInTheDocument();
    });

    // The previous successful calendar is retained!
    expect(screen.getByText('A001')).toBeInTheDocument();
    expect(screen.getByText('C001')).toBeInTheDocument();
  });

  it('restores last completed attempt automatically on page load', async () => {
    calendarApi.getCalendarPreviewContext.mockResolvedValue({
      bundle: null,
      calendar: null,
      latest_attempt_id: 'att-100',
      last_complete_attempt_id: 'att-100',
    });
    calendarApi.getCalendarisation.mockResolvedValue(mockSucceededAttempt);

    render(<CalendarPage onBack={vi.fn()} />);

    expect(await screen.findByText('A001')).toBeInTheDocument();
    expect(screen.getByText('Actual nights assigned.')).toBeInTheDocument();
    expect(calendarApi.getCalendarisation).toHaveBeenCalledWith('att-100', 'demo-officer');
  });
});
