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

- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, etc.
- `CLICKPESA_BASE_URL`
- `CLICKPESA_CLIENT_ID`
- `CLICKPESA_CLIENT_API_KEYS` (or `CLICKPESA_API_KEY`)
