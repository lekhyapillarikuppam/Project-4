"""Error responses (API-FR-11): {"error": code, "message": text, "fields"?: {...}} — never a stack trace."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("tripwise.api")

CODES = {400: "bad_request", 401: "unauthorized", 404: "not_found", 409: "conflict", 422: "invalid", 429: "busy",
         500: "internal", 503: "unavailable"}


class ApiError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None, fields: dict | None = None,
                 extra: dict | None = None):
        self.status, self.message, self.code, self.fields, self.extra = status, message, code or CODES.get(status, "error"), fields, extra


def not_found(what: str = "Not found") -> ApiError:
    return ApiError(404, what)


def body(code: str, message: str, fields: dict | None = None, extra: dict | None = None) -> dict:
    out = {"error": code, "message": message}
    if fields:
        out["fields"] = fields
    if extra:
        out.update(extra)
    return out


def _loc(loc: tuple) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or "body"


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return JSONResponse(body(exc.code, exc.message, exc.fields, exc.extra), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation(_: Request, exc: RequestValidationError):
        fields = {}
        for e in exc.errors():
            fields.setdefault(_loc(tuple(e.get("loc", ()))), e.get("msg", "invalid"))
        return JSONResponse(body("invalid", "Some fields are not valid.", fields), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        msg = exc.detail if isinstance(exc.detail, str) else CODES.get(exc.status_code, "error")
        return JSONResponse(body(CODES.get(exc.status_code, "error"), msg), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.error("unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
        return JSONResponse(body("internal", "Something went wrong on our side."), status_code=500)
