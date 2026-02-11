# Testing Philosophy — Three-Tier TDD

**Core Principle:** Tests are written BEFORE implementation. Every feature, every module, every function.

This is not negotiable. This is how we build reliable software that works in production, not just in test harnesses.

---

## Three-Tier Testing Strategy

Every module must have all three tiers of tests written **before any implementation code**:

### Tier 1: Unit Tests (pytest)
**Purpose:** Fast feedback, 100% coverage, isolated component validation

**Location:** `tests/<module>/test_*.py`

**Characteristics:**
- Test individual functions, classes, methods in isolation
- Mock external dependencies (APIs, file system, databases)
- Fast (entire suite runs in seconds)
- 100% branch coverage required — enforced by CI
- Run on every commit

**Example:** `tests/providers/test_pricing.py`
- Tests `calculate_cost()` function with various inputs
- No real API calls, no real file I/O
- Pure logic validation

**Coverage Requirement:** `--cov-fail-under=100`

---

### Tier 2: Integration Tests (pytest)
**Purpose:** Validate components work together correctly

**Location:** `tests/integration/test_*_integration.py`

**Characteristics:**
- Test multiple components interacting
- Use test doubles where needed (TestModel, mock PM APIs)
- Test realistic workflows end-to-end
- Validate data flows between modules
- Still fast enough for frequent runs

**Example:** `tests/integration/test_provider_integration.py`
- Creates provider, invokes it, validates full result structure
- Tests structured Pydantic output (InterviewQuestion, ReviewFinding)
- Tests cost calculation with realistic token counts
- Uses TestModel to avoid API costs, but exercises full code path

**Why Integration Tests Matter:**
- Unit tests prove components work alone
- Integration tests prove they work together
- Catches interface mismatches, type errors, data transformation bugs

---

### Tier 3: Smoke Tests (standalone scripts)
**Purpose:** Validate the module works in the wild, not just in test harnesses

**Location:** `tests/smoke/smoke_test_*.py`

**Characteristics:**
- Standalone Python scripts (not pytest)
- Import modules like a real user would
- No test framework magic — just plain Python
- Exit 0 on success, 1 on failure
- Run manually or in CI
- Test real usage patterns

**Example:** `tests/smoke/smoke_test_provider.py`
- Imports `imp.providers` like a developer would
- Creates providers, invokes them, validates results
- Uses real Pydantic AI (with TestModel for cost)
- Tests all public APIs
- Validates configuration, cost calculation, model roster

**Run:** `uv run python tests/smoke/smoke_test_provider.py`

**Why Smoke Tests Matter:**
- pytest can pass with mocked imports that don't exist in production
- pytest can pass with circular import issues hidden by test structure
- Smoke tests prove "this actually works when you import it"
- Catches packaging issues, missing dependencies, broken public APIs

---

## TDD Workflow: Tests First, Always

### Before Writing Any Code

1. **Write unit tests** for the functions/classes you plan to implement
   - Define the API in the test (function signatures, return types)
   - Test edge cases, error conditions, happy paths
   - All tests should fail (because the code doesn't exist yet)

2. **Write integration tests** for how components will interact
   - Define the workflow in the test
   - Mock external dependencies, but test real interactions
   - All tests should fail

3. **Write smoke test** for real-world usage
   - Script that imports and uses the module
   - Tests public API from user perspective
   - Should fail (imports don't exist yet)

### Implement

4. **Write minimal code to make tests pass**
   - Start with unit tests (fastest feedback)
   - Move to integration tests
   - Verify smoke tests pass

5. **Refactor if needed**
   - Tests stay green
   - Code gets cleaner

### Verify

6. **Run all three tiers**
   ```bash
   # Tier 1: Unit tests
   uv run pytest tests/<module>/ -v

   # Tier 2: Integration tests
   uv run pytest tests/integration/ -v

   # Tier 3: Smoke tests
   uv run python tests/smoke/smoke_test_<module>.py
   ```

7. **Run full verification suite**
   ```bash
   uv run pytest tests/ -v              # All pytest tests
   uv run mypy src/imp/<module>/        # Type checking
   uv run ruff check src/imp/<module>/  # Linting
   uv run lint-imports                  # Architecture contracts
   ```

---

## What Gets Tested in Each Tier

### Example: Provider Abstraction Module

#### Tier 1: Unit Tests
- `TokenUsage`: creation, defaults, immutability, validation
- `AgentResult`: string output, structured output, generic typing
- `AgentProvider`: abstract class, concrete subclass
- `ProviderConfig`: defaults, overrides, validation
- `ModelRoster`: per-role configs, overrides
- `calculate_cost()`: known models, unknown models, cache costs
- `PydanticAIProvider`: invoke, usage tracking, cost calculation, duration

**Coverage:** Every function, every branch, every edge case

#### Tier 2: Integration Tests
- Full provider flow: create → invoke → structured result
- Realistic Pydantic models (InterviewQuestion, ReviewFinding)
- Multi-turn conversations
- Cost calculation with realistic token counts
- Cache cost calculation with real multipliers
- Model roster configuration and overrides
- Error handling with structured output

**Coverage:** Common workflows, realistic scenarios, component interactions

#### Tier 3: Smoke Tests
- Import all public APIs
- Create provider with TestModel
- Invoke with string output
- Invoke with structured Pydantic output
- Cost calculation for all Anthropic models
- Cache cost calculation
- Model roster configuration
- Provider config defaults and overrides

**Coverage:** Real usage patterns, public API validation, "does it work in the wild"

---

## Rules for Coding Agents

When building any new module, feature, or function:

1. **Tests first, code second** — no exceptions
2. **All three tiers** — unit, integration, smoke
3. **Tests must fail first** — proves they're testing something
4. **100% coverage** — enforced by CI
5. **Smoke tests must pass** — proves it works in production
6. **All tiers must pass** — before marking task complete

**Agents cannot mark a task complete** until:
- ✅ Unit tests written and passing
- ✅ Integration tests written and passing
- ✅ Smoke test written and passing
- ✅ 100% branch coverage achieved
- ✅ mypy strict passing
- ✅ ruff linting passing
- ✅ import-linter passing

---

## Why This Matters

### Scenario: pytest passes, smoke test fails

**Unit tests pass:** `calculate_cost()` function works correctly
**Integration tests pass:** Provider calls `calculate_cost()` and returns correct result
**Smoke test fails:** Import error — `calculate_cost` not exported from `__init__.py`

→ **pytest mocked the import, smoke test caught the real issue**

### Scenario: Everything passes locally, fails in CI

**Locally:** All tests pass
**CI:** Smoke test fails — missing dependency in `pyproject.toml`

→ **Smoke test running in clean environment catches packaging issues**

### Scenario: Works for developer, breaks for agents

**Developer:** Manually runs `imp interview`, works fine
**Agent:** Parses `--format json` output, crashes — field name changed

→ **Integration test for JSON output format catches breaking changes**

---

## Verification Checklist

Before considering any module complete:

```bash
# Tier 1: Unit tests with coverage
uv run pytest tests/<module>/ -v
# → Must show 100% coverage

# Tier 2: Integration tests
uv run pytest tests/integration/ -v
# → All scenarios pass

# Tier 3: Smoke test
uv run python tests/smoke/smoke_test_<module>.py
# → Exit code 0

# Type checking
uv run mypy src/imp/<module>/
# → 0 errors

# Linting
uv run ruff check src/imp/<module>/
# → All checks passed

# Architecture contracts
uv run lint-imports
# → All contracts kept

# Full test suite
uv run pytest tests/ -v
# → 100% coverage, all tests pass
```

**All must pass. No exceptions.**

---

## This Is Who We Are

Three-tier TDD is not a suggestion. It's a core philosophy of Josh's engineering brand.

Tests first. Always.

Unit → Integration → Smoke → Implementation → Verify.

This is how we build software that works in production, not just in demos.
