"""
Stable JSON error shape for every API response.

The desktop client should parse one envelope regardless of whether the failure
is validation, not-found, or an unexpected server error.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context) -> Response:
    """
    Wrap DRF's default handler in {error: {code, message, details}}.

    Never returns an empty body for handled exceptions so the UI can always
    show a message instead of a silent failure.
    """
    response = exception_handler(exc, context)
    if response is None:
        return Response(
            {
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "details": None,
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    details = response.data
    message = "Request failed."
    if isinstance(details, dict):
        if "detail" in details:
            message = str(details["detail"])
        elif details:
            first_key = next(iter(details))
            first_value = details[first_key]
            message = f"{first_key}: {first_value}"
    elif isinstance(details, list) and details:
        message = str(details[0])

    response.data = {
        "error": {
            "code": _status_to_code(response.status_code),
            "message": message,
            "details": details,
        }
    }
    return response


def _status_to_code(status_code: int) -> str:
    """Map HTTP status to a stable machine-readable code."""
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "unprocessable_entity",
        429: "throttled",
    }
    return mapping.get(status_code, "error")
