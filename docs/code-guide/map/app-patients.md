# `app/patients`

## `backend/app/patients/__init__.py` (8 lines)

Patient records: one per person per hospital, so a returning patient's
visits are linked and the doctor (and the report AI) can use the history.

The kiosk only ever sees a masked first name and an age when it looks a
phone number up (several people often share one phone in India); the
history itself is shown only in the doctor portal.

(no functions)

## `backend/app/patients/models.py` (34 lines)

Uses (inside the app): `db`, `models`

Functions and classes:
- **L10–33** `class Patient`  
  A person known to one hospital. Health details are what the patient reported at their visits (merged); doctor-confirmed history lives in the doctor's reviews (`doctor.models.DoctorReview`).

## `backend/app/patients/service.py` (239 lines)

Finding, creating and updating patient records, and the history a
doctor (and the report AI) may use.

Uses (inside the app): `doctor.models`, `models`

Functions and classes:
- **L14–18** `def digits`  
  The number without spaces or a country code, for matching: the last ten digits (Indian mobile numbers).
- **L21–24** `def mask`  
  "Asha Rao" -> "A*** R***": enough for the patient to recognise themselves, not enough to tell a stranger who else uses the number.
- **L27–30** `def age_of`
- **L33–44** `def lookup`  
  The people this hospital knows under a phone number, masked.
- **L47–50** `def visit_code`  
  "ab12-cd" -> "ab12cd": a visit number as typed (the session id's first 6 characters, printed upper case on the report).
- **L53–80** `def lookup_visit`  
  "Have you visited before?" by an earlier visit number: the person that visit belongs to, by full name and age (the user's choice of 2026-10-29, so the patient can recognise themselves). Only this hospital's visits; a number shorter than 6 characters finds nothing.
- **L83–91** `def _merge`  
  Comma lists joined without repeats ("none" never stays beside items).
- **L94–107** `def same_person`  
  For a visit saved offline (no "Have you visited before?" was possible): this hospital's record with the same phone number and name, if exactly one matches.
- **L110–135** `def attach`  
  Links the visit to its patient (the one picked at the kiosk, if it is this hospital's) or a new record, and merges what was reported now. In the caller's transaction.
- **L138–179** `def history_text`  
  For the report AI: the patient's earlier, doctor-confirmed visits and what they reported before. Empty for a new patient. Never the AI's own earlier guesses.
- **L182–219** `def timeline`  
  The patient's other visits, newest first, for the doctor portal.
- **L222–238** `def record_out`
