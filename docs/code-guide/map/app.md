# `app`

## `backend/app/__init__.py` (1 lines)

(no functions)

## `backend/app/auth.py` (143 lines)

Back-office accounts: email and password, and the sessions they open.

By default anyone who can open the back office can create an account and
use it at once. With `MEDORA_REGISTRATION_OPEN=false` only the first account
works straight away; later ones wait for an approval (`PATCH
/api/admin/users/{id}`).

Passwords are stored as scrypt hashes; session tokens as SHA-256 hashes, so
a copy of the database gives access to neither.

Uses (inside the app): `models`

Settings and constants:
- **L23** `SESSION_HOURS`
- **L24** `MIN_PASSWORD`
- **L26** `MAX_FAILURES`
- **L27** `LOCK_SECONDS`
- **L29** `_SCRYPT`

Functions and classes:
- **L33–36** `class AuthError`
  - **L34–36** `def __init__`
- **L39–42** `def hash_password`
- **L45–51** `def verify_password`
- **L54–55** `def _token_hash`
- **L58–59** `def normalize_email`
- **L62–80** `def register`
- **L83–111** `def sign_in`  
  The user and a new session token. Raises AuthError otherwise.
- **L114–129** `def user_for_token`  
  The signed-in user a token belongs to, if it is still valid.
- **L132–136** `def sign_out`
- **L139–142** `def end_sessions`  
  Signs a user out everywhere, for when the account is switched off.

## `backend/app/background.py` (126 lines)

Background work: watching for internet, and copying what waited.

Every 10 s the server checks whether the internet is there
(`runtime.online`). When it is back, visits and reports made offline
(held in memory by `offline.py`) are copied into the database, which is
Supabase. The older mirror to a second database (`cloud_database_url`) is
idle while that setting is empty. Nothing a patient does depends on this.

Uses (inside the app): `models`, `tenancy`

Settings and constants:
- **L24** `_PROBE`
- **L25** `CHECK_EVERY`
- **L26** `SYNC_EVERY`
- **L27** `BATCH`
- **L30** `_MIRRORED`

Functions and classes:
- **L33–38** `class SyncState`
- **L41–44** `class Runtime`
- **L47–53** `async def is_online`
- **L56–59** `def _unsynced`
- **L62–66** `def pending`
- **L69–93** `def mirror_once`  
  Copies one batch of unmirrored rows per table. Returns how many.
- **L96–125** `async def run`  
  Loops until cancelled. `offline` (an `offline.OfflineState`) has its waiting visits copied into the database whenever the internet is back.

## `backend/app/db.py` (15 lines)

Functions and classes:
- **L5–6** `class Base`
- **L9–14** `def make_engine`

## `backend/app/delivery.py` (101 lines)

Sends the report to the patient by email (SMTP) or SMS (Twilio).

SLOT: both channels stay switched off until their credentials are set in
`.env`. A different SMS provider only needs `send_sms` replaced.

Uses (inside the app): `models`, `settings`

Settings and constants:
- **L29** `_URGENCY_TEXT`

Functions and classes:
- **L17–18** `class DeliveryError`
- **L21–22** `def email_configured`
- **L25–26** `def sms_configured`
- **L37–39** `def _summary_line`
- **L42–67** `async def send_email`
- **L70–79** `def _e164`
- **L82–100** `async def send_sms`

## `backend/app/deps.py` (166 lines)

Uses (inside the app): `auth`, `models`, `offline`, `settings`, `tenancy`

Functions and classes:
- **L14–15** `def get_settings`
- **L18–20** `def get_db`
- **L23–31** `def admin_token`  
  The back-office session token, from `Authorization: Bearer ...` or the `X-Admin-Key` header the app sends.
- **L34–35** `def _online`
- **L38–49** `def require_admin`  
  The signed-in back-office user making this request.
- **L52–71** `def _offline_tenant`  
  The client of a kiosk request while Supabase cannot be reached, from what was seen online since the server started (`offline.py`).
- **L74–98** `def current_tenant`  
  The client a request belongs to. In order: the back office previewing a client's kiosk (signed in, plus a tenant id), a client's own system (`X-Api-Key`), a kiosk (`X-Kiosk-Key`), else the default client. Without internet, answered from memory (`offline.py`).
- **L101–128** `def _tenant`
- **L131–158** `def note_api_key`  
  For routes that do not need to know the client: an API key, when one is sent, must still be valid, and its use is still logged (online).

## `backend/app/knowledge_base.py` (638 lines)

Symptom evidence over the medical knowledge (one of the report's two searches;
the guideline passages are the other, app/kb/retrieve.py).

Given the symptoms a patient described, in whatever words, this finds the
matching symptom rows, follows the disease links, and scores each candidate
disease by the evidence for it. It is deterministic and needs no language
model, so the same evidence is available online and offline.

The data comes from the knowledge database (MEDORA_KNOWLEDGE_DATABASE_URL,
tables kb_entities, kb_disease_symptoms, kb_disease_drugs, kb_precautions,
kb_drugs) of the sources reports may use. A copy of what was read is kept on
disk (data/rag_cache/kb_index.json.gz), so the search works when that
database cannot be reached. The app database (Supabase) holds no knowledge.

  1. Symptom matching: exact name, alias or spelling variant first; then
     meaning, by embedding similarity ("my head is pounding" -> Headache).
  2. Evidence scoring: a candidate is scored by how much of the patient's
     presentation it explains, weighting rare symptoms above common ones.
  3. For the best candidates: description, linked drugs and precautions.

Uses (inside the app): `ingest.transform`

Settings and constants:
- **L43** `MAX_SYMPTOMS_PER_DISEASE`
- **L45** `MIN_SIMILARITY`
- **L49** `SYNONYM_SIMILARITY`
- **L50** `MAX_NEIGHBOURS`
- **L51** `MAX_CANDIDATES`
- **L54** `CHECK_EVERY`
- **L55** `CONNECT_TIMEOUT`
- **L58** `_EVERYDAY_SUBSTANCES`
- **L136** `_QUERIES`

Functions and classes:
- **L64–83** `class Embedder`  
  Sentence embeddings from the local Ollama server (works offline).
  - **L67–69** `def __init__`
  - **L71–83** `def embed`
- **L86–95** `class SymptomMatch`
- **L98–110** `class Candidate`
- **L113–125** `class Evidence`
  - **L119–121** `def used`
  - **L123–125** `def drug_names`  
    Normalized name -> display name of every drug linked to a candidate.
- **L128–132** `def _allowed_sql`
- **L152–637** `class KnowledgeIndex`  
  Search structures over the knowledge database, built on first use and rebuilt when a source is loaded, changed or removed.
  - **L156–173** `def __init__`
  - **L175–181** `def from_rows`  
    An index over rows given directly (tests, tools): no database.
  - **L183–198** `def _reset`
  - **L202–204** `def available`  
    Whether there is knowledge to search. Never waits on a database.
  - **L206–212** `def warm`  
    Builds the index ahead of the first request (from the database, or from the copy on disk when it cannot be reached). Never raises.
  - **L214–216** `def refresh_soon`  
    Asks the database again at the next search (after a load).
  - **L218–220** `def _cache_file`
  - **L222–243** `def _ensure`  
    Loads or refreshes the index. False when there is no knowledge. The database is asked at most every CHECK_EVERY seconds; when it cannot be reached, the loaded index (or the disk copy) keeps serving.
  - **L245–248** `def _connect`
  - **L250–266** `def _refresh`
  - **L268–274** `def read_rows`
  - **L276–284** `def _save_disk_copy`
  - **L286–297** `def _load_disk_copy`
  - **L299–434** `def _build`  
    Builds every structure from rows of the knowledge database. Rows of the same disease, symptom or medicine from several sources are merged by name; an `enrich` row only adds other names and text to a row that exists without it.
  - **L436–453** `def _embed_cached`  
    Symptom vectors, computed once per data version and kept on disk.
  - **L457–505** `def match_symptoms`  
    Matches each of the patient's symptoms, given as a group of wordings for it (clinical term, their own words). Returns the matches and the symptoms nothing was found for.
  - **L507–522** `def find_in_text`  
    Symptom names that literally occur in free text, longest first. A safety net for when the language model's phrase list misses one.
  - **L524–584** `def retrieve`  
    Evidence for a patient. `groups` holds one list of wordings per symptom; `free_text` is the raw description they came from.
  - **L586–588** `def disease_names`  
    Every disease name held in memory (for the doctor's type-ahead).
  - **L590–597** `def mentions_drug`  
    True when the text names a medicine from the knowledge base.
  - **L599–622** `def lookup`  
    The knowledge-base disease a condition name refers to, when the search did not surface it: same name or alias, or a disease whose name is contained in the condition ("acute bacterial cystitis").
  - **L624–637** `def _candidate`

## `backend/app/languages.py` (41 lines)

The languages a patient can use at the kiosk, in one place.

The patient's report (screen and PDF) is given in ONE language: the one the
patient used (the user's rule of 2026-10-28). English is always prepared too,
because the checks in patient_view.py compare against it, but it is shown
only to English speakers.

To add a language: an entry here (its name, and the letters its script uses,
so patient_view can tell a translation from English), its labels in
report_pdf.py (`_L` and the small tables beside it) and a font for its script
there, its strings class in frontend/lib/l10n/strings.dart, and its code in
the `language` fields of schemas.py and handoff/router.py.

Functions and classes:
- **L23–25** `def supported`  
  The language code to use: the visit's, or English if it is unknown.
- **L28–29** `def name`
- **L32–35** `def in_script`  
  Whether the text contains letters of that language's own script.
- **L38–40** `def any_local_script`  
  Whether the text contains letters of any non-Latin kiosk language.

## `backend/app/llm.py` (247 lines)

Text LLM access for report generation: Gemini online, Ollama offline.

Online the report runs on Gemini. Offline (`main.py` picks by
`runtime.online`) it runs on a local medical model through Ollama
(`offline_model`, MedGemma), which goes through the same pipeline, review
and code rules. A local model that is not a clinical one (`clinical=False`,
the small fallback summariser) is never trusted with conditions or
medicines: see `clinical()`.

Uses (inside the app): `settings`

Settings and constants:
- **L25** `RETRY_WAITS`
- **L29** `CALL_TIMEOUT`
- **L100** `MAX_ANSWER_TOKENS`

Functions and classes:
- **L32–34** `def is_transient`
- **L37–55** `async def with_retries`  
  Runs `call()` again after a short wait when the failure is transient. Each attempt gets at most `timeout` seconds; a second time-out ends it.
- **L58–59** `class LlmError`
- **L62–78** `class Llm`
  - **L68–78** `async def json`  
    `thinking` caps a hosted model's reasoning tokens (0 = none); None leaves the model's default. Less thinking answers sooner. `answer_tokens` caps the local model's answer (a short verdict needs a few hundred) and `schema` (a JSON schema) makes it fill in exactly that form, so it cannot ramble or break the JSON; hosted models ignore both.
- **L81–87** `def clinical`  
  Whether the model that gave the last answer may write conditions and medicines.
- **L90–97** `def _parse`
- **L103–154** `class OllamaLlm`
  - **L109–117** `def __init__`
  - **L119–154** `async def json`
- **L157–193** `class GeminiLlm`
  - **L160–163** `def __init__`
  - **L165–193** `async def json`
- **L196–216** `class FallbackLlm`  
  Tries each model in order; this is the online -> offline switch.
  - **L199–202** `def __init__`
  - **L204–216** `async def json`
- **L219–224** `def make_llm`
- **L227–238** `def make_report_llm`  
  The chain for the final report's writer, check and review: the report model, then the main model, then the small local one (which may not write clinical content). None when no separate report model is set.
- **L241–246** `def make_offline_llm`  
  The local medical model the whole report runs on without internet, or None when none is configured (then only the plain summary is made).

## `backend/app/main.py` (245 lines)

Uses (inside the app): `db`, `doctor`, `handoff`, `hospital`, `ingest.planner`, `kb.embed`, `kb.retrieve`, `kb.stats`, `kb.uploads`, `knowledge_base`, `llm`, `models`, `offline`, `panel`, `patients`, `progress`, `routers`, `settings`, `tenancy`, `voice`

Functions and classes:
- **L36–44** `class _WebApp`  
  The built web app; a plain 404 while there is no build yet.
  - **L39–44** `async def get_response`
- **L47–61** `def make_retriever`
- **L64–241** `def create_app`

## `backend/app/models.py` (188 lines)

Uses (inside the app): `db`

Functions and classes:
- **L10–11** `def new_id`
- **L14–15** `def now`
- **L18–54** `class IntakeSession`  
  One patient's confirmed intake from the kiosk.
- **L57–65** `class TriageReport`  
  The generated report for one intake session.
- **L68–91** `class Tenant`  
  A client (hospital) and what its kiosks are allowed to offer.
- **L94–107** `class ActivityLog`  
  What happened, per client: the back office's monitoring feed.
- **L110–123** `class AdminUser`  
  Someone who may sign in to the back office.
- **L126–134** `class AdminSession`  
  A signed-in browser. Only a hash of its token is stored.
- **L137–150** `class ApiKey`  
  Lets a client's own system call the Medora API instead of a kiosk.
- **L153–165** `class ApiRequestLog`  
  One request made with an API key.
- **L168–174** `class SystemSetting`  
  Settings the back office can change without editing the server's files.
- **L177–185** `class FeatureConfig`  
  Legacy single-client switches; read once to seed the default client.

## `backend/app/offline.py` (200 lines)

Working without internet, with no local database.

Supabase is the only database (the user's decision of 2026-10-17, kept on
2026-10-18 when offline reports were added). Without internet it cannot be
reached, so this module keeps, in memory only:

- what is needed to serve a kiosk: each client's switches by kiosk key, the
  API keys, and the back-office sign-ins seen while online (so a preview
  opened from the back office keeps working);
- each visit and its report, so the patient gets the report and its PDF;
- activity-log lines that could not be written.

When the internet returns, `flush` copies the visits, reports and log lines
into Supabase. Nothing is written to disk: if the server stops while
offline, what was not yet copied is lost, and a server started without
internet has nothing to serve from (start it online).

Uses (inside the app): `models`, `patients`, `tenancy`

Settings and constants:
- **L37** `KEEP_STORED`
- **L39** `MAX_VISITS`
- **L42** `ADMIN_GRACE`
- **L45** `UNREACHABLE`

Functions and classes:
- **L48–50** `def _snapshot`  
  A detached copy of a row's columns, safe to keep after its session.
- **L53–63** `class Visit`
  - **L61–63** `def pending`
- **L66–199** `class OfflineState`
  - **L67–78** `def __init__`
  - **L82–87** `def remember_tenant`
  - **L89–91** `def remember_api_key`
  - **L93–98** `def remember_admin`  
    A sign-in checked against the database just now. Offline it is trusted for `ADMIN_GRACE` more, never past the server's life.
  - **L102–103** `def tenant_for_key`
  - **L105–106** `def tenant_by_id`
  - **L108–112** `def tenant_for_api_key`
  - **L114–116** `def admin_signed_in`
  - **L120–123** `def add_visit`
  - **L125–128** `def visit`
  - **L130–134** `def set_report`
  - **L136–138** `def pending`
  - **L140–146** `def _trim`
  - **L150–161** `def record`  
    `tenancy.record` when online; queued for `flush` when not.
  - **L165–199** `def flush`  
    Copies what waited into Supabase. Returns how many rows.

## `backend/app/panel.py` (538 lines)

The specialist panel: one CrewAI agent per medical specialty.

Instead of one model answering everything, the specialists a case concerns
read it and the knowledge-base evidence at the same time, each as their own
agent. A specialist who finds the case is outside their field steps aside
and takes no further part; the panel chair weighs the remaining opinions
against each other and writes the joint conclusion.

The patient's name, phone and email are never part of the case text.

Uses (inside the app): `llm`

Settings and constants:
- **L29** `PEDIATRICS`
- **L30** `OBGYN`
- **L36** `GENERAL_OPD`
- **L37** `EMERGENCY_DEPT`
- **L186** `DEPARTMENTS`
- **L188** `SPECIALIST_OUTPUT`
- **L246** `CHAIR_OUTPUT`
- **L354** `CHAIR_STORY`
- **L493** `_T`
- **L494** `_LIST`
- **L495** `_LEVEL`
- **L496** `_URGENCY`
- **L503** `CHAIR_FORM`
- **L513** `SPECIALIST_FORM`

Functions and classes:
- **L40–46** `class Specialty`  
  What one specialist on the standard roster knows about their own job.
- **L325–329** `class PanelResult`
- **L332–333** `class PanelError`
- **L336–351** `def parse_json`  
  The JSON object in a model reply, tolerating code fences and chatter.
- **L362–375** `def backstory`  
  What makes an agent this specialist rather than a general model.
- **L378–488** `class SpecialistPanel`  
  Runs the panel on Gemini through CrewAI.
  - **L381–387** `def __init__`
  - **L389–417** `async def _ask`  
    One agent's answer, as text. The chair thinks more.
  - **L419–488** `async def run`  
    Each specialist reads the case at the same time. Those who find it is not theirs step aside; the chair concludes from the rest. `progress` (a `progress.ReportProgress`) hears each answer.
- **L499–500** `def _form`
- **L522–537** `class LocalPanel`  
  The same panel, with the same agents and instructions, on the local medical model (no internet). Each agent is asked directly in JSON mode: CrewAI's own prompt scaffolding adds hundreds of tokens per call, which a laptop CPU pays for in tens of seconds. Ollama answers one call at a time, so the specialists take turns.
  - **L529–531** `def __init__`
  - **L533–537** `async def _ask`

## `backend/app/patient_view.py` (337 lines)

The patient's report, in the patient's own language.

The report the pipeline writes is clinical English: it is what the safety
reviews and rules check, and what the doctor reads. The patient reads
`patientView`, built here from that checked report and the visit:

  patient details, what they told us (symptoms, since when, medicines
  taken, allergies), vitals, a short summary, possible conditions (a plain
  name and one sentence about each, with the AI's estimate as a percentage:
  the user's choice of 2026-10-29, replacing likelihood words only), medicines (name,
  form and strength, how to take it, what it is for, caution), precautions
  and lifestyle advice.

Every text is given as {"en": simple English, "<code>": the visit's
language}: English is always prepared (the checks below compare against
it), the visit's language only when it is not English. The screen and PDF
show ONE language, the visit's (`view["language"]`; the user's rule of
2026-10-28, replacing the manager's two-language report of 2026-10-22).
Languages are listed in languages.py. One Gemini call rewrites the
patient-facing texts in plain words and translates them; it may not add or
drop information. Guards in code:

- How to take a medicine is assembled here from the reviewed dose,
  frequency, duration and daily maximum; the model only translates it.
- Every number in a source text must appear in what comes back, or the
  source English is kept and the translation dropped for that item.
- A sensitive word (sensitive.py) the source did not have is removed.
- A wrong item count drops the whole rewrite.

Without Gemini (offline, or a failure) the view is the report's own English
(`translated: false`), and the kiosk says so in the patient's language.

Uses (inside the app): `llm`, `triage`

Settings and constants:
- **L42** `_PROMPT`
- **L84** `_NUMBER`
- **L119** `_NOTHING`

Functions and classes:
- **L68–82** `def _prompt`
- **L87–88** `def _numbers`
- **L91–98** `def _pair`
- **L101–115** `def how_to_take`  
  The dose instruction, from the reviewed fields only.
- **L124–127** `def _said`  
  The patient's answer, or "" when it only says there is nothing.
- **L130–166** `def _items`  
  (where it goes, task, source text) for every patient-facing text.
- **L169–186** `def _percents`  
  Each listed condition's percentage, the same number the doctor sees (doctorView), else worked out the same way (triage.with_probabilities).
- **L189–237** `def _skeleton`  
  The view's shape, with the structured parts filled in and every text still empty.
- **L240–244** `def _put`
- **L247–252** `def _clean`  
  Drops the list entries no text was found for.
- **L255–264** `def plain_view`  
  The view without a model: the report's own English, untranslated.
- **L267–302** `def _check`  
  What may be shown for one item: the model's text where it keeps the source's numbers and adds no sensitive word, the source otherwise. `local` is the text in the visit's language (empty for English).
- **L305–336** `async def build_patient_view`  
  The patient's report in their language. Never raises: without the model it falls back to `plain_view`.

## `backend/app/precautions.py` (220 lines)

The patient's precautions: from the knowledge base when it has them,
written for the case when it does not.

Either way nothing reaches the patient unchecked:

  1. Knowledge-base precautions for the likely conditions are the first
     choice, but they describe the disease in general (prevention, recovery),
     so a model picks the ones that suit this patient right now. It may only
     select, never reword them.
  2. If too few suit, the same step writes new ones under strict rules.
  3. Rules in code remove anything naming a medicine, a dose or a diagnosis.
  4. A second, independent model pass reviews every written line for safety
     and drops any it objects to. Lines from the knowledge base are not
     reviewed again; they were already chosen as stored.

Uses (inside the app): `ingest.transform`, `knowledge_base`, `llm`

Settings and constants:
- **L26** `MAX_PRECAUTIONS`
- **L28** `MAX_FROM_KNOWLEDGE`
- **L30** `ENOUGH_FROM_KNOWLEDGE`
- **L32** `EMERGENCY_FIRST`
- **L34** `_SELECT`
- **L75** `_REVIEW`
- **L89** `_FORBIDDEN`

Functions and classes:
- **L97–104** `def acceptable`  
  The rules a written precaution must pass before any model review.
- **L107–118** `def from_knowledge`  
  Stored precautions for the conditions the panel thinks likely or possible, the most likely condition's first.
- **L121–122** `def _numbered`
- **L125–135** `def _numbers`
- **L138–191** `async def choose`  
  The precautions to show, and where they came from: "knowledge_base", "written", "mixed", or "none". With `select` false (offline, where each model call takes minutes) no model is asked: the stored lines for a calm case, as when the selection fails.
- **L194–205** `async def _reviewed`  
  Written lines that an independent pass did not object to. If the review cannot run, written lines are not shown at all.
- **L208–219** `def _finish`

## `backend/app/progress.py` (79 lines)

Live progress of a report being generated, for the kiosk's waiting screen.

Kept in memory: it describes work in flight and means nothing after a
restart. Everything recorded here is what the pipeline is actually doing;
the screen must not show more than this says.

Uses (inside the app): `panel`

Settings and constants:
- **L16** `STAGES`

Functions and classes:
- **L19–60** `class ReportProgress`
  - **L20–31** `def __init__`
  - **L33–35** `def show`
  - **L37–40** `def at`
  - **L42–44** `def panel`
  - **L46–48** `def answered`
  - **L50–60** `def to_json`
- **L63–78** `class ProgressBoard`  
  The reports in flight, newest last; old entries fall off.
  - **L66–68** `def __init__`
  - **L70–75** `def start`
  - **L77–78** `def get`

## `backend/app/report_pdf.py` (514 lines)

Uses (inside the app): `models`, `patient_view`

Settings and constants:
- **L20** `_PINE`
- **L21** `_ACCENT`
- **L22** `_MUTED`
- **L23** `_BORDER`
- **L24** `_SAGE`
- **L28** `_ORDER`
- **L29** `_L`
- **L74** `_URGENCY`
- **L80** `_STATUS`
- **L81** `_LIKELIHOOD`
- **L82** `_GENDER`
- **L83** `_FORM`
- **L88** `_VITAL`
- **L118** `_FONTS`
- **L119** `_MALAYALAM`
- **L120** `_RUNS`
- **L385** `_FINAL`

Functions and classes:
- **L96–106** `def _say`  
  One text in the report's language: a label tuple (in _ORDER) or a patient-view text {"en": ..., "<code>": ...}; English when the language's text is missing.
- **L109–111** `def _report_language`
- **L125–142** `def _register_fonts`
- **L145–163** `def _markup`  
  Escaped text with every word that contains Malayalam set in the Malayalam font. Whole words, punctuation included: ReportLab shapes a word as one piece, and a word split across two fonts breaks the PDF.
- **L166–338** `def render_pdf`  
  The patient's report in the patient's language (patient_view.py), and a last page for the doctor in clinical English when no doctor reviews the report in the doctor portal.
- **L341–382** `def _doctor_page`  
  For the doctor, in clinical English: what the safety-checked report says. Stands in for the doctor portal until it is built.
- **L399–513** `def render_final_pdf`  
  The doctor's signed report: hospital letterhead, the patient, the diagnosis, medicines with how to take them, tests, advice, follow-up and the doctor's name and registration number; in the patient's language.

## `backend/app/report_writer.py` (764 lines)

The last step of a report: a writer drafts it in full, including medicines
with doses, a separate reviewer checks it, and rules in code have the final
word. Nothing a model writes reaches the report unchecked.

  1. Writer: from the case, the vitals assessment, the knowledge-base
     evidence and the specialist panel's conclusion, it writes the clinical
     summary and the medicines (with dose, frequency, duration and cautions),
     and fills what the panel left out (lifestyle advice, points for the
     doctor). Without a panel it also names the possible conditions.
  2. Reviewer: an independent pass, told to act as a cautious clinical
     pharmacist. It approves or rejects each medicine and checks that the
     summary claims nothing the case does not show. It can only remove,
     never add or reword.
  3. Code: no medicines for children under 12 (doses depend on weight) or for
     an emergency; no controlled drugs; a dose must look like a dose;
     prescription medicines are marked; a woman who could be pregnant gets a
     pregnancy check on every medicine. If the reviewer cannot be reached,
     no written medicine is shown.

Medicines are suggestions for the treating doctor, never instructions for
the patient, and the report says so.

Uses (inside the app): `ingest.transform`, `llm`

Settings and constants:
- **L32** `MAX_MEDICINES`
- **L34** `_WRITER`
- **L157** `_FIT`
- **L183** `_REVIEW`
- **L227** `_CONTROLLED`
- **L233** `_PRESCRIPTION`
- **L240** `_SAFE_IN_PREGNANCY`
- **L245** `_DOSE`
- **L246** `_TOPICAL`
- **L247** `_STRENGTH`
- **L248** `_APPLY`
- **L343** `_TEXT`
- **L344** `FIT_FORM`
- **L347** `REVIEW_FORM`
- **L376** `_BRANDS`
- **L388** `_MALAYALAM_NAMES`
- **L405** `_ALLERGY_FAMILIES`
- **L421** `_FORMS`

Functions and classes:
- **L251–258** `def _usable_dose`  
  A dose with an amount; for a skin preparation, how to apply it with its strength (permethrin 5% cream: "apply a thin layer from the neck down").
- **L261–262** `def _text`
- **L265–268** `def _list`
- **L271–276** `def _medicines_raw`
- **L279–281** `def drafted_medicines`  
  The draft's medicines as the review numbers them.
- **L284–295** `def _numbered_medicines`
- **L298–309** `def _approved`
- **L312–322** `def _review_reasons`
- **L325–333** `def _rule_reason`
- **L339–340** `def _form`
- **L355–367** `def _kept`  
  Conditions the check kept, each with a reason from the case.
- **L370–372** `def _local`  
  A small general model answered: not trusted with medicines.
- **L396–400** `def _generics`  
  What the patient took, with brand names spelled out as generics.
- **L427–438** `def _form`  
  The dosage form as one of `_FORMS`, or a guess from the route.
- **L441–451** `def _allergic`  
  Whether the patient reported an allergy to this medicine or its family. "none" and the like name nothing.
- **L454–455** `def _could_be_pregnant`
- **L458–477** `def _material`
- **L480–506** `async def draft`  
  The writer's draft. `panel` is the chair's conclusion, or None when the panel did not run, in which case the draft names conditions too. `known_medicines` maps knowledge-base medicines linked to the listed conditions to what they are used for.
- **L509–519** `def written_conditions`  
  Conditions a draft named (only when there was no panel).
- **L522–565** `async def check_conditions`  
  Its own focused pass: which conditions fit what the patient said. The names kept, or None when the check could not be made.
- **L568–573** `class Kept`  
  The condition names a check kept, with `reasons` for the others.
  - **L571–573** `def __init__`
- **L576–640** `async def finish`  
  The independent review of a draft, then the rules in code. Without the review, nothing written is shown. `conditions` are the ones that stand after the condition check.
- **L643–654** `def label`  
  Marks each medicine as from the knowledge base (with its stored name) or suggested, against the knowledge-base medicines of the listed conditions.
- **L657–679** `def _rules`  
  The rules no model can override. Returns the medicines a patient may see and, when there are none, why. `doctor_medicines` gives the wider list only a doctor sees.
- **L682–701** `def doctor_medicines`  
  Every reviewed medicine a doctor may consider: those a patient may see, plus injections, weight-based children's doses and emergency treatment, each marked `doctorOnly`. Controlled drugs, allergies and malformed doses are still refused. Nothing without the review.
- **L704–763** `def _checked`  
  (for the patient, for the doctor) after the rules in code.

## `backend/app/schemas.py` (159 lines)

Functions and classes:
- **L8–13** `class ApiModel`  
  JSON is camelCase on the wire, snake_case in Python.
- **L16–26** `class FeatureConfigBody`
  - **L22–26** `def _one_way_in`
- **L29–46** `class VitalsBody`  
  The readings the band took. A band measures only what its hardware supports, so any value may be missing, but not all of them, and blood pressure comes as a pair.
  - **L40–46** `def _complete_enough`
- **L49–74** `class SessionCreate`
- **L77–81** `class SessionOut`
- **L84–86** `class Capability`
- **L89–105** `class Status`  
  What this server can do right now, so the kiosk only offers what works.
- **L108–123** `class TenantCreate`
  - **L119–123** `def _one_way_in`
- **L126–132** `class TenantUpdate`
- **L135–149** `class TenantOut`
- **L152–158** `class LogOut`

## `backend/app/sensitive.py` (79 lines)

Words the kiosk report never shows unless the patient raised them.

A kiosk report is read by the patient, often with family beside them. The
user decided on 2026-10-18 that pregnancy and sexual-health conditions and
advice must never appear in it on the AI's initiative ("it should not even
ever suggest those kind of words"). Clinically, though, a woman of
child-bearing age with lower abdominal pain must have a pregnancy test
before imaging or most medicines, and missing an ectopic pregnancy can
kill. So the report keeps that step for the doctor in neutral clinical
wording (LMP, urine hCG), and drops every line that names the topic.
If the patient mentioned it themselves, nothing is hidden.

Settings and constants:
- **L16** `_SENSITIVE`
- **L27** `DOCTOR_CHECK`

Functions and classes:
- **L30–31** `def raised_by_patient`
- **L34–35** `def mentions`
- **L38–40** `def strip_sentences`  
  The text without the sentences that name the topic.
- **L43–46** `def _sentences`  
  The text without the sentences that name the topic.
- **L49–73** `def clean`  
  The report with sensitive conditions, advice and wording removed, unless the patient raised the topic, or answered yes or unsure when the voice agent asked whether she could be pregnant. Changes `report` in place.
- **L76–78** `def _abdominal`

## `backend/app/settings.py` (103 lines)

Functions and classes:
- **L6–102** `class Settings`

## `backend/app/tenancy.py` (124 lines)

Clients (tenants), their kiosk keys, and the activity log.

Uses (inside the app): `db`, `models`

Settings and constants:
- **L17** `_ADDED_COLUMNS`
- **L106** `HOSPITAL_EVENTS`

Functions and classes:
- **L28–39** `def ensure_schema`  
  Creates the app's tables and adds any column an older database lacks.
- **L42–43** `def hash_key`
- **L46–49** `def new_kiosk_key`  
  A fresh key, its hash, and a hint to recognise it by.
- **L52–68** `def ensure_default_tenant`  
  Kiosks that send no key belong to the default client. It inherits the switches of the old single-client setup the first time it is created.
- **L71–74** `def new_api_key`  
  A fresh API key, its hash, and a hint to recognise it by.
- **L77–81** `def find_api_key`  
  The live API key with this value, if any.
- **L84–86** `def get_setting`
- **L89–94** `def set_setting`
- **L97–100** `def find_tenant`
- **L109–123** `def record`  
  Writes one activity-log line in its own transaction, so it survives whatever happens to the request that caused it. Never raises.

## `backend/app/triage.py` (793 lines)

Builds the triage report from a confirmed intake.

1. Symptom understanding   a model turns the patient's words into symptom
                           terms and suggests which specialists to consult
2. Evidence                the knowledge base is searched and candidate
                           diseases are scored (no model involved)
3. Specialist panel        CrewAI agents, one per specialty, give opinions
                           and a chair concludes (online); offline, a single
                           local model writes the summary instead
   Precautions             from the knowledge base when it has suitable
                           ones, otherwise written and safety-reviewed
                           (precautions.py)
4. Safety and grounding    code, not a model, has the last word: vitals set
                           a minimum urgency, and only medicines that the
                           knowledge base links to the conditions are kept

Uses (inside the app): `ingest.transform`, `kb`, `kb.drugnames`, `knowledge_base`, `llm`, `models`, `panel`, `progress`, `vitals`

Settings and constants:
- **L49** `URGENCY`
- **L50** `LIKELIHOOD`
- **L52** `DISCLAIMER`
- **L140** `_UNDERSTAND`
- **L367** `_DEFAULT_PERCENT`
- **L426** `_SOLO`
- **L441** `OFFLINE_NOTE`
- **L535** `FALLBACK_NOTE`

Functions and classes:
- **L60–61** `def _raise`
- **L64–80** `def vital_lines`  
  Each vital as (label, value); one the band did not measure says so.
- **L83–135** `def vital_flags`  
  Out-of-range vitals and the minimum urgency they require.
- **L172–207** `def _case_lines`
- **L210–236** `async def understand`  
  The patient's symptoms, each as a group of wordings for it, the specialists to consult, and up to 3 conditions to look up in the guidelines. Falls back to the raw text and general medicine when the model cannot be used.
- **L239–252** `def choose_panel`  
  Who is asked to look at the case: the specialists the screening found it concerns, in order of relevance, up to `size`. Children always get a paediatrician. Specialists who cannot apply to this patient are never asked. The list may be empty: a complaint no specialty owns goes to the panel chair alone, who is a general physician.
- **L263–278** `def _evidence_text`
- **L284–287** `def _strings`
- **L290–292** `def _one_of`
- **L295–309** `def _candidate_for`  
  The knowledge-base candidate a condition name refers to: the same name or another name of it ("scabies" for Acariasis), or a name that contains it ("acute myocardial infarction").
- **L312–355** `def _conditions`  
  The panel's conditions, each tied back to the evidence where there is any.
- **L358–363** `def _percent`
- **L370–384** `def with_probabilities`  
  Every condition with a consistent "AI estimate" percentage, for the doctor: missing ones filled from the likelihood, never above 100 in total, and never higher than a condition listed before it.
- **L387–393** `def _add_named_conditions`
- **L396–406** `def _known_medicines`  
  Knowledge-base medicines linked to the listed conditions, with what they are used for. (Stored dosage text is not trusted: the sources were inconsistent about it.)
- **L409–413** `def _hosted`  
  Whether the last answer came from a clinical model (Gemini, or the offline medical model). The small general model is not trusted with conditions or medicines.
- **L416–421** `def _patient_advice`  
  Advice lines for the patient, without any that name a medicine: medicines are for the doctor to decide, whatever the model wrote.
- **L447–457** `def _department`  
  One of `DEPARTMENTS`. An emergency always goes to the emergency department, whatever the model said; a child (under 16, as for the panel) whom the model sent to General OPD goes to Pediatrics.
- **L460–514** `def _report`
- **L517–532** `async def _solo`  
  One model writes the summary. It is not trusted to name conditions or medicines: a small offline model gets those wrong too often.
- **L541–545** `async def fallback_report`  
  A plain report for when the full pipeline failed unexpectedly: the patient still leaves with a summary, urgency and advice.
- **L548–792** `async def build_report`  
  `progress`, when given, follows each step for the waiting screen. `history` is the patient's earlier, doctor-confirmed visits (patients.service.history_text), empty for a new patient. `retriever` (app.kb.retrieve.Retriever) searches the guideline database twice: before the panel (pass 1) and before the writer (pass 2). `writer_llm` (optional, `gemini_report_model`) writes the final report: the draft, the condition check and the pharmacist review; it falls back to the main model on its own. `lean` (offline, on the slow local model): the stored precautions are used without a model choosing among them, and the case carries fewer, shorter guideline passages.

## `backend/app/vitals.py` (82 lines)

Each measured vital against its normal range, for the report.

Done in code, never by a model: the ranges are fixed and the same reading
must always get the same verdict. They are common adult resting ranges and,
like the urgency thresholds in `triage.vital_flags`, await clinician review.
Heart rate and blood pressure are not judged for children, whose normal
ranges depend on age.

Functions and classes:
- **L11–13** `def _row`
- **L16–70** `def assess`  
  The measured vitals, each with its normal range and a verdict. Vitals the band did not measure are left out.
- **L73–81** `def describe`  
  The assessment as one line for a model to read.

## `backend/app/vitals_need.py` (74 lines)

Whether a complaint calls for vitals at all.

A knee sprain or low mood does not need a heart rate and oxygen reading, and
making every patient wear the band slows the kiosk down. One quick model
call decides from what the patient said; anything uncertain, and any
failure, means vitals ARE taken. Used by the form flow (`POST
/api/intake/vitals-check`) and by the voice agent (`voice.py`).

Uses (inside the app): `llm`

Settings and constants:
- **L16** `_DECIDE`

Functions and classes:
- **L45–73** `async def vitals_needed`  
  (needed, reason). Only a clear "not needed" from the hosted model skips the vitals.

## `backend/app/voice.py` (744 lines)

Voice intake conversation.

Wire protocol on `/ws/voice` (the browser never talks to the model directly,
so the API key stays on the server):

  browser -> server
    binary                 microphone audio, PCM16 mono 16 kHz
    {"type": "start", "smartBand": bool, "language": "auto" | "en" | "ml",
     "known": {...intake fields}, "vitalsTaken": bool}
                           "auto": Medora greets in English and follows the
                           patient's language (answers `language`); "ml"
                           greets in Malayalam. `known`: details the kiosk
                           already holds (the page was reloaded mid-visit),
                           so Medora carries on instead of starting over
    {"type": "vitals", "captured": bool, ...readings}   answer to request_vitals
    {"type": "pause"} | {"type": "resume"}   staff paused the conversation
                           (noise, an interruption); on resume Medora repeats
                           her last question

  server -> browser
    binary                 Dr. Medora's voice, PCM16 mono 24 kHz
    {"type": "ready"} | {"type": "unavailable", "reason": str}
    {"type": "transcript", "role": "patient" | "medora", "text": str}
    {"type": "interrupted"}        patient spoke over Medora: stop playback
    {"type": "turn_complete"}
    {"type": "intake", "fields": {...}}   details heard so far
    {"type": "language", "language": "en" | "ml"}   the patient's choice
    {"type": "request_vitals"}
    {"type": "vitals_skipped", "reason": str}   this complaint needs no vitals
    {"type": "complete"}           intake finished: go to review
    {"type": "error", "message": str}

Uses (inside the app): `settings`

Settings and constants:
- **L219** `INTAKE_FIELDS`
- **L238** `SPEECH`
- **L240** `TRANSCRIBE_LANGUAGES`
- **L245** `GREETING`
- **L250** `CARRY_ON`
- **L252** `_ASK_LANGUAGE`
- **L448** `_FOOTER`
- **L458** `RESUMED`
- **L722** `VOICE_UNAVAILABLE`
- **L723** `VOICE_NEEDS_INTERNET`

Functions and classes:
- **L48–62** `class VoiceContext`
- **L65–208** `class IntakeTools`  
  The model's tool calls, kept apart from the Gemini plumbing so they can be tested: saving details, deciding on vitals, and making sure the band is used at most once per conversation.
  - **L74–93** `def __init__`
  - **L110–120** `async def _needed`
  - **L122–171** `async def call`
  - **L173–176** `def vitals_done`  
    The band has measured (or failed) once in this conversation.
  - **L178–184** `def drop_pending`  
    The pending request_vitals call can no longer be answered (a new line to the model, or the model cancelled it); the measurement goes on and its result is sent as a message.
  - **L186–208** `def vitals_measured`  
    The kiosk's answer to request_vitals, as (call id, response); the call id is None when the call was dropped (send it as a message).
- **L211–216** `class VoiceProvider`
  - **L214–216** `async def run`
- **L266–291** `def _language_rules`
- **L294–315** `def _vitals_step`
- **L318–333** `def _carry_on`  
  For a conversation that restarts mid-visit (the page was reloaded, or the line to the model dropped): what is already saved.
- **L336–398** `def system_instruction`
- **L401–442** `def tool_declarations`  
  `decide_vitals`: offer vitals_needed (vitals only when the complaint calls for them); without it vitals are always taken.
- **L451–453** `def clean_transcript`  
  Medora's words without the service's disclaimer footer.
- **L465–495** `def clean_intake`  
  Keeps only known fields with usable values.
- **L498–499** `class _LineDropped`  
  The line to the model closed in the middle of the conversation.
- **L502–706** `class GeminiLiveProvider`  
  Online voice through the Gemini Live API.
  - **L514–518** `def __init__`
  - **L520–542** `def _config`
  - **L544–575** `async def run`
  - **L577–706** `async def _session`
- **L709–719** `def make_voice_provider`  
  The provider to use, or None when voice cannot run on this server.
- **L726–738** `def pick_provider`  
  The provider to use right now, or None with the reason there is none.
- **L741–743** `def voice_capability`
