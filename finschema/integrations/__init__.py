"""Optional ecosystem integrations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .fastapi import FinschemaMiddleware

__all__ = [
    "FinschemaMiddleware",
    "depends_validate",
    "polars_expr",
    "read_csv",
    "register_pandas_accessors",
    "register_polars_namespace",
]


def register_pandas_accessors() -> None:
    """Register pandas accessors on demand."""
    from .pandas import register_pandas_accessors as _register

    _register()


def register_polars_namespace() -> None:
    """Register polars namespace on demand."""
    from .polars import register_polars_namespace as _register

    _register()


def read_csv(*args: Any, **kwargs: Any) -> Any:
    """Read a CSV via pandas and immediately validate with finschema."""
    from .pandas import read_csv as _read_csv

    return _read_csv(*args, **kwargs)


class _PolarsExprProxy:
    """Lazy proxy for expression validators in `finschema.integrations.polars.expr`."""

    def __call__(self) -> Any:
        from .polars import expr

        return expr

    def __getattr__(self, name: str) -> Any:
        from .polars import expr

        return getattr(expr, name)


polars_expr = _PolarsExprProxy()


def _missing_fastapi_error() -> RuntimeError:
    return RuntimeError(
        "fastapi is not installed. Install extras with: pip install finschema[fastapi]"
    )


def _missing_fastapi_middleware() -> type[Any]:
    class FinschemaMiddleware:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise _missing_fastapi_error()

    return FinschemaMiddleware


def depends_validate(*_args: Any, **_kwargs: Any) -> Any:
    """FastAPI dependency helper for full-schema validation."""
    try:
        from .fastapi import depends_validate as _depends_validate
    except RuntimeError as exc:
        raise _missing_fastapi_error() from exc

    return _depends_validate(*_args, **_kwargs)


def __getattr__(name: str) -> Any:
    if name == "FinschemaMiddleware":
        try:
            from .fastapi import FinschemaMiddleware
        except RuntimeError:
            return _missing_fastapi_middleware()
        return FinschemaMiddleware
    if name == "depends_validate":
        return depends_validate
    if name == "register_pandas_accessors":
        return register_pandas_accessors
    if name == "register_polars_namespace":
        return register_polars_namespace
    if name == "read_csv":
        return read_csv
    if name == "polars_expr":
        return polars_expr
    raise AttributeError(f"module 'finschema.integrations' has no attribute {name!r}")
