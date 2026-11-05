# 1. The big picture

## The parts

```
 Patient at the kiosk            Hospital staff              Company staff
 (Flutter web, /#/kiosk)   (/#/hospital, /#/doctor)        (back office, /)
            \                       |                          /
             \______________ HTTP + one WebSocket ____________/
                                    |
                     FastAPI backend (backend/app, port 8100)
             /              |                 |                 \
   Supabase (Postgres)   Knowledge DB      Google Gemini      Local Ollama
   clients, visits,      (Postgres +       (online models,    (offline model
   reports, logins       pgvector)          voice)             MedGemma, embeddings)
```

- **Frontend** (`frontend/lib`): one Flutter web app with five faces: the
  back office (`lib/admin`), the kiosk (`lib/screens`, `lib/widgets`), the
  hospital portal (`lib/hospital`), the doctor portal (`lib/doctor`) and the
  patient's own phone pages (`lib/patient`). It never talks to a database or
  an AI model directly: everything goes through the backend.
- **Backend** (`backend/app`): the product. It stores visits, writes
  reports, relays the voice conversation, and serves the built web app.
- **Two databases**:
  - `MEDORA_DATABASE_URL` (Supabase): clients, kiosk keys, visits,
    reports, back-office/hospital/doctor accounts, logs.
  - `MEDORA_KNOWLEDGE_DATABASE_URL` (your teammate's PostgreSQL): ONLY
    medical knowledge (guidelines, diseases, symptoms, medicines,
    precautions). Chapter 8.
- **Models**: Gemini online (report and voice), MedGemma 4B through
  Ollama offline, MedCPT for the guideline search, all-MiniLM for symptom
  matching.

## Backend folders

| Folder / file | What it holds |
| --- | --- |
| `app/main.py` | Builds the server: creates every shared object and plugs in the routers (chapter 2) |
| `app/settings.py` | Every setting, read from `backend/.env` (`MEDORA_...`) |
| `app/routers/` | The URLs: `core` (status, config), `sessions` (save a visit), `reports`, `voice` (WebSocket), `auth` (sign-in), `admin` (back office), `knowledge_admin` (Database tab) |
| `app/hospital/`, `app/doctor/`, `app/patients/`, `app/handoff/` | The hospital portal, doctor portal, patient records, phone intake. Each has its own `router.py` (URLs) and service code |
| `app/triage.py` | The report pipeline (chapter 4) |
| `app/panel.py` | The specialist agents (CrewAI) |
| `app/report_writer.py` | Medicines, condition check, pharmacist review, safety rules |
| `app/precautions.py`, `app/vitals.py`, `app/sensitive.py` | Precautions, vital ranges, sensitive-word filtering |
| `app/patient_view.py`, `app/report_pdf.py` | The patient's simple-language report and its PDF |
| `app/voice.py` | Dr. Medora's voice conversation (chapter 5) |
| `app/llm.py` | One wrapper for every model (Gemini, Ollama), with retries and time limits |
| `app/offline.py`, `app/background.py` | Offline memory and the internet watcher (chapter 6) |
| `app/knowledge_base.py`, `app/kb/`, `app/ingest/` | Medical knowledge and uploads (chapter 8) |
| `app/models.py`, `app/db.py`, `app/tenancy.py`, `app/deps.py` | Database tables, connection, clients/keys, and the per-request checks |
| `data/` | Files the server makes or uses that are not code (chapter 9) |
| `eval/` | Quality measurements of the search and the reports (chapter 9) |
| `tests/` | Automatic tests (chapter 9) |

## How one request travels

Take "save this visit" (`POST /api/sessions`):

1. **Frontend**: `review_screen.dart L179` calls
   `ApiClient.createSession` (`api/api_client.dart L184`), which sends JSON to
   `<server>/api/sessions` with the kiosk key in the `X-Kiosk-Key` header
   (`_headers`, `api_client.dart L137–143`).
2. **Server address**: `medoraApiBase` (`api_client.dart L15`) is the same
   computer as the page, port 8100, unless the build set `MEDORA_API`.
3. **Routing**: FastAPI finds the function decorated
   `@router.post("")` on the `/api/sessions` router: `create_session` in
   `routers/sessions.py L55–87`.
4. **Dependencies run first** (`app/deps.py`): `get_db` (L18) opens a
   database session, `current_tenant` (L74) works out which client
   (hospital) this kiosk belongs to from its key.
5. **The function** checks and saves the visit (`IntakeSession`,
   `models.py L18–54`) and returns its id.
6. **JSON**: Python names are `snake_case`; the wire uses `camelCase`. The
   conversion is automatic for every class built on `schemas.ApiModel`.
7. **Back in the frontend**: the id is kept in `intakeProvider` and the
   screen moves to `/kiosk/report` (`review_screen.dart L191`).

Every feature follows this same path: **screen → `api_client.dart` method →
URL → router function → service code → database or model → JSON back**.

## Where the URLs are

The map lists every route with the frontend files that call it, for example
`map/app-routers.md`. The frontend's own pages are declared in
`frontend/lib/main.dart L64–90` (`/`, `/hospital`, `/doctor`,
`/phone/:code`, `/r/:id`, `/kiosk/...`).
