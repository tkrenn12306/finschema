# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-03-19

### Added

- Integrations rollup across Pandas/Polars/FastAPI with API parity for `validate`, `is_valid`,
  `clean`, `coerce`, and per-row validation helpers.
- Polars `LazyFrame` validation namespace and expression validators (`expr.is_valid_isin`,
  `expr.is_valid_currency`, `expr.is_valid_bic`).
- FastAPI response quality headers (`X-Finschema-*`) and dependency helper
  `depends_validate(...)`.
- CLI `validate` support for JSON input, `--config`, and `--watch`; new `diff` command.
- Interactive standalone HTML report UX (filter/sort, score gauge, invalid-row CSV export,
  trend placeholder) and `QualityReport._repr_html_()` for notebooks.
- MkDocs cookbook with end-to-end recipes and a `py.typed` marker for IDE/type-checker UX.

### Changed

- Version bumped to `0.6.0`.
- Public integrations export surface extended with lazy `read_csv` and `polars_expr` helpers.
- Type JSON schema metadata enriched for stronger FastAPI/OpenAPI docs.

## [0.4.0] - 2026-03-19

### Added

- Full spec rollup: MUST + SHOULD + COULD types and enums.
- Structured error payload normalization with code/rule metadata.
- `CountryCode`, `Rate`, `BasisPoints`, `Tenor`, `MaturityDate`.
- Additional identifiers: `FIGI`, `VALOR`, `WKN`, `RIC`, `Ticker`.
- CLI `check --batch` and ANSI color output.
- Project governance and docs-site scaffolding (`LICENSE`, `CONTRIBUTING`, `CODE_OF_CONDUCT`, MkDocs).

### Changed

- Version bumped to `0.4.0`.
- Runtime dependencies reduced to `pydantic` only.
- CLI migrated from `typer` to stdlib `argparse`.

### Fixed

- IBAN handling now strict ISO-country support (US IBAN rejected).
