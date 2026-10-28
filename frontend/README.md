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
| `/home` | Public light project dashboard (group `(public)` — no sidebar) |
| `/optimize` | Optimize: pick a file, review issues and strategies, copy the prompt |
| `/analyze` | Combined analysis: parse a file/folder, then measure its energy |
| `/energy` | Energy measurement with CodeCarbon, including continuous mode |
| `/detect` | Static energy smell detection mapped to the taxonomy |
| `/candidates` | Full optimization pipeline with accept/reject recording |
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
  AppShell.tsx              sidebar NAV array + mobile header + backend health probe
  Disclosure.tsx            collapsible sections
  ui.tsx                    shared primitives (cards, badges, tables, inputs)
  analyze/ energy/ detect/ candidates/ optimize/   client views per dashboard
lib/
  api.ts                    typed fetch client + SSE stream reader
  types.ts                  backend response contracts
  format.ts                 energy / duration / percentage formatting
```

**Where the sidebar and header live.** The sidebar, the mobile `☰ Menu` bar, the
"backend offline" banner and the footer are all rendered by
`components/AppShell.tsx`, which `app/(app)/layout.tsx` wraps around every route
in that group. Add or reorder nav entries in its `NAV` array; individual pages
never render navigation themselves. The public pages are the exception — the
landing page has its own `<header>` inline in `app/(public)/page.tsx`.

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
Because `/home` is in the public group, the sidebar's *Dashboard* link leaves the
shell instead of staying inside it.

Long-running endpoints stream Server-Sent Events over POST, so `EventSource`
cannot be used (it only supports GET). `lib/api.ts#streamPost` reads the response
body with a streaming reader and parses `data:` frames itself.
