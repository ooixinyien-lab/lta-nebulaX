# Validation performed before delivery

Build date: **6 September 2026**.

## Results

| Check | Result |
|---|---|
| Backend / rules / local auth / persistence tests | **42 passed** |
| CP-SAT-dependent tests | **7 skipped: OR-Tools unavailable** |
| JavaScript module syntax | **10 modules passed** |
| Browser UI smoke flow | **Passed in Chromium; no JavaScript page errors** |
| Real Supabase project | **Not connected; not live-tested** |
| Local HTTP health, HTML and JavaScript serving | **200 responses from running Uvicorn** |
| Full production deployment | **Not performed** |

The Python test runtime was Python 3.13.5 with the core dependency versions in `requirements-core.txt`. Optional JavaScript syntax checking used Node 22.16.0. Other supported OS/Python combinations are not claimed to have been tested here.

## Browser testing method

The actual native-JavaScript pages and styles were rendered in Chromium. Browser network navigation to localhost was restricted in the build environment, so an in-process bridge forwarded frontend fetches to FastAPI's TestClient. It exercised the real route handlers, role checks, database and default demo solver on a temporary database. This was not a static screenshot mockup, but it is also not a production network/deployment test.

The flow covered profile selection, officer conflict display, calculated proposals, publication, requester visibility, request creation, persistence as read by another browser session, withdrawal and a mobile-width view. Screenshots are in `docs/screenshots/`.

`demo_search` was explicitly selected. The screenshots do **not** show a tested CP-SAT execution. The UI labels the active engine.

## Tests of interest

- Initial conflicts: dependency, shared power zone, engineer, equipment and pooled manpower.
- Feasible locked baseline and complete reference repair.
- Missing skill, insufficient transfer time, resource absence and blackout.
- Full phase duration and handback window checks.
- Mandatory work cannot disappear; locked bookings cannot be changed.
- Requester ownership and protected officer endpoints.
- Owner/role injection attempts and mutable Supabase user metadata.
- Requests persist without becoming bookings.
- Proposal generation does not commit reservations.
- Stale proposal rejection and recheck of a tampered proposal.
- All-or-nothing publication and repeated-commit rejection.
- Auth-only mocked Supabase role mapping and disabled demo reset.

The real external Supabase verification call was not exercised. Mocked identity tests confirm role mapping, not the availability/configuration of a real provider.

## Why CP-SAT was not run

The environment did not contain OR-Tools and could not download missing packages. The CP-SAT module passed Python syntax compilation, and its separate tests were written but skipped. Do not interpret those skips as proof that the adapter is correct. Your optimisation teammate should install `requirements-cpsat.txt`, enable `cp_sat`, and run all tests before presenting it as a CP-SAT-backed demo.

## Rerun

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
node scripts/check-js.mjs
```

For optional browser checks:

```sh
python -m pip install playwright
python -m playwright install chromium
python scripts/browser_smoke.py
```

The smoke script uses the local in-process API bridge and a temporary database, not a real account or a live railway system. Set `CHROMIUM_EXECUTABLE` when using an existing Chromium installation rather than the Playwright-managed browser.
