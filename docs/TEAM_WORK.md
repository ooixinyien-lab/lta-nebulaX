# Team handoff: work in parallel without building disconnected pieces

## First 30 minutes together

Have everyone run the unmodified repository. Open the officer profile, calculate a proposal, publish it and then view the result as a requester. Agree the request field names and API responses before anyone redesigns them.

One teammate creates your shared Git repository and commits this starter. Other teammates clone that same repository. You do not need a separate repository for every module.

The current frontend is intentionally native JavaScript, not React. Decide once, as a team, whether to keep it for the hackathon. Do not have different people independently rewrite different pages in different frameworks.

## Suggested ownership

| Stream | Owned files | First useful task | Definition of done |
|---|---|---|---|
| Frontend | `frontend/src/pages/`, `components/`, `styles.css` | Improve request feedback and make protection vs work location unmistakable | Submitted data persists; rendered fields match the API; no scheduling rules hidden in UI |
| Backend/rules | `backend/app/api/routes.py`, `database.py`, `services/checker.py` | Add well-defined work-compatibility rules and clear errors | Tests demonstrate allowed AND forbidden cases; revision bumps and ownership still work |
| Optimisation | `services/cp_sat.py`, `candidates.py`, `scheduler.py`, `test_scheduler.py` | Install OR-Tools, run seven CP-SAT tests, then compare against demo search | Feasible outputs pass the checker; status/objective meanings are documented |
| Auth/integration/testing | `backend/app/auth/`, `frontend/src/auth/`, CI and auth tests | Enable a real Supabase test project with two requester users and one officer | Real requester cannot call officer endpoints; no secret key reaches the browser |

With a fifth person, split requester and officer frontend files. With three people, combine auth with backend, and give browser QA to the frontend owner.

### Shared files that need coordination

`backend/app/schemas.py`, `frontend/src/app.js`, `frontend/src/lib/api.js`, `data/demo_data.json`, the dependency files and `.env.example` affect several streams. Assign one integrator or announce edits before changing them. The API guide is the contract; do not silently rename fields.

Keep the current fixture as a baseline. Put additional scenarios in new files/tests rather than changing every existing test to match a new answer.

## Module boundaries

**Frontend calls the API.** It may validate a required field for convenience, but the backend must validate it again. It must not decide that a job is safe because a timeline rectangle looks empty.

**Routes coordinate the workflow.** They load snapshots, authorize users, call the checker/solver, and persist proposals. They should not contain a second scheduling algorithm.

**Checker evaluates rules.** Input: snapshot + candidate allocations. Output: structured issues. It does not use HTTP, database state or OR-Tools.

**Solver searches.** Input: snapshot + time limit. Output: status, allocations, timings and a message. It does not publish anything.

**Authentication establishes identity.** Server-owned configuration determines whether that identity is a requester or officer. A frontend-selected role is never a real authority.

## A simple Git workflow

Repository owner, from the starter root:

```sh
git init -b main
git add .
git commit -m "Add RailPlan team starter"
```

Create an empty repository on your chosen Git host, then add its remote using the URL that host gives you. No remote repository has been created by this download.

Each teammate starts a branch, for example:

```sh
git switch -c feat/cp-sat-alternatives
# edit only your agreed module files
python -m pytest -q
git add backend/app/services backend/tests/test_scheduler.py
git commit -m "Generate and validate distinct schedule alternatives"
git push -u origin feat/cp-sat-alternatives
```

Open a pull request, ask another teammate to review it, then merge. Pull the updated `main` before starting another feature. Prefer small integrated changes to a last-minute merge of four disconnected applications.

Do not upload `.env`, `.venv`, SQLite databases, caches, personal passwords or API secret keys. Share real configuration through your team's chosen secure channel, not by committing it.

## Why we do not need two login applications

One sign-in verifies a user. The backend returns `/api/me` with a role. The browser presents the matching pages. Both pages call the same backend and operate on the same database.

Requester and officer roles are application identities. E01-E04 are maintenance personnel resources. A requester is NOT necessarily the engineer assigned to the work.

## Integration checkpoints

1. Requester creates a job; officer can see it after refresh.
2. Checker identifies a hidden power/resource conflict.
3. Solver changes the allocation when an input changes.
4. Officer publishes; requester sees their committed result.
5. A stale proposal fails with no partial database writes.
6. Requester attempts to call a protected endpoint and gets `403`.

All teammates should be able to run the same checks before a demo.

## What sharing means

A shared repository distributes source code. It does not distribute a running server or synchronise the team's laptop databases. For development, that isolation is useful. For an integrated demonstration, use one laptop/server as the source of truth and review the auth/deployment checklist before allowing remote access.
