# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
