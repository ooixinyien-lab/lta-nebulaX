# NebulaX Canonical UI

`nebula-ui/` is the React 19 + Vite frontend for new NebulaX features. The root [PS1 adoption plan](../PS1_OFFICIAL_ADOPTION_PLAN.md) is authoritative; scheduling, scoring, conflict detection and explanation facts remain server-side.

## Development

```sh
npm install
npm run dev
npm run build
npm run lint
npm test
```

The development server runs on `http://127.0.0.1:5173` and proxies `/api` to FastAPI on port 8000. A production build is written to `dist/` and served by FastAPI at `/network-map`.

## Workflow roadmap

The UI must clearly separate the official weekly fields (`week`, local `access_night`, local `co_share_group`) from operational `service_date`/`global_night_id`. New views cover recurrence policies/generated jobs, frozen-history emergency replans, scenario score versus churn, and official-export eligibility.

Dragging creates a draft sent to backend preflight; it never mutates a published run directly. Render structured hard conflicts and warnings, then use the repair endpoint for a complete replan. Do not duplicate constraint logic in React.

Clicking a displaced activity opens a visible auto-prompt backed by a deterministic explanation fact pack. General schedule chat uses caller-scoped read-only tools, cites run/activity/location IDs and falls back to the deterministic summary. The chatbot cannot validate, edit or publish schedules.

The legacy `../frontend/` workspace remains transitional and is not the target for these features.
