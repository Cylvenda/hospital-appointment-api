# Backend (Django API)

This folder contains the Django backend for authentication, appointments, payments, notifications, and the clinical modules that support consultation, prescriptions, medical records, and laboratory workflows.

## Stack

- Django
- Django REST Framework
- Djoser + JWT
- drf-spectacular (API docs)
- SQLite (local development)

## Run Locally

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Backend URL: `http://127.0.0.1:8000`

## Key Endpoints

- Swagger UI: `/`
- OpenAPI schema: `/api/schema/`
- Auth: `/api/auth/...`
- App auth routes: `/api/me/auth/...`
- Appointments: `/api/appointments/`
- Illness categories: `/api/illness_category/`
- Consultations, medical records, prescriptions, and laboratory modules are available as Django apps in `api/`
- Consultations: `/api/consultations/`
- Medical records: `/api/medical-records/`
- Diagnoses: `/api/diagnoses/`
- Prescriptions: `/api/prescriptions/`
- Prescription items: `/api/prescription-items/`
- Lab tests: `/api/lab-tests/`
- Lab requests: `/api/lab-requests/`
- Lab request items: `/api/lab-request-items/`
- Lab results: `/api/lab-results/`
- Invoices: `/api/invoices/`
- Invoice items: `/api/invoice-items/`
- Medicines: `/api/medicines/`
- Dispensings: `/api/dispensings/`
- Dispensing items: `/api/dispensing-items/`
- Payments webhook: `/api/webhooks/payments/`

## Environment

Set values in `backend/.env`:

- Copy `.env.example` to `.env` for a safe starting template.
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, etc.
- `CLICKPESA_BASE_URL`
- `CLICKPESA_CLIENT_ID`
- `CLICKPESA_CLIENT_API_KEYS` (or `CLICKPESA_API_KEY`)
- `CLICKPESA_CHECKSUM_KEY`

## Supabase PostgreSQL

For Render, use the Supabase **session pooler** because it provides an IPv4
connection. Add this secret environment variable in Render:

```env
DATABASE_URL=postgresql://postgres.lugghkshvznncrwgoblx:YOUR_URL_ENCODED_PASSWORD@aws-0-eu-west-3.pooler.supabase.com:5432/postgres?sslmode=require
```

Replace `YOUR_URL_ENCODED_PASSWORD` with the database password from
**Supabase → Project Settings → Database**. If the password contains special
characters, URL-encode it first. Do not commit the completed URL.

Also set:

```env
USE_SQLITE=False
DB_CONN_MAX_AGE=0
```

`DB_CONN_MAX_AGE=0` is important when using Supabase's session pooler. It
closes each Django database connection at the end of the request instead of
holding scarce session-pooler clients open.

The application prefers `DATABASE_URL`. Separate `DB_HOST`, `DB_PORT`,
`DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `DB_SSLMODE=require` variables are
supported as an alternative.

To verify the connection and initialize the database:

```bash
python manage.py migrate --noinput
python manage.py ensure_superuser
```
