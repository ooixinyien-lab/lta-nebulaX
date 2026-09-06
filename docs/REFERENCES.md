# Source and design notes

The prior `Rail_Scheduler_Blueprint_and_Demo_Data.zip` in this conversation provided the fictional corridor and four-request scenario. The dataset here retains those operational assumptions, with ownership assigned to the new demo profiles.

This repository is newly written implementation code. The earlier README was a blueprint, not an executable application. In particular, this starter deliberately changes the frontend to a no-build native-JavaScript website and starts with a small dependency-free search engine. It implements one proposal and one officer approval, not the entire earlier extension roadmap.

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
