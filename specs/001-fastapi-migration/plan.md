# Implementation Plan: FastAPI Backend Migration

**Branch**: `001-fastapi-migration` | **Date**: 2026-03-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-fastapi-migration/spec.md`

## Summary

Migrate the Flask backend to FastAPI while maintaining 100% API compatibility. The Flask application (`app.py`) serves 26 API endpoints and static files. The migration reorganizes routes into FastAPI's router-based structure (`api/routes/`) while keeping all business logic in `services/` unchanged. The result enables automatic OpenAPI documentation, async support for future enhancements, and cleaner code organization.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: FastAPI 0.115+, uvicorn[standard], python-multipart
**Storage**: SQLite (`data/trades.db`) - unchanged
**Testing**: Manual API testing via `/docs`, existing pytest suite
**Target Platform**: Linux server (development), localhost
**Project Type**: Web service (REST API + static file serving)
**Performance Goals**: Server startup < 5 seconds; API response times unchanged
**Constraints**: 26 endpoints must maintain identical response schemas; services/ modules remain unchanged; Vue SPA frontend unchanged
**Scale/Scope**: 26 endpoints, single Vue 3 SPA frontend, 7 service modules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Data Integrity | PASS | Migration wraps existing service calls; no change to data validation or API fallback logic |
| II. Graceful Degradation | PASS | Background tasks unchanged (threading.Thread); FastAPI BackgroundTasks used only for lifecycle hooks |
| III. Risk Management | N/A | This migration does not change trading logic |
| IV. Module Autonomy | PASS | API routes are thin wrappers; services/ remain self-contained with explicit interfaces |
| V. Observable Operations | PASS | Logging configuration unchanged; Flask logging → FastAPI logging equivalent |

**Gate Result**: PASS - No violations require justification

## Project Structure

### Documentation (this feature)

```text
specs/001-fastapi-migration/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output (not needed - migration is well-defined)
├── data-model.md        # Phase 1 output (not applicable - no new entities)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (not applicable - internal API)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
# Changes to existing structure
.
├── main.py                      # NEW - FastAPI application entry point
├── app.py                       # EXISTS - Delete after migration validation
├── api/                         # NEW - Route module directory
│   ├── __init__.py
│   ├── response.py              # NEW - success_response(), error_response() helpers
│   └── routes/
│       ├── __init__.py
│       ├── trades.py            # NEW - /api/upload, /api/trades, /api/kline, /api/report
│       ├── screener.py          # NEW - /api/screener/* (9 endpoints)
│       ├── crypto.py            # NEW - /api/crypto/* (9 endpoints)
│       └── backtest.py          # NEW - /api/crypto/backtest/*, /api/stock/backtest/* (5 endpoints)
├── requirements.txt             # MODIFY - Add fastapi, uvicorn, python-multipart
├── services/                    # UNCHANGED
│   ├── parser.py, matcher.py, analyzer.py, screener.py, ...
├── static/                      # UNCHANGED - Vue SPA
└── frontend/                    # UNCHANGED - Vue 3 source
```

**Structure Decision**: Option 2 (Web application) applies because this project has both backend API and frontend. The `api/` directory contains route modules analogous to `backend/src/api/`. All business logic stays in `services/` (equivalent to `backend/src/services/`).

## Phase 0: Research

**Status**: SKIPPED - This is a framework migration (Flask → FastAPI) with a detailed specification document (`doc/fastapi_migration_plan.md`). All technical decisions are already determined:

- Route organization: By domain (trades, screener, crypto, backtest)
- Response format: Preserve `{success: True/False, ...data}` structure
- Background tasks: Keep existing threading, FastAPI only manages lifecycle
- Static files: Use `StaticFiles` mount
- CORS: `CORSMiddleware` with permissive settings for development

## Phase 1: Design & Contracts

### Quickstart

**File**: `quickstart.md`

```markdown
# FastAPI Migration - Quickstart

## Running the Server

```bash
# Install dependencies
pip install -r requirements.txt

# Start FastAPI dev server
uvicorn main:app --reload --port 8000

# Access API docs at:
# http://127.0.0.1:8000/docs
```

## Key Changes

| Item | Before (Flask) | After (FastAPI) |
|------|---------------|-----------------|
| Entry point | `python app.py` | `uvicorn main:app --reload` |
| API docs | None | `http://localhost:8000/docs` |
| Port | 5000 | 8000 |
| Route files | `app.py` single file | `api/routes/*.py` modular |

## Verification Steps

1. Start server: `uvicorn main:app --reload --port 8000`
2. Open `http://127.0.0.1:8000/docs` - should see 26 endpoints
3. Try `/api/screener/index` - should return index data
4. Vue frontend: Update API base URL to port 8000
```

### Agent Context Update

Run `.specify/scripts/bash/update-agent-context.sh claude` to update CLAUDE.md with new FastAPI context if needed.

## Implementation Sequence

### Phase 1: Infrastructure
1. Update `requirements.txt` - add `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`, `python-multipart>=0.0.20`
2. Create `api/__init__.py` - empty package marker
3. Create `api/response.py` - `success_response()` and `error_response()` helpers
4. Create `main.py` - FastAPI app skeleton with lifespan, CORS, static files

### Phase 2: Route Migration (by module)
5. Create `api/routes/__init__.py` - empty package marker
6. Create `api/routes/trades.py` - 4 endpoints (upload, trades, kline, report)
7. Create `api/routes/screener.py` - 9 endpoints
8. Create `api/routes/crypto.py` - 9 endpoints
9. Create `api/routes/backtest.py` - 5 endpoints

### Phase 3: Validation
10. Start server and verify all 26 endpoints work
11. Test frontend integration (update API base URL to port 8000)
12. Verify `/docs` shows all endpoints with correct schemas

### Phase 4: Cleanup
13. Delete `app.py` after full validation
14. Update README/CLAUDE.md with new startup commands

## Complexity Tracking

| Decision | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| Separate `api/routes/` modules | Each route module has 4-9 endpoints; single file would be 700+ lines | Flask-style single file rejected - violates Module Autonomy principle |
| Response helper functions | DRY - 26 endpoints all use same `{success, ...data}` pattern | Inline responses rejected - violates YAGNI for future changes |
| Keep services/ unchanged | Services contain complex business logic (screening, trading, backtesting) | Reimplementing services in FastAPI would introduce bugs and take days |

## Dependencies

- **External**: FastAPI, uvicorn, python-multipart (new)
- **Internal**: All `services/` modules unchanged
- **Data**: SQLite database schema unchanged

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Response format mismatch | Low | High | Test each endpoint against Flask response before deleting app.py |
| CORS issues with Vue | Medium | Medium | Use permissive CORS during migration; tighten after validation |
| Background task threading conflict | Low | High | Daemon threads already configured; no FastAPI task interference expected |

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `requirements.txt` | Modify | Add FastAPI and dependencies |
| `main.py` | Create | FastAPI application entry point |
| `api/__init__.py` | Create | Package marker |
| `api/response.py` | Create | Response helper functions |
| `api/routes/__init__.py` | Create | Package marker |
| `api/routes/trades.py` | Create | Trade endpoints |
| `api/routes/screener.py` | Create | Screener endpoints |
| `api/routes/crypto.py` | Create | Crypto endpoints |
| `api/routes/backtest.py` | Create | Backtest endpoints |
| `app.py` | Delete | Replaced by main.py after validation |
| `CLAUDE.md` | Modify | Update startup commands |
| `README.md` | Modify | Update startup commands |
