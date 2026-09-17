# NebulaX References and Authoritative Sources

> [!IMPORTANT]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> The single authoritative source of truth for Problem Statement 1 (PS1) is [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md), supported by the official PS1 challenge materials (`NebulaX-Hackathon-ProblemStatement-main/PS1/PS1_README.md`).
>
> Historical artifacts (`constraints_lp_setup.md`, `scripts/generate_synthetic_dataset.py`, `data/comprehensive_synthetic_data.json`, `solver_v0.py`, `solver_v1.py`, and `backend/app/services/cp_sat.py`) are **retired as PS1 authority** and retained solely as legacy learning/testing artifacts.

## Official PS1 Authoritative Materials

| Reference | Purpose |
|---|---|
| [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md) | Single authoritative project roadmap, architecture, and requirements reconciliation |
| [Official PS1 README](../../NebulaX-Hackathon-ProblemStatement-main/PS1/PS1_README.md) | Authoritative problem statement, operating rules, and scoring rubric |
| [Official Input CSVs](../../NebulaX-Hackathon-ProblemStatement-main/PS1/01_data/) | 8 official input files: `01_LINES.csv` through `08_ACTIVITY_DETAILS.csv` |
| [Official Submission Sample](../../NebulaX-Hackathon-ProblemStatement-main/PS1/03_submission_sample/) | Sample outputs: `SCHEDULE_ACCESS.csv`, `SCHEDULE_OCCUPANCY.csv`, `RESULTS.csv` |
| [Network Diagram SVG](../../NebulaX-Hackathon-ProblemStatement-main/PS1/02_references/network_diagram.svg) | Official rail network topology, stations, and interchange boundaries |
| [Network Drawio Reference](../../NebulaX-Hackathon-ProblemStatement-main/PS1/02_references/PS1.drawio) | Spatial relationships, crossover, and buffer considerations |

## Technical and Software References

| Reference | Used for |
|---|---|
| [Google OR-Tools CP-SAT Guide](https://developers.google.com/optimization/cp/cp_solver) | Integer modelling, CP-SAT solver statuses, and search parameters |
| [OR-Tools Python Model API](https://or-tools.github.io/docs/pdoc/ortools/sat/python/cp_model.html) | Boolean variables, linear constraints, and hints |
| [FastAPI Request Bodies](https://fastapi.tiangolo.com/tutorial/body/) | Validated JSON/multipart inputs and generated OpenAPI schemas |
| [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/) | TestClient and pytest integration |
| [SQLite Transactions](https://www.sqlite.org/lang_transaction.html) | Atomic update boundaries and revision management |
| [Supabase Auth Quickstart](https://supabase.com/docs/guides/auth/quickstarts/react) | Optional real email/password authentication adapter |

*Note:* Public descriptions of deployed railway systems do not grant access to their APIs. This prototype makes no live calls to TAMS, MOMS, LTA, or operator production systems.

