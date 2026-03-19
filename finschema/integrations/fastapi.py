"""FastAPI middleware integration for finschema validation."""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, cast, get_args, get_origin

from pydantic import BaseModel

from finschema.quality import ValidationEngine
from finschema.quality.report import QualityReport, ValidationIssue

try:
    from fastapi import Body, HTTPException, Request
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

_LOGGER = logging.getLogger("finschema.fastapi")
_BODY_REQUIRED = Body(...)


def _known_schema_name(model: type[BaseModel]) -> str | None:
    from finschema import schemas as schemas_module

    return model.__name__ if hasattr(schemas_module, model.__name__) else None


def _resolve_model(annotation: Any) -> type[BaseModel] | None:
    if annotation is inspect.Signature.empty:
        return None

    if isinstance(annotation, str):
        from finschema import schemas as schemas_module

        candidate = getattr(schemas_module, annotation, None)
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return candidate
        return None

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


def _apply_report_headers(response: Response, report: QualityReport) -> Response:
    response.headers["X-Finschema-Score"] = f"{report.score:.4f}"
    response.headers["X-Finschema-Errors"] = str(len(report.errors))
    response.headers["X-Finschema-Warnings"] = str(len(report.warnings))
    return response


def _log_report(request: Request, report: QualityReport) -> None:
    _LOGGER.info(
        "validated_request method=%s path=%s score=%.4f errors=%d warnings=%d info=%d passed=%s",
        request.method,
        request.url.path,
        report.score,
        len(report.errors),
        len(report.warnings),
        len(report.info),
        report.passed,
    )


class FinschemaMiddleware(_BaseHTTPMiddleware):
    """Middleware that auto-validates request JSON payloads for known finschema schemas."""

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
            return await call_next(request)

        content_type = request.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            return await call_next(request)

        schema = _detect_schema_from_request(request)
        if schema is None:
            return await call_next(request)

        raw_body = await request.body()
        if not raw_body:
            return await call_next(request)

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            request_with_body = self._request_with_restored_body(request, raw_body)
            return await call_next(request_with_body)

        report = self._engine.validate(
            payload,
            schema=schema,
            context=self._context,
            overrides=self._overrides,
        )
        request.state.finschema_report = report
        _log_report(request, report)

        if self._strict and report.errors:
            detail = [_issue_to_detail(issue) for issue in report.errors]
            error_response = JSONResponse(status_code=422, content={"detail": detail})
            return _apply_report_headers(error_response, report)

        request_with_body = self._request_with_restored_body(request, raw_body)
        request_with_body.state.finschema_report = report
        response = await call_next(request_with_body)
        return _apply_report_headers(response, report)

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


def depends_validate(
    schema: type[BaseModel] | str,
    *,
    engine: ValidationEngine | None = None,
    context: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    strict: bool = True,
) -> Callable[..., Any]:
    """Create a FastAPI dependency that validates request payloads via ValidationEngine."""

    runtime_engine = engine or ValidationEngine()
    runtime_context = context or {}
    runtime_overrides = overrides or {}

    async def _dependency(request: Request, payload: Any = _BODY_REQUIRED) -> Any:
        report = runtime_engine.validate(
            payload,
            schema=schema,
            context=runtime_context,
            overrides=runtime_overrides,
        )
        request.state.finschema_report = report

        if strict and report.errors:
            raise HTTPException(
                status_code=422,
                detail=[_issue_to_detail(issue) for issue in report.errors],
            )

        return payload

    return _dependency


__all__ = ["FinschemaMiddleware", "depends_validate"]
