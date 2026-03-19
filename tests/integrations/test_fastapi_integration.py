import importlib.util

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
) -> tuple[int, dict[str, object]]:
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, json=payload)
        return response.status_code, response.json()


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
    status, body = await _post_json(app, "/trades", payload)

    assert status == 422
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

    status, body = await _post_json(app, "/trades", _valid_trade_payload())
    assert status == 200, body
    assert body["has_report"] is True


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
    status, _body = await _post_json(app, "/trades/bulk", [valid, invalid])
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

    status, body = await _post_json(app, "/raw", {"foo": "bar"})
    assert status == 200
    assert body == {"foo": "bar"}
