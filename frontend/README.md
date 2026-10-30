# OASIS Frontend

Next.js (App Router, TypeScript, Tailwind CSS v4) dashboard for the OASIS energy
optimization backend. It replaces the earlier static `index.html` / `analysis.html`
pages.

## Running

The backend and this UI are two processes. Start the backend from `OASIS/` first.

```bash
# terminal 1 — from OASIS/
uvicorn backend.main:app --port 8000 --reload

# terminal 2 — from OASIS/frontend/
npm install
npm run dev        # http://localhost:3000
```

The UI talks to `http://127.0.0.1:8000` by default. To point it elsewhere, copy
`.env.example` to `.env.local` and set `NEXT_PUBLIC_API_BASE_URL`.

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Development server with hot reload |
| `npm run build` | Production build (also runs the TypeScript check) |
| `npm start` | Serve the production build |

## Routes

| Route | What it does |
|---|---|
| `/` | Public landing page (group `(public)` — no sidebar) |
| `/home` | Workspace launcher: next action, the four stages, recent decisions |
| `/workspace/scan` | **Stage 1** — static energy smell detection with a filterable findings list |
| `/workspace/measure` | **Stage 2** — live CodeCarbon board (energy, power, CO₂, sparkline) |
| `/workspace/improve` | **Stage 3** — streamed pipeline, candidate list + detail |
| `/workspace/decide` | **Stage 4** — measured comparison and accept/reject recording |
| `/detect`, `/energy`, `/candidates` | Redirect to the corresponding stage |
| `/analyze` | Project structure: parse a file/folder, optionally measure |
| `/optimize` | Prompt lab: review issues and copy an LLM prompt |
| `/taxonomy` | The 12-category energy smell taxonomy |
| `/history` | Recorded optimization decisions |
| `/settings` | Backend, LLM and language configuration |

## Design rules this UI follows

1. **Summary first.** Every dashboard opens with headline metric cards. Deep
   tables live inside a collapsed `Disclosure` (`<details>` based, so it works
   without JavaScript). The combined analysis page in particular must never open
   onto a wall of raw per-file numbers.
2. **Predicted and measured are never mixed.** Predicted impact is rendered in a
   distinct style from measured energy, and the candidate cards show both side by
   side rather than a single blended score.
3. **Failures stay visible.** Neutral, regressed and failed candidates are shown
   with the same prominence as improvements.
4. **No business logic in components.** Energy, verification and decision logic
   lives in the backend modules; the UI only renders what the API returns.
5. **One workflow, four stages.** Scan → Measure → Improve → Decide, with the
   current step, its result and the single next action shown on every screen.
   Each stage remains directly reachable, so the flow guides without locking
   anyone in. Results and paths live in `WorkspaceContext`, not in each page.

## Structure

```
app/
  layout.tsx                root <html>/<body> + metadata (dark theme)
  (public)/layout.tsx       bare fragment — no shell
  (public)/page.tsx         landing page at "/" with its own inline header
  (public)/home/            light project dashboard, no sidebar/footer
  (app)/layout.tsx          mounts AppShell for every route below
  (app)/optimize/ analyze/ energy/ detect/ candidates/ taxonomy/ history/ settings/
components/
  AppShell.tsx              workflow rail + tools + mobile header + backend health probe
  Disclosure.tsx            collapsible sections
  ui.tsx                    shared primitives (cards, badges, tables, inputs)
  workspace/
    WorkspaceContext.tsx    shared settings + per-stage results + stage progress
    StageChrome.tsx         stage header, step strip, guidance bar, workspace bar
    Sparkline.tsx           zero-dependency live chart
    FindingsExplorer.tsx    filter/sort/search/expand findings list
    ScanView.tsx MeasureView.tsx ImproveView.tsx DecideView.tsx
    LauncherView.tsx        the /home workspace launcher
  analyze/ optimize/        secondary tools
lib/
  api.ts                    typed fetch client + SSE stream reader
  types.ts                  backend response contracts
  format.ts                 energy / duration / percentage formatting
```

**Where the sidebar and header live.** The sidebar, the mobile `☰ Menu` bar, the
"backend offline" banner and the footer are all rendered by
`components/AppShell.tsx`, which `app/(app)/layout.tsx` wraps around every route
in that group. The four workflow stages come from `STAGES` in
`components/workspace/WorkspaceContext.tsx`; utility links live in `UTILITY_NAV`
in `AppShell.tsx`. Individual pages never render navigation themselves. The
public landing page is the exception — it has its own `<header>` inline in
`app/(public)/page.tsx`.

**The workspace.** `WorkspaceProvider` (mounted by `app/(app)/layout.tsx`) is the
single source of truth for the file path, project path, language and execution
command (persisted to `localStorage` under `oasis-workspace`) and for the result
of each stage. Because the layout does not remount between routes, Scan →
Measure → Improve → Decide keep their results as you move; a hard refresh keeps
the settings but clears the results. Every stage reads and writes the same
state, so nothing is retyped.

**Themes.** `globals.css` defines the dark palette in `@theme`; a second
`:root[data-theme="light"]` block redefines the same token names with light
values. The toggle in the AppShell sidebar flips `data-theme` on `<html>` and
stores it in `localStorage` under `oasis-theme`; an inline script in
`app/layout.tsx` reapplies it before first paint so there is no flash. Both
themes work everywhere in `(app)/` because views use the tokens only — a new
component just uses `bg-surface`, `text-ink`, `text-muted`, `border-line`,
`bg-accent-soft`, … and needs no theme-specific code. Cards use
`shadow-[var(--elevation)]` for the same reason. Anything with a hard-coded hex
will ignore the toggle.

**Two palettes, two groups.** The shell group is dark: `globals.css` sets
`--color-canvas: #080c11` and `--color-ink: #e8eef6`, `app/layout.tsx` puts
`bg-canvas text-ink` on `<body>`, and views there use the tokens (`bg-surface`,
`text-ink`, `border-line`, `text-muted`). The public pages are light regardless of the toggle:
`(public)/page.tsx` and `(public)/home/page.tsx` hard-code `#F7F7FC` /
`#20252C`. Don't cross the two — a light page inside `(app)/` only paints the
part of the viewport it covers and leaves the dark canvas visible around it.
Long-running endpoints stream Server-Sent Events over POST, so `EventSource`
cannot be used (it only supports GET). `lib/api.ts#streamPost` reads the response
body with a streaming reader and parses `data:` frames itself.
