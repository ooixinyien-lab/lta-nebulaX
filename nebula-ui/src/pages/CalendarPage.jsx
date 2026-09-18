import { useEffect, useState } from 'react';
import { CalendarDays, ChevronLeft, ChevronRight, Upload } from 'lucide-react';
import WeekCalendar from '../components/calendar/WeekCalendar';
import { addDays } from '../components/calendar/dateUtils';
import {
  createCalendar,
  createDemoCalendar,
  getAuthConfig,
  getCalendarisation,
  importScheduleBundle,
  queueCalendarisation,
} from '../services/calendarApi';
import '../styles/calendar.css';

const REQUIRED_OUTPUTS = ['SCHEDULE_ACCESS.csv', 'SCHEDULE_OCCUPANCY.csv', 'RESULTS.csv'];

export default function CalendarPage({ onBack }) {
  const [authConfig, setAuthConfig] = useState(null);
  const [identity, setIdentity] = useState('');
  const [revisionId, setRevisionId] = useState('');
  const [files, setFiles] = useState([]);
  const [bundle, setBundle] = useState(null);
  const [calendar, setCalendar] = useState(null);
  const [attempt, setAttempt] = useState(null);
  const [lastComplete, setLastComplete] = useState(null);
  const [week, setWeek] = useState(1);
  const [status, setStatus] = useState('Select the matching instance revision and solver outputs.');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getAuthConfig().then((config) => {
      setAuthConfig(config);
      if (config.auth_mode === 'demo' && config.demo_users.length > 0) {
        const officer = config.demo_users.find((user) => user.role === 'officer');
        setIdentity(officer?.id || config.demo_users[0].id);
      }
    }).catch((error) => setStatus(error.message));
  }, []);

  useEffect(() => {
    if (!attempt?.attempt_id || !['QUEUED', 'RUNNING'].includes(attempt.status)) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const latest = await getCalendarisation(attempt.attempt_id, identity);
        setAttempt(latest);
        if (latest.complete) setLastComplete(latest);
        if (latest.status === 'SUCCEEDED') {
          setStatus(latest.complete
            ? 'All fixed accesses have been assigned an actual night.'
            : 'No complete mapping was produced for this fixed schedule and calendar.');
        } else if (latest.status === 'FAILED') {
          setStatus(latest.error_message || 'Calendar assignment failed.');
        }
      } catch (error) {
        setStatus(error.message);
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [attempt?.attempt_id, attempt?.status, identity]);

  const handleFiles = (event) => {
    const selected = Array.from(event.target.files);
    setFiles(selected);
    const names = new Set(selected.map((file) => file.name));
    if (REQUIRED_OUTPUTS.every((name) => names.has(name)) && selected.length === 3) {
      setStatus('Three solver outputs selected.');
    } else {
      setStatus('Select exactly SCHEDULE_ACCESS.csv, SCHEDULE_OCCUPANCY.csv and RESULTS.csv.');
    }
  };

  const importOutputs = async () => {
    setBusy(true);
    setStatus('Importing and validating the fixed solver outputs…');
    try {
      const result = await importScheduleBundle(revisionId.trim(), files, identity);
      setBundle(result);
      setAttempt(null);
      setLastComplete(null);
      setStatus(`Imported ${result.access_count} fixed access rows without changing the source files.`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const useDemo = async () => {
    setBusy(true);
    setStatus('Creating the assumed demo calendar…');
    try {
      const result = await createDemoCalendar(revisionId.trim(), identity);
      setCalendar(result);
      setStatus('Demo calendar created. Its assumptions will remain visible.');
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const importCalendarJson = async (event) => {
    const [file] = Array.from(event.target.files);
    if (!file) return;
    setBusy(true);
    setStatus('Importing and validating the operating calendar…');
    try {
      const definition = JSON.parse(await file.text());
      const result = await createCalendar(definition, identity);
      setCalendar(result);
      setStatus('Operating calendar imported.');
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const assignNights = async () => {
    setBusy(true);
    setStatus('Queuing actual-night assignment…');
    try {
      const queued = await queueCalendarisation(
        bundle.bundle_id,
        calendar.calendar_revision_id,
        revisionId.trim(),
        identity,
      );
      setAttempt(queued);
      setStatus('Date assignment queued. Start the calendar worker if it is not running.');
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const visibleResult = attempt?.complete ? attempt : lastComplete;
  const horizonWeeks = visibleResult?.horizon_weeks || 30;
  const assignments = visibleResult?.assignments || [];
  const rangeStart = visibleResult?.horizon_start
    ? addDays(visibleResult.horizon_start, (week - 1) * 7)
    : '';
  const range = rangeStart ? `${rangeStart} – ${addDays(rangeStart, 6)}` : '';

  return (
    <main className="calendar-page">
      <header className="calendar-page__header">
        <div>
          <button className="calendar-link" type="button" onClick={onBack}>← Network map</button>
          <h1><CalendarDays size={24} /> Actual Night Preview</h1>
          <p>Read-only dates mapped onto an unchanged official solver output.</p>
        </div>
      </header>

      <section className="calendar-setup" aria-label="Calendar setup" aria-busy={busy}>
        {authConfig?.auth_mode === 'demo' && (
          <label>Demo profile
            <select value={identity} onChange={(event) => setIdentity(event.target.value)}>
              {authConfig.demo_users.map((user) => (
                <option value={user.id} key={user.id}>{user.name}</option>
              ))}
            </select>
          </label>
        )}
        <label>Instance revision ID
          <input value={revisionId} onChange={(event) => setRevisionId(event.target.value)} placeholder="rev-…" />
        </label>
        <label className="calendar-file-label"><Upload size={15} /> Solver output CSVs
          <input type="file" multiple accept=".csv" onChange={handleFiles} />
        </label>
        <button type="button" disabled={busy || !revisionId || files.length !== 3} onClick={importOutputs}>Import outputs</button>
        <button type="button" disabled={busy || !revisionId} onClick={useDemo}>Create demo calendar</button>
        <label className="calendar-file-label">Calendar JSON
          <input type="file" accept="application/json,.json" onChange={importCalendarJson} />
        </label>
        <button className="calendar-primary" type="button" disabled={busy || !bundle || !calendar} onClick={assignNights}>Assign actual nights</button>
      </section>

      <section className={`calendar-status ${attempt?.complete ? 'calendar-status--ok' : ''}`} aria-live="polite">
        <strong>{status}</strong>
        {calendar?.assumed_calendar && <span>Assumed demo calendar</span>}
        {attempt?.assumptions?.length > 0 && (
          <details><summary>Calendar assumptions</summary><ul>{attempt.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></details>
        )}
        {attempt?.conflicts?.length > 0 && (
          <ul>{attempt.conflicts.slice(0, 12).map((item, index) => <li key={`${item.rule_code}-${index}`}>{item.message}</li>)}</ul>
        )}
      </section>

      {visibleResult?.complete && (
        <section className="calendar-result">
          <div className="calendar-week-nav">
            <button aria-label="Previous week" type="button" disabled={week === 1} onClick={() => setWeek((value) => value - 1)}><ChevronLeft size={18} /></button>
            <div><strong>Week {week}</strong><span>{range}</span></div>
            <button aria-label="Next week" type="button" disabled={week === horizonWeeks} onClick={() => setWeek((value) => value + 1)}><ChevronRight size={18} /></button>
          </div>
          <p className="calendar-caption">Scenario {visibleResult.scenario} · Source {visibleResult.bundle_id} · Calendar {visibleResult.calendar_revision_id}</p>
          <WeekCalendar horizonStart={visibleResult.horizon_start} week={week} assignments={assignments} />
        </section>
      )}
    </main>
  );
}
