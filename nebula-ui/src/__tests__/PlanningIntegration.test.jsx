import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import AppHeader from '../components/AppHeader';
import { loadMapSchedule, loadSchedule } from '../services/planningApi';

afterEach(() => vi.restoreAllMocks());

describe('global planning controls', () => {
  it('exposes both planning modes and A/B/C without mutating a schedule', () => {
    const onModeChange = vi.fn();
    const onScenarioChange = vi.fn();
    render(<AppHeader activeTab="matrix" onNavigate={vi.fn()} mode="operations" scenario="B" onModeChange={onModeChange} onScenarioChange={onScenarioChange} onAddJob={vi.fn()} onSolve={vi.fn()} onAccept={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'PS1 Requirements' }));
    fireEvent.click(screen.getByRole('button', { name: 'C' }));
    expect(onModeChange).toHaveBeenCalledWith('requirements');
    expect(onScenarioChange).toHaveBeenCalledWith('C');
    expect(screen.getByRole('button', { name: 'A' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'B' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'C' })).toBeDefined();
  });

  it('shows operational actions and candidate acceptance only in Operations Mode', () => {
    const { rerender } = render(<AppHeader activeTab="matrix" onNavigate={vi.fn()} mode="operations" scenario="A" onModeChange={vi.fn()} onScenarioChange={vi.fn()} onAddJob={vi.fn()} onSolve={vi.fn()} onAccept={vi.fn()} hasCandidate />);
    expect(screen.getByRole('button', { name: /add job request/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /auto solve/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /accept schedule/i })).toBeDefined();
    rerender(<AppHeader activeTab="matrix" onNavigate={vi.fn()} mode="requirements" scenario="A" onModeChange={vi.fn()} onScenarioChange={vi.fn()} onAddJob={vi.fn()} onSolve={vi.fn()} onAccept={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /add job request/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /accept schedule/i })).toBeNull();
  });
});

describe('explicit schedule projection API', () => {
  it('uses the identical operational candidate identity for matrix and map', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, json: async () => ({ identity: {} }) });
    const identity = { mode: 'operations', scenario: 'B', baselineId: 'baseline-3', baselineRevision: 4, runId: 'sir-17' };
    await loadSchedule(identity);
    await loadMapSchedule(identity, 5);
    const matrixUrl = String(fetchMock.mock.calls[0][0]);
    const mapUrl = String(fetchMock.mock.calls[1][0]);
    for (const expected of ['mode=operations', 'scenario=B', 'baseline_id=baseline-3', 'baseline_revision=4', 'run_id=sir-17']) {
      expect(matrixUrl).toContain(expected);
      expect(mapUrl).toContain(expected);
    }
    expect(mapUrl).toContain('week=5');
    expect(matrixUrl).not.toContain('week=');
  });

  it('never adds a latest-run selector when an official run is explicit', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, json: async () => ({ identity: {} }) });
    await loadSchedule({ mode: 'requirements', scenario: 'C', instanceRevisionId: 'rev-3', runId: 'run-9' });
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain('instance_revision_id=rev-3');
    expect(url).toContain('run_id=run-9');
    expect(url.toLowerCase()).not.toContain('latest');
  });
});
