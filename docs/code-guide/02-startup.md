# 2. Startup: `backend/app/main.py`

`./run_dev.sh` (in `backend/`) loads `.env`, rebuilds the web app if its code
changed, and starts `uvicorn app.main:app` on port 8100. `app = create_app()`
at the bottom of `main.py` is what uvicorn runs. Everything below is
`create_app` (L64–241).

## L64–65: the settings

`settings = settings or Settings()`. `Settings` (`settings.py L6–102`) reads
every `MEDORA_...` value from `backend/.env`. Tests pass their own
`Settings(...)` here, which is how they use a throwaway SQLite database
instead of Supabase.

## L67–125: `lifespan`, what runs once at start and once at stop

FastAPI calls `lifespan` when the server starts; the code before `yield`
(L121) runs at start, the code after it at shutdown.

- **L69–71 `prepare()`**: `ensure_schema` (`tenancy.py L28`) creates the
  app's tables in Supabase if they are missing, and adds new columns listed
  in `_ADDED_COLUMNS` (`tenancy.py L17`; there are no migrations).
  `ensure_default_tenant` (`tenancy.py L52`) makes sure the "Default client"
  exists.
- **L74–93**: if Supabase cannot be reached (no internet at start), the
  server still starts and `retry()` tries `prepare()` again every 10 s.
- **L95–120** (only when `background_tasks` is on; tests turn it off):
  - L98: `kb.warm` builds the symptom index from the knowledge database
    (or its disk copy), in a worker thread so startup is not blocked.
  - L101: `kb_stats.summary` counts the knowledge database once, so the
    Database tab is current when first opened.
  - L102–103: `retriever.warm` loads the MedCPT search models.
  - L104–114: `move_legacy` loads Medora's old knowledge export into the
    knowledge database once, retrying every 2 minutes until it can reach it.
  - L115–120: `background.run` starts the internet watcher (chapter 6).
- **L122–125**: at shutdown, those tasks are cancelled and the database
  connections closed.

## L127–189: the shared objects on `app.state`

Every request can reach these as `request.app.state.<name>`. Tests replace
them directly (for example a fake model) instead of patching code.

| Line | Object | What it is |
| --- | --- | --- |
| L129 | `engine` | The Supabase connection pool (`db.make_engine`, 5 s connect limit so offline is noticed fast) |
| L130 | `runtime` | Live state: online or not, last sync (`background.Runtime`) |
| L131 | `progress` | Reports being written and their stage, for the waiting screen (`progress.py`) |
| L132 | `report_tasks` | A report already being written, so a second request waits for it instead of starting another |
| L133 | `llm` | The main text model (Gemini), `llm.make_llm` |
| L134 | `report_llm` | Optional stronger model for the final report |
| L137 | `offline` | Memory that holds visits, keys and logins while there is no internet (`offline.py`) |
| L138–139 | `offline_llm`, `offline_panel` | MedGemma through Ollama, and the one-doctor "panel" used offline |
| L140–142 | `voice_provider` | Gemini Live for the voice conversation; the offline voice slot is empty on purpose |
| L147 | `kb` | Symptom evidence index (`knowledge_base.KnowledgeIndex`) |
| L158 | `retriever` | Guideline search, MedCPT (`kb/retrieve.py`) |
| L161 | `kb_stats` | Live numbers for the Database tab (`kb/stats.py`) |
| L169–172 | `knowledge_changed` | Tells the index and the numbers to re-read after an upload |
| L173 | `uploads` | The upload desk for the Database tab (`kb/uploads.py`) |
| L183 | `panel` | The CrewAI specialist panel (only with a Gemini key) |

## L191–224: middleware (code that wraps every request)

- **L191 CORS**: lets the web app call the API from another port.
- **L197–224 `log_api_key_requests`**: when a request carries an API key
  (a hospital's own system), it writes one row to `api_request_logs`
  (method, path, status, time) and updates the key's "last used". That is
  what the back office shows under a client's API calls.

## L226–236: the routers (all the URLs)

Each module's `router` holds its URLs; `include_router` plugs them in.
`sessions` has two routers (`router` for `/api/sessions`, `intake_router`
for `/api/intake`), `hospital` two (the portal and the company's
"hospital admins" endpoints), `doctor` two (the portal and the patient's
"final report" page).

## L237–240: the web app

`app.mount("/", _WebApp(...))` serves `frontend/build/web` at the root, after
all API routes so they always win. `_WebApp` (L36–44) answers 404 instead of
crashing while there is no build. This is why the QR code on a phone opens
`http://<laptop>:8100/#/phone/...`: the same server serves the page and the
API.
