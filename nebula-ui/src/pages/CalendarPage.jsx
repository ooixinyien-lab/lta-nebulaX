import { useEffect, useState } from 'react';
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react';
import WeekCalendar from '../components/calendar/WeekCalendar';
import { addDays, parseDateOnly } from '../components/calendar/dateUtils';
import {
  autoAssignActualNights,
  getAuthConfig,
  getCalendarisation,
  getCalendarPreviewContext,
} from '../services/calendarApi';
import '../styles/calendar.css';

const formatRange = (startDateStr) => {
  if (!startDateStr) return '';
  const start = parseDateOnly(startDateStr);
  const end = parseDateOnly(addDays(startDateStr, 6));
  const startPart = start.toLocaleDateString('en-SG', { day: 'numeric', month: 'short' });
  const endPart = end.toLocaleDateString('en-SG', { day: 'numeric', month: 'short', year: 'numeric' });
  return `${startPart} – ${endPart}`;
};

export default function CalendarPage({ onBack }) {
  const [identity, setIdentity] = useState('');
  const [selectedScenario, setSelectedScenario] = useState('A');
  const [attempt, setAttempt] = useState(null);
  const [lastComplete, setLastComplete] = useState(null);
  const [week, setWeek] = useState(1);
  const [status, setStatus] = useState('Ready to assign actual nights from /outputs/A.');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [authLoaded, setAuthLoaded] = useState(false);

  const isPolling = Boolean(attempt?.attempt_id && ['QUEUED', 'RUNNING'].includes(attempt.status));
  const busy = isSubmitting || isPolling;

  useEffect(() => {
    let isMounted = true;
    getAuthConfig()
      .then((config) => {
        if (!isMounted) return;
        let officerId = '';
        if (config.auth_mode === 'demo') {
          const officer = config.demo_users?.find((user) => user.role === 'officer');
          officerId = officer?.id || 'demo-officer';
          setIdentity(officerId);
        }
        setAuthLoaded(true);
      })
      .catch((error) => {
        if (isMounted) {
          setStatus(error.message);
          setAuthLoaded(true);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!authLoaded) return;
    let isMounted = true;

    getCalendarPreviewContext(identity, null, selectedScenario)
      .then(async (context) => {
        if (!isMounted) return;
        if (context.last_complete_attempt_id) {
          const lastResult = await getCalendarisation(context.last_complete_attempt_id, identity);
          if (!isMounted) return;
          setLastComplete(lastResult);
          setStatus(
            lastResult.complete
              ? 'Actual nights assigned.'
              : 'No complete mapping was produced for this fixed schedule and calendar.'
          );
        } else if (context.latest_attempt_id) {
          const latestResult = await getCalendarisation(context.latest_attempt_id, identity);
          if (!isMounted) return;
          setAttempt(latestResult);
          if (latestResult.complete) {
            setLastComplete(latestResult);
            setStatus('Actual nights assigned.');
          } else {
            setStatus('No complete mapping was produced for this fixed schedule and calendar.');
          }
        } else {
          setStatus(`Ready to assign actual nights from /outputs/${selectedScenario}.`);
        }
      })
      .catch(() => {
        if (isMounted) {
          setStatus(`Ready to assign actual nights from /outputs/${selectedScenario}.`);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [authLoaded, identity, selectedScenario]);

  useEffect(() => {
    if (!isPolling) {
      return undefined;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const latest = await getCalendarisation(attempt.attempt_id, identity);
        if (cancelled) return;
        setAttempt(latest);
        if (latest.complete) {
          setLastComplete(latest);
        }
        if (latest.status === 'SUCCEEDED') {
          setStatus(
            latest.complete
              ? 'Actual nights assigned.'
              : 'No complete mapping was produced for this fixed schedule and calendar.'
          );
        } else if (latest.status === 'FAILED') {
          setStatus(latest.error_message || 'Calendar assignment failed.');
        }
      } catch (error) {
        if (!cancelled) {
          setStatus(error.message);
        }
      }
    };
    poll();
    const timer = window.setInterval(poll, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [isPolling, attempt?.attempt_id, identity]);

  const handleSelectScenario = (sc) => {
    if (busy || sc === selectedScenario) return;
    setAttempt(null);
    setLastComplete(null);
    setSelectedScenario(sc);
  };

  const assignNights = async () => {
    setIsSubmitting(true);
    setStatus(`Assigning actual nights from /outputs/${selectedScenario}…`);
    try {
      const queued = await autoAssignActualNights(identity, selectedScenario);
      setAttempt(queued);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const visibleResult = attempt?.complete ? attempt : lastComplete;
  const horizonWeeks = visibleResult?.horizon_weeks || 30;
  const assignments = visibleResult?.assignments || [];
  const rangeStart = visibleResult?.horizon_start
    ? addDays(visibleResult.horizon_start, (week - 1) * 7)
    : '';
  const range = formatRange(rangeStart);

  return (
    <main className="calendar-page">
      <header className="calendar-page__header">
        <div>
          <button className="calendar-link" type="button" onClick={onBack}>← Network map</button>
          <h1><CalendarDays size={24} /> Actual Night View</h1>
          <p>Read-only dates mapped onto an unchanged official solver output.</p>
        </div>
      </header>

      <section className="calendar-setup" aria-label="Calendar setup" aria-busy={busy}>
        <div className="calendar-setup__meta">
          <span className="calendar-setup__role">Planning officer</span>
          <span className="calendar-setup__sep">·</span>
          <span className="calendar-setup__source-label">Source:</span>
          <div className="calendar-scenario-toggle" role="group" aria-label="Scenario output source">
            {['A', 'B', 'C'].map((sc) => {
              const isSelected = selectedScenario === sc;
              return (
                <button
                  key={sc}
                  type="button"
                  className={`calendar-scenario-btn ${isSelected ? 'calendar-scenario-btn--active' : ''}`}
                  onClick={() => handleSelectScenario(sc)}
                  disabled={busy}
                  aria-pressed={isSelected}
                  aria-label={`Select /outputs/${sc}`}
                >
                  /outputs/{sc}
                </button>
              );
            })}
          </div>
        </div>
        <button
          className="calendar-primary"
          type="button"
          disabled={busy}
          onClick={assignNights}
        >
          Assign actual nights
        </button>
      </section>

      <section
        className={`calendar-status ${visibleResult?.complete ? 'calendar-status--ok' : ''}`}
        aria-live="polite"
      >
        <strong>{status}</strong>
        {visibleResult?.assumed_calendar && <span>Assumed demo calendar</span>}
        {visibleResult?.solver_status === 'OPTIMAL' && <span>Optimal</span>}
        {visibleResult?.solver_status === 'FEASIBLE' && <span>Automatically generated</span>}
        {attempt?.assumptions?.length > 0 && (
          <details>
            <summary>Calendar assumptions</summary>
            <ul>{attempt.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
          </details>
        )}
        {attempt?.conflicts?.length > 0 && (
          <ul>
            {attempt.conflicts.slice(0, 12).map((item, index) => (
              <li key={`${item.rule_code}-${index}`}>{item.message}</li>
            ))}
          </ul>
        )}
      </section>

      {visibleResult?.complete && (
        <section className="calendar-result">
          <div className="calendar-week-nav">
            <button
              aria-label="Previous week"
              type="button"
              disabled={week === 1}
              onClick={() => setWeek((value) => value - 1)}
            >
              <ChevronLeft size={18} />
            </button>
            <div>
              <strong>Week {week}</strong>
              <span>{range}</span>
            </div>
            <button
              aria-label="Next week"
              type="button"
              disabled={week === horizonWeeks}
              onClick={() => setWeek((value) => value + 1)}
            >
              <ChevronRight size={18} />
            </button>
          </div>
          <p className="calendar-caption">
            Scenario {visibleResult.scenario} · Source {visibleResult.bundle_id} · Calendar {visibleResult.calendar_revision_id}
          </p>
          <WeekCalendar horizonStart={visibleResult.horizon_start} week={week} assignments={assignments} />
        </section>
      )}
    </main>
  );
}
