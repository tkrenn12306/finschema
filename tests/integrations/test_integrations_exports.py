from __future__ import annotations

import pytest

import finschema.integrations as integrations


def test_integrations_lazy_exports() -> None:
    assert callable(integrations.register_pandas_accessors)
    assert callable(integrations.register_polars_namespace)
    assert integrations.FinschemaMiddleware.__name__ == "FinschemaMiddleware"


def test_integrations_unknown_attribute() -> None:
    with pytest.raises(AttributeError):
        _ = integrations.does_not_exist
