# Contributing

Thanks for contributing to `finschema`.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Quality Gates

```bash
ruff check .
ruff format --check .
mypy
pytest
coverage report --include="finschema/types/*" --fail-under=95
```

## Pull Requests

- Keep PRs focused and small.
- Add tests for every behavior change.
- Keep public APIs backward compatible unless explicitly marked breaking.
- Update `CHANGELOG.md` under `Unreleased`.
