# payments/services.py
import requests
from rest_framework.exceptions import ValidationError
from .payments import BASE_URL, clickpesa_headers, PaymentGatewayError
from .models import Payment
from django.conf import settings
import uuid


def normalize_phone_number(raw_phone):
    """
    Normalize phone to ClickPesa format: country code, digits only, no plus sign.
    Example: 0780598902 -> 255780598902
    """
    if raw_phone is None:
        raise ValidationError({"phoneNumber": "Phone number is required."})

    phone = str(raw_phone).strip()

    # Handle accidental numeric casting, e.g. 255780598902.0
    if phone.endswith(".0"):
        phone = phone[:-2]

    # Keep digits only
    digits = "".join(ch for ch in phone if ch.isdigit())

    # Convert local format to international if needed
    if digits.startswith("0") and len(digits) == 10:
        digits = f"255{digits[1:]}"

    if not digits.startswith("255"):
        raise ValidationError(
            {
                "phoneNumber": "Valid phoneNumber is required, must start with country code and without the plus sign."
            }
        )

    if len(digits) != 12:
        raise ValidationError(
            {"phoneNumber": "Phone number must be 12 digits, e.g. 2557XXXXXXXX."}
        )

    return digits


def initiate_payment(payment: Payment, user, appointment, preffered_phone_number):
    """
    Initiates a ClickPesa payment for the given payment object.
    """
    phone = preffered_phone_number or user.phone

    if not phone:
        raise ValueError("No phone number provided")

    phone_number = normalize_phone_number(phone)
    url = f"{BASE_URL}/payments/initiate-ussd-push-request"
    phone_number = normalize_phone_number(phone)
    order_reference = f"PAYID{appointment.id}UUID{uuid.uuid4().hex[:6].upper()}"

    payload = {
        "phoneNumber": phone_number,
        "amount": str(payment.amount),
        "currency": "TZS",
        "orderReference": order_reference,
        "description": f"Payment for appointment {payment.appointment.uuid}",
    }
    try:
        headers = clickpesa_headers()
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=20,
        )
        data = response.json()
        print(
            f"[ClickPesa][Initiate] payload={payload} status={response.status_code} response={data}",
            flush=True,
        )
    except requests.RequestException as exc:
        raise PaymentGatewayError(f"Unable to connect to ClickPesa: {exc}") from exc
    except ValueError as exc:
        print(
            f"[ClickPesa][Initiate] payload={payload} status={response.status_code} raw={response.text}",
            flush=True,
        )
        raise PaymentGatewayError(
            "ClickPesa payment initiation response was not valid JSON."
        ) from exc

    if response.status_code >= 400:
        raise ValidationError(
            {
                "message": "ClickPesa rejected the payment request.",
                "status_code": response.status_code,
                "clickpesa_response": data,
                "request_payload": payload,
            }
        )

    # Store the exact reference we sent so webhook can match reliably.
    # If gateway echoes back orderReference, prefer that value.
    payment.transaction_reference = data.get("orderReference") or order_reference
    payment.save()

    return data
