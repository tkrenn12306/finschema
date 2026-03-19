"""Configuration loading and validation for quality engine."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from finschema.errors import ValidationError

DEFAULT_CONFIG_FILENAMES = ("finschema.yaml", "finschema.toml", "pyproject.toml")


def _default_price_bounds() -> dict[str, Decimal]:
    return {
        "EQUITY": Decimal("999999"),
        "FIXED_INCOME": Decimal("300"),
        "FX": Decimal("10"),
        "COMMODITY": Decimal("1000000"),
        "DERIVATIVE": Decimal("1000000"),
    }


def _default_settlement_cycles() -> dict[str, int]:
    return {
        "US:EQUITY": 1,
        "EU:EQUITY": 2,
        "US:TREASURY": 1,
    }


class EngineConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weight_tolerance: Decimal = Decimal("0.001")
    max_single_position: Decimal = Decimal("0.25")
    fx_deviation_max: Decimal = Decimal("0.05")
    fx_inverse_tolerance: Decimal = Decimal("0.02")
    price_min: Decimal = Decimal("0")
    price_daily_change_max: Decimal = Decimal("0.25")
    price_max_by_asset_class: dict[str, Decimal] = Field(default_factory=_default_price_bounds)
    min_score: float = 0.95
    strict_mode: bool = False
    fail_on_severity: str = "ERROR"
    default_settlement_days: int = 1
    settlement_cycles: dict[str, int] = Field(default_factory=_default_settlement_cycles)
    stale_price_days: int = 3
    enabled_rulesets: list[str] = Field(default_factory=list)
    disabled_rulesets: list[str] = Field(default_factory=list)


def _merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def validate_engine_config(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = EngineConfigModel.model_validate(raw)
    except PydanticValidationError as exc:
        raise ValidationError(
            "Invalid finschema quality config",
            field="config",
            expected="EngineConfigModel",
            actual=raw,
            details={"errors": exc.errors()},
        ) from exc
    return validated.model_dump(mode="python")


def _load_toml(path: Path) -> dict[str, Any]:
    parsed_any: Any
    if sys.version_info >= (3, 11):
        import tomllib

        with path.open("rb") as handle:
            parsed_any = tomllib.load(handle)
    else:
        try:
            import tomli
        except Exception as exc:  # pragma: no cover - depends on python/dependency setup
            raise RuntimeError(
                "TOML config on Python <3.11 requires tomli. Install with: pip install tomli"
            ) from exc
        with path.open("rb") as handle:
            parsed_any = tomli.load(handle)

    if not isinstance(parsed_any, dict):
        return {}
    return parsed_any


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-untyped]
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "YAML config requires PyYAML. Install extras with: pip install finschema[yaml]"
        ) from exc

    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValidationError(
            "Invalid YAML config root",
            field="config",
            expected="mapping object",
            actual=type(parsed).__name__,
        )
    return parsed


def _load_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return _load_yaml(path)
    if suffix == ".toml":
        parsed = _load_toml(path)
        if path.name == "pyproject.toml":
            tool = parsed.get("tool", {})
            if isinstance(tool, dict):
                finschema = tool.get("finschema", {})
                if isinstance(finschema, dict):
                    return finschema
            return {}
        return parsed
    raise ValidationError(
        "Unsupported config format",
        field="config",
        expected=".yaml/.yml/.toml",
        actual=str(path),
    )


def discover_file_config(cwd: Path | None = None) -> dict[str, Any]:
    base = cwd or Path.cwd()
    for filename in DEFAULT_CONFIG_FILENAMES:
        candidate = base / filename
        if candidate.exists() and candidate.is_file():
            return _load_file(candidate)
    return {}


def load_engine_config(config: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    discovered = discover_file_config()

    if config is None:
        merged = discovered
        return validate_engine_config(merged)

    if isinstance(config, (str, Path)):
        loaded = _load_file(Path(config))
        return validate_engine_config(loaded)

    if isinstance(config, dict):
        merged = _merge_config(discovered, config)
        return validate_engine_config(merged)

    raise TypeError("config must be dict, str, Path, or None")
