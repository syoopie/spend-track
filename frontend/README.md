# SG Expenditure Tracker (frontend)

React + TypeScript + Vite frontend for the local-only SG bank statement expenditure tracker. See the [repo root README](../README.md) for the full picture (what it does, one-command startup, design decisions).

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api/* to the backend
npm run build     # production build
npx tsc -b        # typecheck
```

Stack: Vite, Tailwind CSS v4, TanStack Query, React Router, Oxlint. No charting library — every chart in the dashboard is hand-rolled SVG.
