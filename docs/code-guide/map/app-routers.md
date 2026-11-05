# `app/routers`

## `backend/app/routers/__init__.py` (1 lines)

(no functions)

## `backend/app/routers/admin.py` (398 lines)

Back office: clients, monitoring and logs. Every route needs the admin key.

Uses (inside the app): `deps`, `hospital`, `hospital.models`, `models`, `panel`, `schemas`, `tenancy`, `voice`

Functions and classes:
- **L23–31** `def _tenant_out`
- **L34–38** `def _get`
- **L41–49** `def _issue_client_key`  
  A client has ONE key: its kiosks send it, and so does its own system as `X-Api-Key`. Registering it as an API key too is what makes those calls authenticate and appear in the request log. Earlier keys of the client stop working.
- **L52–55** `def list_tenants` — route `GET /api/admin/tenants`; called from: `frontend/lib/admin/clients_tab.dart`, `frontend/lib/admin/hospital_admins_dialog.dart`, `frontend/lib/admin/kiosk_tab.dart`, `frontend/lib/admin/logs_tab.dart`, `frontend/lib/admin/sessions_tab.dart`
- **L58–108** `def create_tenant` — route `POST /api/admin/tenants`; called from: `frontend/lib/admin/clients_tab.dart`, `frontend/lib/admin/hospital_admins_dialog.dart`, `frontend/lib/admin/kiosk_tab.dart`, `frontend/lib/admin/logs_tab.dart`, `frontend/lib/admin/sessions_tab.dart`  
  A new client (hospital), with its first hospital administrator when an email is given: the client and the account are created together or not at all.
- **L111–127** `def update_tenant` — route `PATCH /api/admin/tenants/{tenant_id}`; called from: `frontend/lib/admin/clients_tab.dart`, `frontend/lib/admin/hospital_admins_dialog.dart`, `frontend/lib/admin/kiosk_tab.dart`, `frontend/lib/admin/logs_tab.dart`, `frontend/lib/admin/sessions_tab.dart`
- **L130–138** `def rotate_kiosk_key` — route `POST /api/admin/tenants/{tenant_id}/kiosk-key`; called from: `frontend/lib/admin/clients_tab.dart`, `frontend/lib/admin/hospital_admins_dialog.dart`, `frontend/lib/admin/kiosk_tab.dart`, `frontend/lib/admin/logs_tab.dart`, `frontend/lib/admin/sessions_tab.dart`  
  Issues a new kiosk key. The previous key stops working at once.
- **L141–158** `def list_logs` — route `GET /api/admin/logs`; called from: `frontend/lib/admin/logs_tab.dart`
- **L164–166** `class ApiKeyCreate`
- **L169–190** `def _api_key_out`
- **L193–194** `def _tenant_names`
- **L197–201** `def list_api_keys` — route `GET /api/admin/api-keys`; called from: `frontend/lib/admin/clients_tab.dart`
- **L204–212** `def create_api_key` — route `POST /api/admin/api-keys`; called from: `frontend/lib/admin/clients_tab.dart`
- **L215–224** `def revoke_api_key` — route `DELETE /api/admin/api-keys/{key_id}`; called from: `frontend/lib/admin/clients_tab.dart`  
  Stops the key working at once. The key and its request log are kept.
- **L227–249** `def list_api_logs` — route `GET /api/admin/api-logs`; called from: `frontend/lib/admin/clients_tab.dart`
- **L255–256** `class SystemUpdate`
- **L259–308** `def _system`
- **L311–313** `def read_system` — route `GET /api/admin/system`; called from: no frontend file (API clients / tests)
- **L316–321** `def update_system` — route `PUT /api/admin/system`; called from: no frontend file (API clients / tests)
- **L324–397** `def overview` — route `GET /api/admin/overview`; called from: `frontend/lib/admin/overview_tab.dart`  
  The dashboard. `tz` is the viewer's offset from UTC in minutes (IST is 330), so "today" and the days of the week are the viewer's days.

## `backend/app/routers/auth.py` (106 lines)

Signing in to the back office, and managing who may.

Uses (inside the app): `deps`, `models`, `schemas`, `tenancy`

Functions and classes:
- **L16–18** `class Credentials`
- **L21–22** `class Registration`
- **L25–34** `def _user`
- **L37–56** `def register` — route `POST /api/auth/register`; called from: `frontend/lib/api/api_client.dart`  
  Creates an account and signs it in. With registration closed, only the first account is signed in; later ones wait for an approval.
- **L59–67** `def login` — route `POST /api/auth/login`; called from: `frontend/lib/api/api_client.dart`
- **L70–72** `def me` — route `GET /api/auth/me`; called from: `frontend/lib/api/api_client.dart`
- **L75–77** `def logout` — route `POST /api/auth/logout`; called from: `frontend/lib/api/api_client.dart`
- **L80–82** `class UserUpdate`
- **L85–87** `def list_users` — route `GET /api/admin/users`; called from: no frontend file (API clients / tests)
- **L90–105** `def update_user` — route `PATCH /api/admin/users/{user_id}`; called from: no frontend file (API clients / tests)

## `backend/app/routers/core.py` (106 lines)

Uses (inside the app): `deps`, `schemas`, `voice`

Functions and classes:
- **L12–19** `def health` — route `GET /api/health`; called from: no frontend file (API clients / tests)
- **L22–58** `def lan_address`  
  This machine's address on the local network, worked out fresh each time (a laptop's Wi-Fi address can change). A UDP "connect" sends nothing; it only asks the system which address it would use. Without a route (offline), the first private address of a network card.
- **L61–68** `def phone_base`  
  The fixed address phones open (http://<LAN address>:<this port>), when this server serves the built web app; else empty and the kiosk falls back to its own address.
- **L71–99** `def status` — route `GET /api/status`; called from: `frontend/lib/api/api_client.dart`
- **L102–105** `def read_config` — route `GET /api/config`; called from: `frontend/lib/api/api_client.dart`  
  The calling kiosk's feature switches, as set for its client.

## `backend/app/routers/knowledge_admin.py` (195 lines)

Back office: the knowledge database (MEDORA_KNOWLEDGE_DATABASE_URL).

What it holds (counted live) and uploading files into it. There is no
browsing of raw passages on purpose (2026-11-02: meaningless to operators). The
app database (Supabase) holds no medical knowledge any more: everything here
reads and writes the knowledge database only.

Uses (inside the app): `deps`, `kb.uploads`, `schemas`, `tenancy`

Settings and constants:
- **L23** `_CHUNK`

Functions and classes:
- **L26–32** `def _desk`
- **L35–36** `def _fail`
- **L39–73** `def _upload_out`
- **L79–88** `async def summary` — route `GET /api/admin/knowledge/summary`; called from: `frontend/lib/admin/knowledge_tab.dart`  
  Counts from the knowledge database (reused for a few seconds; the last counts when it cannot be reached), plus how the reports' searches stand.
- **L94–100** `async def list_uploads` — route `GET /api/admin/knowledge/uploads`; called from: `frontend/lib/admin/knowledge_tab.dart`
- **L103–109** `async def upload_detail` — route `GET /api/admin/knowledge/uploads/{upload_id}`; called from: `frontend/lib/admin/knowledge_tab.dart`
- **L112–159** `async def upload` — route `POST /api/admin/knowledge/uploads`; called from: `frontend/lib/admin/knowledge_tab.dart`  
  Stores a file and starts on it: a PDF is read and loaded at once; a data file or article is planned by the AI and waits for approval.
- **L162–163** `class ReasonBody`
- **L166–194** `async def act` — route `POST /api/admin/knowledge/uploads/{upload_id}/{action}`; called from: `frontend/lib/admin/knowledge_tab.dart`  
  approve | reject | revise | retry | remove | allow | block (reports' use).

## `backend/app/routers/reports.py` (274 lines)

Uses (inside the app): `deps`, `llm`, `models`, `offline`, `patient_view`, `patients`, `report_pdf`, `schemas`, `tenancy`, `triage`

Settings and constants:
- **L60** `_DOCTOR_ONLY`
- **L62** `_BEFORE_DOCTOR`

Functions and classes:
- **L30–42** `def _session`  
  The visit, from memory first (recent and offline visits), then the database.
- **L45–55** `def _stored_report`
- **L68–85** `def patient_medicines`  
  The medicines for the patient's copy: the doctor's list (reviewed, with injections and emergency care marked doctorOnly), else the patient list; wording on pregnancy or sexual health only if the patient raised it (sensitive.py), as in the rest of the patient's report.
- **L88–96** `def for_patient`  
  The stored report as the patient may see it.
- **L99–103** `def _report`
- **L106–124** `async def generate` — route `POST /api/sessions/{session_id}/report`; called from: `frontend/lib/admin/sessions_tab.dart`, `frontend/lib/api/api_client.dart`, `frontend/lib/doctor/doctor_screen.dart`, `frontend/lib/hospital/hospital_api.dart`  
  Generates the report once; later calls return the stored one. Online it runs on Gemini; offline on the local medical model, with the same steps, review and rules (fewer specialists, as they take turns). A request made while the report is still being written waits for that one instead of starting another.
- **L127–130** `async def _generate`
- **L133–219** `async def _write_report`
- **L222–228** `def progress` — route `GET /api/sessions/{session_id}/report/progress`; called from: `frontend/lib/admin/sessions_tab.dart`, `frontend/lib/api/api_client.dart`, `frontend/lib/doctor/doctor_screen.dart`, `frontend/lib/hospital/hospital_api.dart`  
  What the report being generated for this session is doing now.
- **L231–234** `def read` — route `GET /api/sessions/{session_id}/report`; called from: `frontend/lib/admin/sessions_tab.dart`, `frontend/lib/api/api_client.dart`, `frontend/lib/doctor/doctor_screen.dart`, `frontend/lib/hospital/hospital_api.dart`
- **L237–244** `def pdf` — route `GET /api/sessions/{session_id}/report.pdf`; called from: `frontend/lib/admin/sessions_tab.dart`, `frontend/lib/api/api_client.dart`, `frontend/lib/doctor/doctor_screen.dart`, `frontend/lib/hospital/hospital_api.dart`
- **L247–248** `class SendBody`
- **L251–273** `async def send` — route `POST /api/sessions/{session_id}/report/send`; called from: `frontend/lib/admin/sessions_tab.dart`, `frontend/lib/api/api_client.dart`, `frontend/lib/doctor/doctor_screen.dart`, `frontend/lib/hospital/hospital_api.dart`

## `backend/app/routers/sessions.py` (113 lines)

Uses (inside the app): `deps`, `models`, `offline`, `patients`, `schemas`, `vitals_need`

Functions and classes:
- **L18–22** `class VitalsCheck`
- **L25–34** `async def vitals_check` — route `POST /api/intake/vitals-check`; called from: `frontend/lib/api/api_client.dart`  
  Whether this complaint calls for vitals. Always yes while `vitals_always` is on (the default: vitals at every visit), and offline: only the hosted model may waive a measurement.
- **L37–40** `class VisitLookup`  
  An earlier visit number (printed on the report), e.g. "AB12CD".
- **L43–52** `def find_patients` — route `POST /api/intake/patients`; called from: `frontend/lib/api/api_client.dart`  
  "Have you visited before?": the person an earlier visit number belongs to, by name and age, to pick. Nothing else about them.
- **L55–87** `def create_session` — route `POST /api/sessions`; called from: `frontend/lib/admin/sessions_tab.dart`, `frontend/lib/api/api_client.dart`, `frontend/lib/doctor/doctor_screen.dart`, `frontend/lib/hospital/hospital_api.dart`  
  Called by the kiosk when the patient confirms the review screen. Without internet the visit is held in memory and copied to the database when it is back (offline.py).
- **L90–112** `def list_sessions` — route `GET /api/sessions`; called from: `frontend/lib/admin/sessions_tab.dart`, `frontend/lib/api/api_client.dart`, `frontend/lib/doctor/doctor_screen.dart`, `frontend/lib/hospital/hospital_api.dart`

## `backend/app/routers/voice.py` (112 lines)

Uses (inside the app): `auth`, `models`, `tenancy`, `vitals_need`, `voice`

Functions and classes:
- **L18–111** `async def voice` — route `WEBSOCKET /ws/voice`; called from: `frontend/lib/api/api_client.dart`  
  `key` is the kiosk key; browsers cannot set headers on a WebSocket. `tenant` + `admin` let the back office preview a client's kiosk.
