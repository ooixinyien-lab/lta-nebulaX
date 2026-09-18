import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import WeekCalendar from '../components/calendar/WeekCalendar';
import { addDays } from '../components/calendar/dateUtils';

const assignment = {
  access_id: 'bundle:A001:1',
  activity_id: 'A001',
  access_seq: 1,
  week: 1,
  access_night: 1,
  eclo: false,
  service_date: '2027-01-06',
  global_night_id: 'calendar:2027-01-06',
  contract_number: 'C001',
  contract_description: 'Test',
  line_codes: ['ALP'],
  location_ids: ['L1'],
};

describe('WeekCalendar', () => {
  it('renders actual weekdays separately from the local access index', () => {
    render(
      <WeekCalendar
        horizonStart="2027-01-04"
        week={1}
        assignments={[assignment]}
      />,
    );
    expect(screen.getByText('Wednesday')).toBeInTheDocument();
    expect(screen.getByText('A001')).toBeInTheDocument();
    expect(screen.getByText('Local access index: 1')).toBeInTheDocument();
    expect(screen.getAllByText('No activities')).toHaveLength(6);
  });

  it('handles Sunday and month boundaries as date-only values', () => {
    expect(addDays('2027-01-31', 1)).toBe('2027-02-01');
    render(
      <WeekCalendar
        horizonStart="2027-01-04"
        week={1}
        assignments={[{ ...assignment, service_date: '2027-01-10' }]}
      />,
    );
    expect(screen.getByText('Sunday')).toBeInTheDocument();
    expect(screen.getByText('10 Jan')).toBeInTheDocument();
  });
});
