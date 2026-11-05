# `app/doctor`

## `backend/app/doctor/__init__.py` (9 lines)

The doctor portal: the patient queue, the doctor's review of Medora's
report, and the signed final report the patient receives.

Doctors sign in with their hospital account (`app/hospital/`, role
`doctor`). The AI report is never changed: the doctor's decisions are kept
beside it in `DoctorReview`, so what the AI suggested and what the doctor
decided can always both be seen.

(no functions)

## `backend/app/doctor/catalogue.py` (326 lines)

Type-ahead suggestions for the doctor portal: medicines (with their usual
Indian strengths and forms, and brand names that lead to them), diagnoses
and tests.

The lists here are the common outpatient ones, so suggestions work without
any database. Diagnoses also come from the knowledge index in memory
(`knowledge_base`, 2,400 diseases); medicine names also come from the
guideline database (`kb_drugs`) when it can be reached. A suggestion only
fills in fields: the doctor still sets the dose and how often, and nothing
is signed without them.

Uses (inside the app): `ingest.transform`

Settings and constants:
- **L198** `DIAGNOSES`
- **L221** `TESTS`
- **L234** `ALIASES`
- **L245** `FOLLOW_UPS`
- **L250** `LIMIT`
- **L320** `_CLEAN`

Functions and classes:
- **L253–268** `def _rank`  
  0: the text starts with the query; 1: every query word starts a word of the text; 2: the query is somewhere in it; None: no match.
- **L271–277** `def _medicine`
- **L280–300** `def medicines`  
  Preparations whose name (or a brand of theirs) matches, best first; then other medicine names from the guideline database.
- **L303–317** `def names`  
  Diagnoses or tests: the common list first, then the rest.
- **L323–325** `def tidy`  
  A database name as a doctor would read it.

## `backend/app/doctor/models.py` (38 lines)

Uses (inside the app): `db`, `models`

Functions and classes:
- **L10–37** `class DoctorReview`  
  One doctor's consultation for one visit.

## `backend/app/doctor/router.py` (556 lines)

The doctor portal's API (`/api/doctor/...`) and the patient's view of
the doctor's result (`/api/sessions/{id}/final`).

A doctor works only on their own hospital's visits. Picking a patient locks
the visit to that doctor until they finalise or release it, so two doctors
never treat the same patient at once. The AI report is never edited: the
doctor's decisions go into `DoctorReview`, and finalising makes the signed
report the patient receives, in English or Malayalam, as the doctor chooses.

Uses (inside the app): `deps`, `hospital`, `hospital.models`, `models`, `offline`, `patient_view`, `patients`, `patients.models`, `report_pdf`, `schemas`

Settings and constants:
- **L33** `URGENCY_ORDER`
- **L36** `LOCK_HOURS`
- **L38** `QUEUE_HOURS`

Functions and classes:
- **L41–44** `def doctor`
- **L50–53** `def _utc`
- **L56–58** `def visit_number`  
  What the kiosk shows the patient and the doctor calls out.
- **L61–64** `def _locked_by_other`
- **L67–74** `def _own_visit`
- **L77–78** `def _my_department`
- **L84–96** `def whoami` — route `GET /api/doctor/me`; called from: no frontend file (API clients / tests)
- **L99–148** `def queue` — route `GET /api/doctor/queue`; called from: `frontend/lib/doctor/pages/queue_page.dart`  
  Patients with a Medora report from the last day who have not been finalised: the emergencies first, then by how long they have waited.
- **L151–153** `def _visits`
- **L159–174** `def _review_out`
- **L177–194** `def _ai_medicines`  
  Medora's suggestions as editable lines, marked as from Medora.
- **L197–228** `def pick` — route `POST /api/doctor/visits/{session_id}/pick`; called from: `frontend/lib/doctor/pages/consult_page.dart`, `frontend/lib/doctor/pages/queue_page.dart`, `frontend/lib/hospital/pages/visits_page.dart`  
  Takes the patient: locked to this doctor until finalised or released. The draft starts from Medora's suggested medicines and advice.
- **L231–240** `def release` — route `POST /api/doctor/visits/{session_id}/release`; called from: `frontend/lib/doctor/pages/consult_page.dart`, `frontend/lib/doctor/pages/queue_page.dart`, `frontend/lib/hospital/pages/visits_page.dart`  
  Puts the patient back in the queue for any doctor.
- **L243–299** `def visit` — route `GET /api/doctor/visits/{session_id}`; called from: `frontend/lib/doctor/pages/consult_page.dart`, `frontend/lib/doctor/pages/queue_page.dart`, `frontend/lib/hospital/pages/visits_page.dart`  
  Everything the doctor needs: what the patient said, the vitals, Medora's doctor report (all conditions with an AI percentage, all suggested medicines), the patient's history, and the draft.
- **L302–304** `class Diagnosis`
- **L307–317** `class MedicineLine`
- **L320–329** `class Draft`
- **L332–339** `def _mine`
- **L342–351** `class _InLanguage`  
  The visit as the patient-view builder reads it, in the language the doctor chose for the signed report (the stored visit is not changed).
  - **L346–348** `def __init__`
  - **L350–351** `def __getattr__`
- **L354–360** `def _apply`
- **L363–368** `def save_draft` — route `PUT /api/doctor/visits/{session_id}/draft`; called from: `frontend/lib/doctor/pages/consult_page.dart`, `frontend/lib/doctor/pages/queue_page.dart`, `frontend/lib/hospital/pages/visits_page.dart`
- **L371–447** `async def finalize` — route `POST /api/doctor/visits/{session_id}/finalize`; called from: `frontend/lib/doctor/pages/consult_page.dart`, `frontend/lib/doctor/pages/queue_page.dart`, `frontend/lib/hospital/pages/visits_page.dart`  
  Signs the consultation: the patient's final report is made from the doctor's decisions (never the AI's), in the language the doctor chose (English or Malayalam), with the doctor's name and registration number.
- **L450–473** `async def suggest` — route `GET /api/doctor/suggest`; called from: `frontend/lib/doctor/pages/consult_page.dart`  
  Type-ahead for the consultation: medicines (usual strength, form and route; brand names lead to the generic), diagnoses and tests. Fills in fields only; the doctor still sets the dose and how often.
- **L476–497** `def consultations` — route `GET /api/doctor/consultations`; called from: `frontend/lib/doctor/pages/consultations_page.dart`  
  This doctor's signed consultations, newest first.
- **L503–519** `def _final`  
  The visit, its doctor review and its report. Without internet (or the database out of reach) a visit made at this kiosk is read from memory: the patient's page then says it is waiting for the doctor.
- **L522–541** `def final_status` — route `GET /api/sessions/{session_id}/final`; called from: `frontend/lib/admin/sessions_tab.dart`, `frontend/lib/api/api_client.dart`, `frontend/lib/doctor/doctor_screen.dart`, `frontend/lib/hospital/hospital_api.dart`  
  For the patient's page (reached by the QR code on the kiosk): where their visit is, and the doctor's final report once signed. Guarded, like the report itself, by the visit's unguessable id.
- **L544–555** `def final_pdf` — route `GET /api/sessions/{session_id}/final.pdf`; called from: `frontend/lib/admin/sessions_tab.dart`, `frontend/lib/api/api_client.dart`, `frontend/lib/doctor/doctor_screen.dart`, `frontend/lib/hospital/hospital_api.dart`
