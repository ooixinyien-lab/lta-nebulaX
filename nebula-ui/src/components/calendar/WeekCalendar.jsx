import { addDays, parseDateOnly } from './dateUtils';

const labelDate = (value) => parseDateOnly(value).toLocaleDateString('en-SG', {
  day: 'numeric',
  month: 'short',
});

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export default function WeekCalendar({ horizonStart, week, assignments }) {
  if (!horizonStart) return null;
  const weekStart = addDays(horizonStart, (week - 1) * 7);
  const dates = DAYS.map((name, offset) => ({ name, date: addDays(weekStart, offset) }));

  return (
    <div className="week-calendar" aria-label={`Calendar week ${week}`}>
      {dates.map(({ name, date }) => {
        const rows = assignments.filter((item) => item.service_date === date);
        return (
          <section className="calendar-day" key={date}>
            <header>
              <strong>{name}</strong>
              <span>{labelDate(date)}</span>
            </header>
            <div className="calendar-day__entries">
              {rows.length === 0 && <p className="calendar-empty">No activities</p>}
              {rows.map((row) => (
                <article className="calendar-access" key={row.access_id}>
                  <div className="calendar-access__title">
                    <strong>{row.activity_id}</strong>
                    {row.eclo && <span className="eclo-badge">ECLO</span>}
                  </div>
                  <span>{row.contract_number}</span>
                  <details>
                    <summary>Details</summary>
                    <p>Local access index: {row.access_night}</p>
                    <p>Lines: {row.line_codes.join(', ')}</p>
                    <p>Locations: {row.location_ids.join(', ')}</p>
                  </details>
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
