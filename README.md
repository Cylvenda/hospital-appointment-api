# Backend (Django API)

This folder contains the Django backend for authentication, appointments, payments, and notifications.

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
- Payments webhook: `/api/webhooks/payments/`

## Environment

Set values in `backend/.env`:

- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, etc.
- `CLICKPESA_BASE_URL`
- `CLICKPESA_CLIENT_ID`
- `CLICKPESA_CLIENT_API_KEYS` (or `CLICKPESA_API_KEY`)

