# Source and design notes

The earlier four-request scenario survives only as `data/demo_data.json` for scaffold-specific tests. The current synthetic source of truth is `scripts/generate_synthetic_dataset.py`, which produces `data/comprehensive_synthetic_data.json` according to `constraints_lp_setup.md`.

The native-JavaScript frontend and small dependency-free search remain from that scaffold. The canonical scheduling path is now the full CP-SAT solver plus an independent nine-constraint validator.

No public source establishes the correctness of the invented railway rules. The following official sources support software mechanisms only:

| Reference | Used for |
|---|---|
| [FastAPI request bodies](https://fastapi.tiangolo.com/tutorial/body/) | Validated JSON input and generated API schemas |
| [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/) | TestClient and pytest integration |
| [OR-Tools job-shop scheduling](https://developers.google.com/optimization/scheduling/job_shop) | Interval, precedence and exclusive-resource modelling |
| [CP-SAT solver guide](https://developers.google.com/optimization/cp/cp_solver) | Integer modelling and solver status distinctions |
| [OR-Tools Python model API](https://or-tools.github.io/docs/pdoc/ortools/sat/python/cp_model.html) | Conditional constraints, allowed assignments and cumulative resources |
| [Supabase password sign-in](https://supabase.com/docs/reference/javascript/auth-signinwithpassword) | Email/password authentication capability |
| [Supabase verified user retrieval](https://supabase.com/docs/reference/javascript/auth-getuser) | Authentic server-confirmed user identity |
| [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys) | Publishable vs privileged secret keys |
| [Supabase Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security) | Server-controlled authorization and cautions about mutable user metadata |
| [SQLite transactions](https://www.sqlite.org/lang_transaction.html) | Atomic update boundaries |

Public descriptions of deployed railway systems do not grant access to their APIs. This starter makes no calls to TAMS, MOMS, LTA or operator systems.
