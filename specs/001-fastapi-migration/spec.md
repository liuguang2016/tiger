# Feature Specification: FastAPI Backend Migration

**Feature Branch**: `001-fastapi-migration`
**Created**: 2026-03-26
**Status**: Draft
**Input**: User description: "@doc/fastapi_migration_plan.md 按文档的要求重构这个项目的后端"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - API Endpoint Preservation (Priority: P1)

All existing API endpoints continue to function identically after migration. Frontend applications can switch from Flask to FastAPI backend without any frontend code changes.

**Why this priority**: This is the core requirement - the migration must not break existing integrations.

**Independent Test**: Can be validated by running existing frontend against FastAPI backend and confirming all features work identically.

**Acceptance Scenarios**:

1. **Given** a CSV file upload request to `/api/upload`, **When** sent to FastAPI backend, **Then** the system returns the same `{success: True/False, ...}` response format as Flask
2. **Given** a screener status poll to `/api/screener/status`, **When** a screening task is running, **Then** the response contains identical `status`, `progress`, `results` fields
3. **Given** a crypto kline request to `/api/crypto/kline`, **When** valid parameters are provided, **Then** the response matches the exact structure of the Flask response
4. **Given** a backtest run request, **When** the task completes, **Then** the result structure is identical to the original Flask implementation

---

### User Story 2 - OpenAPI Documentation (Priority: P2)

FastAPI provides automatic interactive API documentation at `/docs`, allowing developers to explore and test all endpoints without separate documentation effort.

**Why this priority**: Developer experience improvement - easier debugging and API exploration.

**Independent Test**: Can be verified by accessing `/docs` in a browser and confirming all endpoints appear with correct schemas.

**Acceptance Scenarios**:

1. **Given** a developer opens `/docs` in a browser, **When** the FastAPI server is running, **Then** all 26 API endpoints are listed with their schemas
2. **Given** a developer clicks on any endpoint in `/docs`, **When** they expand the endpoint, **Then** they can see request parameters and example responses
3. **Given** a developer fills in parameters in `/docs`, **When** they click "Execute", **Then** the actual API call is made and the response is displayed

---

### User Story 3 - Background Task Integrity (Priority: P2)

Long-running background operations (stock screening, backtests) continue to run correctly using the existing threading-based implementation, without modification.

**Why this priority**: Core business logic must not be disrupted by the framework change.

**Independent Test**: Can be validated by starting a stock screening task and confirming it completes with correct results.

**Acceptance Scenarios**:

1. **Given** a stock screening request is submitted, **When** the background task starts, **Then** status polling returns accurate progress updates until completion
2. **Given** a backtest is running, **When** multiple status polls occur, **Then** each poll returns current progress without interfering with the task
3. **Given** the FastAPI server receives a shutdown signal, **When** background tasks are running, **Then** daemon threads complete gracefully without crashing

---

### User Story 4 - Static File and CORS Support (Priority: P2)

The Vue 3 SPA frontend continues to be served correctly, and API calls from the browser are allowed via CORS.

**Why this priority**: Frontend must remain unchanged and functional.

**Independent Test**: Can be verified by serving the Vue app and confirming all API calls succeed.

**Acceptance Scenarios**:

1. **Given** a browser loads `http://127.0.0.1:8000/`, **When** the Vue SPA is present, **Then** it is served correctly with all assets
2. **Given** the Vue SPA makes API calls from `http://127.0.0.1:8000/`, **When** an API endpoint is called, **Then** CORS headers allow the request without errors

---

### Edge Cases

- What happens when the Flask `app.py` is deleted but the new `main.py` has bugs? **Mitigation**: Keep both files during transition, delete only after full validation
- How does the system handle requests to endpoints that exist in Flask but are not yet migrated? **Mitigation**: Clear migration checklist prevents this
- What if akshare or other external API rate-limits requests during testing? **Mitigation**: Existing retry and cache mechanisms in services/ remain unchanged

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide all 26 existing Flask API endpoints via FastAPI routes
- **FR-002**: All API responses MUST maintain the existing `{success: True/False, ...data}` JSON structure
- **FR-003**: System MUST serve static files (Vue SPA) from the `static/` directory
- **FR-004**: System MUST allow cross-origin requests from any origin for development
- **FR-005**: Background tasks (screening, backtests) MUST continue to use existing threading implementation without modification
- **FR-006**: System MUST initialize the SQLite database on startup
- **FR-007**: System MUST run on port 8000 with `uvicorn main:app --reload`
- **FR-008**: API routes MUST be organized into: `trades.py`, `screener.py`, `crypto.py`, `backtest.py`
- **FR-009**: System MUST provide a unified error response format via `success_response()` and `error_response()` helpers
- **FR-010**: System MUST allow frontend to switch between Flask and FastAPI by changing only the API base URL

### Key Entities

- **API Route Module**: Groups related endpoints (trades, screener, crypto, backtest)
- **Response Helper**: Standardizes API response formatting across all routes
- **Application Lifespan Manager**: Handles startup (DB init) and shutdown cleanup
- **Background Task**: Existing threading-based tasks for long-running operations

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 26 API endpoints return responses matching Flask response schemas exactly
- **SC-002**: Frontend integration tests pass with FastAPI replacing Flask (100% feature parity)
- **SC-003**: OpenAPI documentation at `/docs` lists all 26 endpoints with correct schemas
- **SC-004**: Stock screening completes with identical results when run on FastAPI vs Flask
- **SC-005**: System starts successfully with `uvicorn main:app --reload` within 5 seconds
- **SC-006**: No breaking changes to existing frontend Vue 3 application

## Assumptions

- Vue 3 SPA frontend will be redeployed/rebuilt separately and will point to FastAPI backend
- External data sources (akshare, Binance) are accessed unchanged via existing service modules
- SQLite database schema remains identical - no migrations needed
- Developers understand they should test both before and after migration for parity
- The migration is done incrementally by route module, allowing partial rollback if needed
