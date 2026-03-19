"""Optional ecosystem integrations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .fastapi import FinschemaMiddleware

__all__ = [
    "FinschemaMiddleware",
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


def _missing_fastapi_middleware() -> type[Any]:
    class FinschemaMiddleware:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError(
                "fastapi is not installed. Install extras with: pip install finschema[fastapi]"
            )

    return FinschemaMiddleware


def __getattr__(name: str) -> Any:
    if name == "FinschemaMiddleware":
        try:
            from .fastapi import FinschemaMiddleware
        except RuntimeError:
            return _missing_fastapi_middleware()
        return FinschemaMiddleware
    if name == "register_pandas_accessors":
        return register_pandas_accessors
    if name == "register_polars_namespace":
        return register_polars_namespace
    raise AttributeError(f"module 'finschema.integrations' has no attribute {name!r}")
