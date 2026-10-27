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
| `/` | System status and the pipeline overview |
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
app/                     routes (one directory per page)
components/
  AppShell.tsx           sidebar navigation + backend health probe
  Disclosure.tsx         collapsible sections
  ui.tsx                 shared primitives (cards, badges, tables, inputs)
  analyze/ energy/ detect/ candidates/   client views per dashboard
lib/
  api.ts                 typed fetch client + SSE stream reader
  types.ts               backend response contracts
  format.ts              energy / duration / percentage formatting
```

Long-running endpoints stream Server-Sent Events over POST, so `EventSource`
cannot be used (it only supports GET). `lib/api.ts#streamPost` reads the response
body with a streaming reader and parses `data:` frames itself.
