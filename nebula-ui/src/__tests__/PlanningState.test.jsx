import { describe, expect, it } from 'vitest';
import { reconcilePlanningState } from '../planning/PlanningContext';

const emptyState = {
  mode: 'operations', scenario: 'A',
  requirements: { A: null, B: null, C: null },
  operations: { A: null, B: null, C: null },
};

describe('persisted planning identity reconciliation', () => {
  it('hydrates solve identities from an existing database without requiring another upload', () => {
    const catalog = {
      instances: [{ instance_id: 'instance-1', revision_id: 'revision-1', revision_number: 1, created_at: '2026-09-19T01:00:00Z' }],
      official_runs: [],
      operational_baselines: [{ baseline_id: 'baseline-1', baseline_revision: 1, official_revision_id: 'revision-1', created_at: '2026-09-19T01:01:00Z' }],
      operational_runs: [],
    };

    const result = reconcilePlanningState(emptyState, catalog);

    expect(result.requirements.A).toMatchObject({ instanceId: 'instance-1', instanceRevisionId: 'revision-1', scenario: 'A' });
    expect(result.operations.A).toMatchObject({ baselineId: 'baseline-1', baselineRevision: 1, instanceRevisionId: 'revision-1', scenario: 'A' });
  });

  it('advances a stale saved baseline to its newest revision and drops an incompatible candidate', () => {
    const current = {
      ...emptyState,
      operations: {
        ...emptyState.operations,
        A: { mode: 'operations', scenario: 'A', baselineId: 'baseline-1', baselineRevision: 1, runId: 'old-run', instanceRevisionId: 'revision-1' },
      },
    };
    const catalog = {
      instances: [{ instance_id: 'instance-1', revision_id: 'revision-1', revision_number: 1, created_at: '2026-09-19T01:00:00Z' }],
      official_runs: [],
      operational_baselines: [
        { baseline_id: 'baseline-1', baseline_revision: 2, official_revision_id: 'revision-1', created_at: '2026-09-19T02:00:00Z' },
      ],
      operational_runs: [{ run_id: 'old-run', baseline_id: 'baseline-1', baseline_revision: 1, scenario: 'A', status: 'SUCCEEDED', created_at: '2026-09-19T01:30:00Z' }],
    };

    expect(reconcilePlanningState(current, catalog).operations.A).toMatchObject({
      baselineId: 'baseline-1', baselineRevision: 2, runId: null,
    });
  });
});
