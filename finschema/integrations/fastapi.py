"""FastAPI middleware integration for finschema validation."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, cast, get_args, get_origin

from pydantic import BaseModel

from finschema.quality import ValidationEngine
from finschema.quality.report import ValidationIssue

try:
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Match
except Exception as exc:  # pragma: no cover - depends on optional dependency
    raise RuntimeError(
        "fastapi is not installed. Install extras with: pip install finschema[fastapi]"
    ) from exc

if TYPE_CHECKING:

    class _BaseHTTPMiddleware:
        def __init__(self, app: Any) -> None: ...
else:
    _BaseHTTPMiddleware = BaseHTTPMiddleware


def _known_schema_name(model: type[BaseModel]) -> str | None:
    from finschema.schemas import Portfolio, Position, Trade

    known: dict[type[BaseModel], str] = {
        Trade: "Trade",
        Position: "Position",
        Portfolio: "Portfolio",
    }
    return known.get(model)


def _resolve_model(annotation: Any) -> type[BaseModel] | None:
    if annotation is inspect.Signature.empty:
        return None

    if isinstance(annotation, str):
        from finschema.schemas import Portfolio, Position, Trade

        by_name: dict[str, type[BaseModel]] = {
            "Trade": Trade,
            "Position": Position,
            "Portfolio": Portfolio,
        }
        return by_name.get(annotation)

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is None:
        return None

    if str(origin) == "typing.Annotated" and args:
        return _resolve_model(args[0])

    if origin in (list, tuple) and args:
        return _resolve_model(args[0])

    return None


def _resolve_endpoint(request: Request) -> Callable[..., Any] | None:
    endpoint = request.scope.get("endpoint")
    if callable(endpoint):
        return cast(Callable[..., Any], endpoint)

    route = request.scope.get("route")
    endpoint = getattr(route, "endpoint", None)
    if callable(endpoint):
        return cast(Callable[..., Any], endpoint)

    router = getattr(request.app, "router", None)
    routes = getattr(router, "routes", [])
    for candidate in routes:
        matcher = getattr(candidate, "matches", None)
        if not callable(matcher):
            continue
        match, _child_scope = matcher(request.scope)
        if match == Match.FULL:
            endpoint = getattr(candidate, "endpoint", None)
            if callable(endpoint):
                return cast(Callable[..., Any], endpoint)
    return None


def _detect_schema_from_request(request: Request) -> str | None:
    endpoint = _resolve_endpoint(request)
    if endpoint is None:
        return None

    signature = inspect.signature(endpoint)
    for parameter in signature.parameters.values():
        model = _resolve_model(parameter.annotation)
        if model is None:
            continue
        name = _known_schema_name(model)
        if name is not None:
            return name
    return None


def _issue_to_detail(issue: ValidationIssue) -> dict[str, Any]:
    field = issue.field
    if field is None or field == "__root__":
        loc: list[str] = ["body"]
    else:
        loc = ["body", *str(field).split(".")]
    return {
        "type": issue.rule,
        "loc": loc,
        "msg": issue.message,
        "ctx": issue.context,
    }


class FinschemaMiddleware(_BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        *,
        strict: bool = True,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(app)
        self._strict = strict
        self._engine = engine or ValidationEngine()
        self._context = context or {}
        self._overrides = overrides or {}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method.upper() not in {"POST", "PUT", "PATCH"}:
            response = await call_next(request)
            return response

        content_type = request.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            response = await call_next(request)
            return response

        schema = _detect_schema_from_request(request)
        if schema is None:
            response = await call_next(request)
            return response

        raw_body = await request.body()
        if not raw_body:
            response = await call_next(request)
            return response

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            request_with_body = self._request_with_restored_body(request, raw_body)
            response = await call_next(request_with_body)
            return response

        report = self._engine.validate(
            payload,
            schema=schema,
            context=self._context,
            overrides=self._overrides,
        )
        request.state.finschema_report = report

        if self._strict and report.errors:
            detail = [_issue_to_detail(issue) for issue in report.errors]
            return JSONResponse(status_code=422, content={"detail": detail})

        request_with_body = self._request_with_restored_body(request, raw_body)
        request_with_body.state.finschema_report = report
        response = await call_next(request_with_body)
        return response

    @staticmethod
    def _request_with_restored_body(request: Request, raw_body: bytes) -> Request:
        sent = False

        async def _receive() -> dict[str, Any]:
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": raw_body, "more_body": False}

        return Request(request.scope, _receive)


__all__ = ["FinschemaMiddleware"]
