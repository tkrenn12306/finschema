import importlib.util
import logging
from typing import Annotated, Any

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("fastapi") is None
    or importlib.util.find_spec("starlette") is None
    or importlib.util.find_spec("httpx") is None,
    reason="fastapi/httpx not installed",
)


def _valid_trade_payload() -> dict[str, object]:
    return {
        "trade_id": "T-1",
        "isin": "US0378331005",
        "side": "BUY",
        "quantity": 100,
        "price": 178.52,
        "currency": "USD",
        "trade_date": "2026-03-19",
        "settlement_date": "2026-03-20",
    }


async def _post_json(
    app: object,
    path: str,
    payload: dict[str, object] | list[dict[str, object]],
) -> tuple[int, dict[str, object], dict[str, str]]:
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, json=payload)
        return response.status_code, response.json(), dict(response.headers)


async def _get_json(
    app: object,
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path, params=params)
        return response.status_code, response.json(), dict(response.headers)


@pytest.mark.anyio
async def test_fastapi_middleware_strict_true_returns_422() -> None:
    from fastapi import FastAPI

    from finschema.integrations.fastapi import FinschemaMiddleware
    from finschema.schemas import Trade

    app = FastAPI()
    app.add_middleware(FinschemaMiddleware, strict=True)

    @app.post("/trades")
    async def create_trade(trade: Trade) -> dict[str, str]:
        return {"trade_id": trade.trade_id}

    payload = _valid_trade_payload()
    payload["isin"] = "US0378331009"
    status, body, headers = await _post_json(app, "/trades", payload)

    assert status == 422
    assert "x-finschema-score" in headers
    assert headers["x-finschema-errors"] == "1"
    assert "detail" in body
    detail = body["detail"]
    assert isinstance(detail, list)
    first = detail[0]
    assert isinstance(first, dict)
    assert first["type"] == "schema_validation"


@pytest.mark.anyio
async def test_fastapi_middleware_strict_false_sets_request_state() -> None:
    from fastapi import FastAPI, Request

    from finschema.integrations.fastapi import FinschemaMiddleware
    from finschema.schemas import Trade

    app = FastAPI()
    app.add_middleware(FinschemaMiddleware, strict=False)

    @app.post("/trades")
    async def create_trade(request: Request, trade: Trade) -> dict[str, object]:
        report = getattr(request.state, "finschema_report", None)
        return {"trade_id": trade.trade_id, "has_report": report is not None}

    status, body, headers = await _post_json(app, "/trades", _valid_trade_payload())
    assert status == 200, body
    assert body["has_report"] is True
    assert "x-finschema-score" in headers
    assert headers["x-finschema-errors"] == "0"


@pytest.mark.anyio
async def test_fastapi_middleware_list_payload_support() -> None:
    from fastapi import FastAPI

    from finschema.integrations.fastapi import FinschemaMiddleware
    from finschema.schemas import Trade

    app = FastAPI()
    app.add_middleware(FinschemaMiddleware, strict=True)

    @app.post("/trades/bulk")
    async def create_trades(trades: list[Trade]) -> dict[str, int]:
        return {"count": len(trades)}

    valid = _valid_trade_payload()
    invalid = dict(valid)
    invalid["isin"] = "US0378331009"
    status, _body, _headers = await _post_json(app, "/trades/bulk", [valid, invalid])
    assert status == 422


@pytest.mark.anyio
async def test_fastapi_middleware_noop_for_unsupported_signature() -> None:
    from fastapi import FastAPI

    from finschema.integrations.fastapi import FinschemaMiddleware

    app = FastAPI()
    app.add_middleware(FinschemaMiddleware, strict=True)

    @app.post("/raw")
    async def raw_endpoint(payload: dict[str, object]) -> dict[str, object]:
        return payload

    status, body, headers = await _post_json(app, "/raw", {"foo": "bar"})
    assert status == 200
    assert body == {"foo": "bar"}
    assert "x-finschema-score" not in headers


@pytest.mark.anyio
async def test_fastapi_middleware_logs_validation_summary(caplog: pytest.LogCaptureFixture) -> None:
    from fastapi import FastAPI

    from finschema.integrations.fastapi import FinschemaMiddleware
    from finschema.schemas import Trade

    app = FastAPI()
    app.add_middleware(FinschemaMiddleware, strict=False)

    @app.post("/trades")
    async def create_trade(trade: Trade) -> dict[str, str]:
        return {"trade_id": trade.trade_id}

    with caplog.at_level(logging.INFO, logger="finschema.fastapi"):
        status, _body, _headers = await _post_json(app, "/trades", _valid_trade_payload())

    assert status == 200
    assert "validated_request method=POST path=/trades" in caplog.text


@pytest.mark.anyio
async def test_fastapi_depends_validate_helper_strict_modes() -> None:
    from fastapi import Depends, FastAPI, Request

    from finschema.integrations.fastapi import depends_validate

    app = FastAPI()
    strict_dependency = depends_validate("Trade", strict=True)
    soft_dependency = depends_validate("Trade", strict=False)

    @app.post("/strict")
    async def strict_route(
        payload: Annotated[dict[str, object], Depends(strict_dependency)],
    ) -> dict[str, object]:
        return payload

    @app.post("/soft")
    async def soft_route(
        request: Request,
        payload: Annotated[dict[str, object], Depends(soft_dependency)],
    ) -> dict[str, object]:
        return {"payload": payload, "has_report": hasattr(request.state, "finschema_report")}

    bad_payload = _valid_trade_payload()
    bad_payload["isin"] = "US0378331009"

    strict_status, strict_body, _strict_headers = await _post_json(app, "/strict", bad_payload)
    assert strict_status == 422
    assert "detail" in strict_body

    soft_status, soft_body, _soft_headers = await _post_json(app, "/soft", bad_payload)
    assert soft_status == 200
    assert soft_body["has_report"] is True


@pytest.mark.anyio
async def test_fastapi_types_validate_path_query_and_openapi_schema() -> None:
    from fastapi import FastAPI

    from finschema.types import ISIN, CurrencyCode

    app = FastAPI()

    @app.get("/ids/{isin}")
    async def by_isin(isin: ISIN, currency: CurrencyCode) -> dict[str, str]:
        return {"isin": str(isin), "currency": str(currency)}

    ok_status, ok_body, _ok_headers = await _get_json(
        app,
        "/ids/US0378331005",
        params={"currency": "USD"},
    )
    assert ok_status == 200
    assert ok_body["currency"] == "USD"

    bad_status, bad_body, _bad_headers = await _get_json(
        app,
        "/ids/US0378331009",
        params={"currency": "USD"},
    )
    assert bad_status == 422
    assert "detail" in bad_body

    openapi_status, openapi, _openapi_headers = await _get_json(app, "/openapi.json")
    assert openapi_status == 200
    serialized = str(openapi)
    assert "US0378331005" in serialized
    assert "^[A-Z]{2}[A-Z0-9]{9}[0-9]$" in serialized
