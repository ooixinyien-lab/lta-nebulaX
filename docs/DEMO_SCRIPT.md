# Five-minute canonical solver demonstration

All jobs, resources, locations and operational rules in this demonstration are
synthetic.

## 1. Establish the source of truth

Show `constraints_lp_setup.md` and explain that it contains the nine approved
constraint families. Show that `scripts/generate_synthetic_dataset.py`
generates `data/comprehensive_synthetic_data.json`; `demo_data.json` belongs
only to the original scaffold.

## 2. Compare the learning versions

Run V0. It uses complete durations, the usable engineering window and frozen
starts, but it permits conflicts not yet taught in that version.

Run V1. Compared with V0, it adds dependency/handover ordering and opposed
traction-power separation. It still is not the complete scheduler.

Run the canonical solver:

```sh
python -m backend.app.services.cp_sat --planning-date 2026-09-14 --time-limit 8
```

## 3. Explain strict and recovery results

The canonical dataset proves strict mode `INFEASIBLE`: all selected work cannot
coexist while every hard rule remains enforced. Recovery then returns
`OPTIMAL`, meaning the best valid partial schedule under its documented
sequential objectives—not a universally best railway plan.

Point out:

- seven scheduled requests and five explicitly deferred requests;
- mandatory R09 remains scheduled;
- locked R01 remains at 01:30;
- R05 is deferred because its exact required equipment Q04 is unserviceable;
- the other deferred explanations correctly say that no single cause was
  proved when the global constraint combination was decisive.

## 4. Show independent validation and objectives

The output contains nine separate validation passes. Explain that the
validator recalculates the rules from exported timestamps and assignments; it
does not inspect CP-SAT's internal variables.

Show the recovery objective stages in order: scheduled urgency, scheduled
count, moved-allocation count, movement minutes, non-null preference deviation
and latest completion. Each stage reports a value, best bound and gap.

## 5. Demonstrate the application workflow

Start the local app, choose **Planning officer**, and click **Generate
proposal**. The frontend calls the configured CP-SAT API and displays strict
and recovery statuses plus deferred requests. Publishing repeats independent
validation within the database transaction.

Changing a resource increments the planning revision, so an older proposal is
rejected as stale. A deliberately invalid or tampered proposal is rejected
without partial publication.

End by stating that neither solver optimality nor officer publication grants
real engineering access. This prototype has no live railway-system
integration.
