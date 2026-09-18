# Optional real identity with Supabase

> [!NOTE]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> As established in [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md), identity and role enforcement in `backend/app/auth/` are **kept intact**: user authentication and server-enforced roles are independent of the scheduling domain model.
>
> Note: `DATASET_PATH` and single-night parameters in `.env` configure the legacy synthetic prototype. For the official PS1 challenge, instances are supplied via 8 official CSV file uploads through `/api/ps1/instances/upload`.

## Do we need this immediately?

No, not for local development with the supplied synthetic PS1 challenge data. The demo profile selector is deliberately not authentication. For an actual shared-account demonstration, the optional Supabase adapter is wired into the backend authentication flow; canonical new UI work belongs in `nebula-ui/`.

This repository uses Supabase **Auth only**. Planning records stay in the application's SQLite database. Enabling Auth does not upload your bookings to Supabase, synchronise teammates' databases, or enable Row Level Security on SQLite.

## Identity flow

```text
User enters email/password on the single login page
       |
       v
Browser calls your Supabase project's Auth endpoint
       |
       v
Supabase returns a session access token
       |
       v
Browser sends Bearer token to FastAPI
       |
       v
FastAPI asks that project's Auth server to verify the token
       |
       v
Backend matches the verified user ID against OFFICER_USER_IDS
       |
       +--> matched: officer
       +--> otherwise: requester
```

The browser never chooses its own real role. `user_metadata.role` is not used. The simulated `X-Demo-User` header is ignored in Supabase mode.

## Setup

1. Create a Supabase test project under an account your team controls.
2. Obtain its project URL and **publishable key** (`sb_publishable_...`) from the project's connection/API-key settings. This adapter intentionally requires the new publishable-key format; it does not accept a secret/service-role key.
3. Create/invite test users through your administrator workflow. This starter's UI supports password sign-in, not self-service signup or password recovery. Complete the provider's account confirmation/password setup before testing.
4. For an invite-only team, disable unrestricted signups in the provider configuration; merely omitting a signup button does not disable a public signup API.
5. Copy the **user UUID** of the officer account. Do not use an email address, a demo ID or a client-provided role.
6. Update the repository-root `.env`:

```dotenv
APP_ENV=development
AUTH_MODE=supabase
SUPABASE_URL=https://YOUR_PROJECT_REFERENCE.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_YOUR_PUBLIC_KEY
OFFICER_USER_IDS=THE_OFFICER_USER_UUID
SOLVER_ENGINE=cp_sat
DATASET_PATH=./data/comprehensive_synthetic_data.json
```

`DATASET_PATH` and `SOLVER_ENGINE` above are legacy-only settings. Official startup reads `OFFICIAL_DATA_PATH`; future operational calendars, recurrence policies and emergency changes are uploaded as typed, versioned enrichment data rather than environment variables.

For multiple officers, use comma-separated UUIDs. Everyone else authenticated to the configured project is treated as a requester, so restrict project membership/signup as appropriate.

7. Stop and restart the Python server. The login screen now asks for email/password; demo profile buttons disappear.
8. Test with separate requester and officer accounts. Real requesters initially have no personally owned seed jobs. They should create their own requests; the officer can see all of them.

You do not need a `VITE_...` variable or a second frontend `.env`. The frontend gets only the project URL and publishable key from `/api/config`. Those are intentionally browser-visible public configuration. Officer UUID lists remain backend-only.

## Session simplification

The starter keeps real access and refresh tokens in JavaScript memory only. While the page remains open, it refreshes the access token before expiry when needed. Reloading the page signs you out of this app; sign in again.

No real passwords or Supabase tokens are written to SQLite. Demo profile IDs alone use `sessionStorage`. A polished persistent-session implementation can be added later with an explicit security design; do not blindly put privileged secrets into browser storage.

## Verification checklist

- Real requester can create and see only their own request records.
- Real requester receives `403` from `/api/schedule/proposals`, `/api/conflicts/check`, resource changes and publication.
- PS1 instance/run/enrichment reads are tenant/role scoped; only authorised planning roles may create recurrence policies, emergency revisions, locks, repairs or publications.
- Manual preflight may be read-only, but saving/pinning a drag requires current revision authority.
- Chat and explanation endpoints can call only role-scoped read-only schedule tools. They never inherit provider credentials in the browser and cannot bypass the separate scheduling action endpoints.
- Editing a profile's user metadata to contain `role=officer` does not confer authority.
- Verified allowlisted officer can plan and publish.
- Invalid/expired tokens fail verification.
- `/api/demo/reset` is disabled in Supabase mode.
- No secret/service-role key appears in the page, API config, JavaScript or Git history.

Mocked role tests are included. A real Supabase project was NOT connected or tested during artifact creation.

## Before exposing the app beyond localhost

Supabase sign-in alone does not make this a production deployment. Review HTTPS, user admission, session security, rate limits, payload limits, error handling, backups, dependency patches, restrictive network access, privacy, logging and database hosting. Chat logs/fact packs need explicit retention and redaction controls, and uploaded text must be isolated from system/tool instructions. Use a persistent server database deployment suited to the expected load. SQLite on each developer's laptop is not a shared cloud database.

The app refuses `APP_ENV=production` with demo identities, but that guard is only one safeguard. It is not a production certification. There is no real track-access control in this prototype.

If you later migrate application tables to Supabase Postgres and expose them directly to clients, design and test table-level Row Level Security and grants; this starter does not include that migration or policies.

## Primary references

- [Supabase Auth React quickstart](https://supabase.com/docs/guides/auth/quickstarts/react)
- [Password sign-in](https://supabase.com/docs/reference/javascript/auth-signinwithpassword)
- [Server-verified user retrieval](https://supabase.com/docs/reference/javascript/auth-getuser)
- [API keys: publishable versus secret](https://supabase.com/docs/guides/getting-started/api-keys)
- [Row Level Security and user metadata](https://supabase.com/docs/guides/database/postgres/row-level-security)
