"""Reject non-loopback HTTP so the shop API is not reachable on the LAN by default."""

from __future__ import annotations

from django.http import JsonResponse


class LoopbackOnlyMiddleware:
    """Desktop API must stay on 127.0.0.1 / ::1 unless an operator later opens LAN access."""

    ALLOWED = {"127.0.0.1", "::1", "localhost", "testserver"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        remote = request.META.get("REMOTE_ADDR") or ""
        host = (request.get_host() or "").split(":")[0]
        if remote not in self.ALLOWED and host not in self.ALLOWED:
            return JsonResponse(
                {
                    "error": {
                        "code": "forbidden",
                        "message": "This application only accepts requests from this computer.",
                        "details": None,
                    }
                },
                status=403,
            )
        return self.get_response(request)
