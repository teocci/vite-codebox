# Testing Requirements

## Framework

Use `pytest` as the testing framework.

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── test_models/
├── test_services/
└── test_utils/
```

## Naming

- Test files: `test_<module>.py`
- Test functions: `test_<function>_<scenario>`
- Test classes: `Test<ClassName>`

## Key Practices

- Use `@pytest.fixture` for shared setup (in `conftest.py`)
- Use `@pytest.mark.parametrize` for multiple test cases
- Mock external dependencies (database, API, filesystem) — never call real services in unit tests
- Aim for ≥80% coverage on critical paths; don't chase 100%
- Each test must be independent — no shared mutable state, pass in any order
- Run with: `pytest --cov=mypackage --cov-report=term-missing`

## What to Test

- Happy path (expected inputs)
- Edge cases (empty, None, boundaries)
- Error conditions (invalid inputs, failures)
- Integration points (with mocked dependencies)
