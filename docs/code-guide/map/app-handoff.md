# `app/handoff`

## `backend/app/handoff/__init__.py` (10 lines)

Filling the intake on the patient's own phone instead of the kiosk's
touchscreen (fewer hands on a shared screen, so less infection).

The kiosk opens a hand-off and shows its link as a QR code; the patient,
or a nurse helping them, scans it and fills the form on their phone; the
kiosk sees the details arrive and carries on with vitals and the report.
The code in the link is long and random and works for 30 minutes: it is
the only thing that lets the phone in.

(no functions)

## `backend/app/handoff/models.py` (23 lines)

Uses (inside the app): `db`, `models`

Functions and classes:
- **L10–22** `class PhoneHandoff`

## `backend/app/handoff/router.py` (185 lines)

`/api/handoffs`: the kiosk's side (open, wait, mark done), and the
phone's side (`/api/handoffs/{code}/phone`), which needs nothing but the
code from the QR.

Without internet it keeps working: the phone reaches the kiosk server over
the hospital's own Wi-Fi, and a hand-off opened while the database cannot be
reached is kept in memory (`offline.handoffs`) for its 30 minutes.

Uses (inside the app): `deps`, `hospital.models`, `models`, `offline`, `patients`, `schemas`

Settings and constants:
- **L27** `LIFETIME`

Functions and classes:
- **L30–31** `def _utc`
- **L34–46** `def _live`  
  The hand-off, from memory (opened offline) or the database.
- **L49–52** `def _save`  
  Changes to a hand-off in memory are already kept; a row is committed.
- **L55–56** `class Opening`
- **L59–84** `def open_handoff` — route `POST /api/handoffs`; called from: `frontend/lib/api/api_client.dart`  
  The kiosk asks for a code to show as a QR.
- **L87–93** `def kiosk_status` — route `GET /api/handoffs/{code}`; called from: `frontend/lib/api/api_client.dart`  
  The kiosk waits for the phone; once submitted, it gets the details.
- **L96–97** `class Done`
- **L100–111** `def kiosk_done` — route `POST /api/handoffs/{code}/done`; called from: `frontend/lib/api/api_client.dart`  
  The kiosk saved the visit: the phone can now follow its report.
- **L117–133** `def phone_view` — route `GET /api/handoffs/{code}/phone`; called from: `frontend/lib/api/api_client.dart`
- **L136–152** `class PhoneIntake`
- **L155–163** `def phone_submit` — route `POST /api/handoffs/{code}/phone`; called from: `frontend/lib/api/api_client.dart`
- **L166–169** `class VisitLookup`  
  An earlier visit number (printed on the report), e.g. "AB12CD".
- **L172–184** `def phone_lookup` — route `POST /api/handoffs/{code}/phone/patients`; called from: `frontend/lib/api/api_client.dart`  
  "Have you visited before?" from the phone, by visit number. Offline the records cannot be read, so the visit starts a new one (as on the kiosk).
