# `app/hospital`

## `backend/app/hospital/__init__.py` (11 lines)

The hospital admin portal (a tenant's own back office), kept apart from
the company back office in `routers/admin.py`.

Hospital people (hospital admins, doctors, staff) have their own accounts
and sessions (`models.HospitalUser`, `HospitalSession`), separate from the
company's back-office accounts: a hospital login can never open the company
back office, and the company's open registration never creates hospital
accounts. Every query here is scoped to the signed-in person's own hospital
(`service.scope`), never to a hospital named in the request.

(no functions)

## `backend/app/hospital/models.py` (107 lines)

Tables of the hospital portal. Created at startup with the app's own
tables (`tenancy.ensure_schema`), because they share `db.Base`.

Uses (inside the app): `db`, `models`

Settings and constants:
- **L15** `ROLES`

Functions and classes:
- **L18–42** `class HospitalUser`  
  Someone who works at one hospital: its admin, a doctor, or staff.
- **L45–53** `class HospitalSession`  
  A signed-in hospital browser. Only a hash of its token is stored.
- **L56–70** `class Department`  
  A department of the hospital; doctors belong to one, and the doctor queue (later) is per department.
- **L73–89** `class HospitalSettings`  
  How the hospital presents itself: on its reports and portal.
- **L92–106** `class AuditEntry`  
  Who did what in the hospital portal, including who opened which patient's record: health data needs that trail.

## `backend/app/hospital/router.py` (641 lines)

The hospital portal's API (`/api/hospital/...`), and the two company
back-office endpoints that open a hospital's portal by creating its first
administrators (`/api/admin/tenants/{id}/hospital-admins`).

Every hospital endpoint works on the signed-in person's own hospital
(`user.tenant_id`); none takes a hospital from the request.

Uses (inside the app): `deps`, `doctor.models`, `models`, `panel`, `schemas`, `service`, `tenancy`

Settings and constants:
- **L515** `_LOGO`
- **L516** `MAX_LOGO_BYTES`

Functions and classes:
- **L34–35** `def _fail`
- **L38–39** `def _iso`
- **L42–58** `def _user_out`
- **L61–68** `def _settings`
- **L71–78** `def _hospital_out`
- **L81–84** `def _departments`
- **L90–92** `class Credentials`
- **L95–103** `def login` — route `POST /api/hospital/auth/login`; called from: `frontend/lib/api/api_client.dart`, `frontend/lib/hospital/hospital_api.dart`
- **L106–108** `def me` — route `GET /api/hospital/auth/me`; called from: `frontend/lib/api/api_client.dart`, `frontend/lib/hospital/hospital_api.dart`
- **L111–116** `def logout` — route `POST /api/hospital/auth/logout`; called from: `frontend/lib/api/api_client.dart`, `frontend/lib/doctor/doctor_screen.dart`, `frontend/lib/hospital/hospital_screen.dart`
- **L119–121** `class PasswordChange`
- **L124–131** `def change_password` — route `POST /api/hospital/auth/password`; called from: `frontend/lib/hospital/hospital_login.dart`
- **L137–143** `def _local_midnight`
- **L146–159** `def _visit_rows`
- **L162–177** `def _visit_out`
- **L180–233** `def dashboard` — route `GET /api/hospital/dashboard`; called from: `frontend/lib/hospital/pages/dashboard_page.dart`
- **L239–242** `class DepartmentBody`
- **L245–252** `def _department_out`
- **L255–258** `def _check_report_department`
- **L261–277** `def list_departments` — route `GET /api/hospital/departments`; called from: `frontend/lib/hospital/pages/departments_page.dart`, `frontend/lib/hospital/pages/people_page.dart`
- **L280–296** `def create_department` — route `POST /api/hospital/departments`; called from: `frontend/lib/hospital/pages/departments_page.dart`, `frontend/lib/hospital/pages/people_page.dart`
- **L299–314** `def update_department` — route `PATCH /api/hospital/departments/{department_id}`; called from: `frontend/lib/hospital/pages/departments_page.dart`, `frontend/lib/hospital/pages/people_page.dart`
- **L320–328** `class PersonCreate`
- **L331–339** `class PersonUpdate`
- **L342–348** `def _own_department`
- **L351–355** `def _own_person`
- **L358–364** `def list_people` — route `GET /api/hospital/people`; called from: `frontend/lib/hospital/pages/people_page.dart`
- **L367–389** `def create_person` — route `POST /api/hospital/people`; called from: `frontend/lib/hospital/pages/people_page.dart`
- **L392–414** `def update_person` — route `PATCH /api/hospital/people/{person_id}`; called from: `frontend/lib/hospital/pages/people_page.dart`
- **L417–428** `def reset_password` — route `POST /api/hospital/people/{person_id}/reset-password`; called from: `frontend/lib/hospital/pages/people_page.dart`
- **L434–460** `def list_visits` — route `GET /api/hospital/visits`; called from: `frontend/lib/doctor/pages/consult_page.dart`, `frontend/lib/doctor/pages/queue_page.dart`, `frontend/lib/hospital/pages/visits_page.dart`
- **L463–481** `def visit` — route `GET /api/hospital/visits/{visit_id}`; called from: `frontend/lib/doctor/pages/consult_page.dart`, `frontend/lib/doctor/pages/queue_page.dart`, `frontend/lib/hospital/pages/visits_page.dart`
- **L487–498** `def audit_log` — route `GET /api/hospital/audit`; called from: `frontend/lib/hospital/pages/activity_page.dart`
- **L501–510** `def activity` — route `GET /api/hospital/activity`; called from: `frontend/lib/hospital/pages/activity_page.dart`  
  What the hospital's kiosks did: visits, reports, voice, errors.
- **L519–526** `class SettingsBody`
- **L529–538** `def _settings_out`
- **L541–545** `def get_settings_` — route `GET /api/hospital/settings`; called from: `frontend/lib/hospital/pages/settings_page.dart`
- **L548–565** `def put_settings` — route `PUT /api/hospital/settings`; called from: `frontend/lib/hospital/pages/settings_page.dart`
- **L571–575** `class AdminCreate`
- **L578–582** `def _company_tenant`
- **L585–593** `def list_hospital_admins` — route `GET /api/admin/tenants/{tenant_id}/hospital-admins`; called from: `frontend/lib/admin/clients_tab.dart`, `frontend/lib/admin/hospital_admins_dialog.dart`, `frontend/lib/admin/kiosk_tab.dart`, `frontend/lib/admin/logs_tab.dart`, `frontend/lib/admin/sessions_tab.dart`
- **L596–620** `def create_hospital_admin` — route `POST /api/admin/tenants/{tenant_id}/hospital-admins`; called from: `frontend/lib/admin/clients_tab.dart`, `frontend/lib/admin/hospital_admins_dialog.dart`, `frontend/lib/admin/kiosk_tab.dart`, `frontend/lib/admin/logs_tab.dart`, `frontend/lib/admin/sessions_tab.dart`  
  The hospital's first administrator, who then adds everyone else.
- **L623–640** `def reset_hospital_admin` — route `POST /api/admin/tenants/{tenant_id}/hospital-admins/{user_id}/reset-password`; called from: `frontend/lib/admin/clients_tab.dart`, `frontend/lib/admin/hospital_admins_dialog.dart`, `frontend/lib/admin/kiosk_tab.dart`, `frontend/lib/admin/logs_tab.dart`, `frontend/lib/admin/sessions_tab.dart`

## `backend/app/hospital/service.py` (204 lines)

Hospital accounts, sessions, and the audit trail.

Password and token handling reuse `app.auth` (scrypt hashes, SHA-256 token
hashes), but against the hospital tables, so hospital and company accounts
never mix.

Uses (inside the app): `deps`, `models`

Settings and constants:
- **L22** `SESSION_HOURS`

Functions and classes:
- **L25–28** `class HospitalError`
  - **L26–28** `def __init__`
- **L31–34** `def temporary_password`  
  Easy to read out and type: no 0/O or 1/l.
- **L37–44** `def _check_email`
- **L47–76** `def create_user`  
  A new account and its password: a temporary one (shown once, changed at first sign-in) unless the company chose it (`chosen`).
- **L79–109** `def sign_in`  
  The user and a new session token. Raises HospitalError otherwise.
- **L112–129** `def user_for_token`
- **L132–136** `def sign_out`
- **L139–141** `def end_sessions`
- **L144–153** `def set_password`
- **L156–167** `def audit`  
  One line in the hospital's audit trail, in the caller's transaction.
- **L173–179** `def hospital_token`
- **L182–192** `def signed_in`  
  Anyone signed in at a hospital.
- **L195–199** `def hospital_admin`  
  A hospital admin: the only role with the hospital portal.
