# payments/clickpesa_client.py
import requests
import os
from rest_framework.exceptions import APIException

BASE_URL = os.getenv("CLICKPESA_BASE_URL")
CLIENT_ID = os.getenv("CLICKPESA_CLIENT_ID")
API_KEY = os.getenv("CLICKPESA_CLIENT_API_KEYS")


class PaymentGatewayError(APIException):
    status_code = 502
    default_detail = "Payment gateway is unavailable. Please try again."
    default_code = "payment_gateway_error"


def get_token():
    """
    Exchange API Key + Client ID for a short-lived JWT token.
    """
    url = f"{BASE_URL}/generate-token"
    headers = {
        "client-id": CLIENT_ID,
        "api-key": API_KEY,
    }
    try:
        response = requests.post(url, headers=headers, timeout=20)
        data = response.json()
        print(
            f"[ClickPesa][Token] status={response.status_code} response={data}",
            flush=True,
        )
    except requests.RequestException as exc:
        raise PaymentGatewayError(f"Unable to connect to ClickPesa: {exc}") from exc
    except ValueError as exc:
        print(
            f"[ClickPesa][Token] status={response.status_code} raw={response.text}",
            flush=True,
        )
        raise PaymentGatewayError("ClickPesa token response was not valid JSON.") from exc

    if response.status_code >= 400:
        raise PaymentGatewayError(
            {
                "message": "ClickPesa token request failed.",
                "status_code": response.status_code,
                "response": data,
            }
        )

    token = data.get("token")
    if not token:
        raise PaymentGatewayError(
            {
                "message": "ClickPesa token response did not include token/access_token.",
                "response": data,
            }
        )
    return token


def clickpesa_headers():
    token = get_token()
    return {
        "Authorization": f"{token}",
        "Content-Type": "application/json",
    }
