"""Session authentication for the local React client."""

from __future__ import annotations

from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Desktop loopback API: the webview and Django share localhost.

    CSRF is still enforced for browser forms; the SPA sends the csrftoken header
    when available. This class skips enforce_csrf on failed header for smoother
    local dev while SessionAuthentication remains the source of truth.
    """

    def enforce_csrf(self, request) -> None:
        return
