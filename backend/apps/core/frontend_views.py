"""
Serve the built React app from Django.

In the installed desktop app the window loads http://127.0.0.1:<port>/, so the
UI, /api, and /media share one origin (no proxy, no CORS, cookies just work).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.views import View

# Windows can map .js to text/plain via the registry, which makes browsers
# refuse to run module scripts. Pin the types the Vite build emits.
for _mime, _ext in (
    ("text/javascript", ".js"),
    ("text/javascript", ".mjs"),
    ("text/css", ".css"),
    ("image/svg+xml", ".svg"),
    ("image/webp", ".webp"),
    ("application/json", ".json"),
    ("font/woff2", ".woff2"),
):
    mimetypes.add_type(_mime, _ext)


class FrontendAppView(View):
    """Return a built asset, or index.html for client-side routes like /sales."""

    http_method_names = ["get", "head"]
    NOT_BUILT_MESSAGE = (
        "The shop UI is not built yet. Run `npm run build` in frontend/ "
        "(during development open http://127.0.0.1:5173 instead)."
    )

    def get(self, request: HttpRequest, path: str = "") -> HttpResponse:
        root = Path(settings.FRONTEND_DIST).resolve()
        index = root / "index.html"
        if not index.is_file():
            return HttpResponse(self.NOT_BUILT_MESSAGE, status=503, content_type="text/plain; charset=utf-8")
        target = self._resolve(root, path)
        if target is None:
            # Missing file with an extension (e.g. a stale /assets/x.js) is a real 404,
            # otherwise it is a React route and gets the app shell.
            if Path(path).suffix:
                raise Http404("Asset not found.")
            target = index
        response = FileResponse(target.open("rb"))
        if target == index:
            response["Cache-Control"] = "no-cache"
        elif target.parent.name == "assets":
            # Vite asset names contain a content hash, so they never change.
            response["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    def _resolve(self, root: Path, path: str) -> Path | None:
        """Map a URL path to a file inside the build folder, refusing path traversal."""
        if not path:
            return None
        candidate = (root / path).resolve()
        if root not in candidate.parents or not candidate.is_file():
            return None
        return candidate
