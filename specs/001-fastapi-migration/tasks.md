# Tasks: FastAPI Backend Migration

**Input**: Design documents from `/specs/001-fastapi-migration/`
**Prerequisites**: plan.md, spec.md

**Organization**: Tasks are organized by implementation phase, grouped by route module. Route modules can be implemented in parallel since they are independent.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install dependencies and create the package structure

- [x] T001 [P] Update `requirements.txt` - add `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`, `python-multipart>=0.0.20`
- [x] T002 Create `api/__init__.py` - empty package marker
- [x] T003 Create `api/routes/__init__.py` - empty package marker

---

## Phase 2: Foundational (FastAPI App Core)

**Purpose**: Create the FastAPI application entry point and response helpers that ALL routes depend on

**⚠️ CRITICAL**: All route module work MUST wait for this phase to complete

- [x] T004 Create `api/response.py` - implement `success_response()` and `error_response()` helpers
- [x] T005 Create `main.py` - FastAPI app with lifespan context manager, CORS middleware, static file mounting

**Checkpoint**: Core app ready - route modules can now be implemented

---

## Phase 3: Route Migration - Trades Module

**Purpose**: Migrate trade-related endpoints (4 endpoints)

- [x] T006 [P] [US1] Create `api/routes/trades.py` - implement `/api/upload` POST endpoint
- [x] T007 [P] [US1] Create `api/routes/trades.py` - implement `/api/trades` GET endpoint
- [x] T008 [P] [US1] Create `api/routes/trades.py` - implement `/api/kline` GET endpoint
- [x] T009 [P] [US1] Create `api/routes/trades.py` - implement `/api/report` GET endpoint

---

## Phase 4: Route Migration - Screener Module

**Purpose**: Migrate stock screener endpoints (9 endpoints)

- [x] T010 [P] [US1] Create `api/routes/screener.py` - implement `/api/screener/run` POST endpoint
- [x] T011 [P] [US1] Create `api/routes/screener.py` - implement `/api/screener/status` GET endpoint
- [x] T012 [P] [US1] Create `api/routes/screener.py` - implement `/api/screener/index` GET endpoint
- [x] T013 [P] [US1] Create `api/routes/screener.py` - implement `/api/screener/pool` GET endpoint
- [x] T014 [P] [US1] Create `api/routes/screener.py` - implement `/api/screener/pool/<stock_code>` DELETE endpoint
- [x] T015 [P] [US1] Create `api/routes/screener.py` - implement `/api/screener/pool` DELETE (clear all) endpoint
- [x] T016 [P] [US1] Create `api/routes/screener.py` - implement `/api/screener/strategies` GET endpoint
- [x] T017 [P] [US1] Create `api/routes/screener.py` - implement `/api/screener/strategy/run` POST endpoint
- [x] T018 [P] [US1] Create `api/routes/screener.py` - register screener router in `main.py`

---

## Phase 5: Route Migration - Crypto Module

**Purpose**: Migrate cryptocurrency endpoints (9 endpoints)

- [x] T019 [P] [US1] Create `api/routes/crypto.py` - implement `/api/crypto/config` GET and POST endpoints
- [x] T020 [P] [US1] Create `api/routes/crypto.py` - implement `/api/crypto/bot/start` POST endpoint
- [x] T021 [P] [US1] Create `api/routes/crypto.py` - implement `/api/crypto/bot/stop` POST endpoint
- [x] T022 [P] [US1] Create `api/routes/crypto.py` - implement `/api/crypto/bot/status` GET endpoint
- [x] T023 [P] [US1] Create `api/routes/crypto.py` - implement `/api/crypto/bot/scan` POST endpoint
- [x] T024 [P] [US1] Create `api/routes/crypto.py` - implement `/api/crypto/trades` GET endpoint
- [x] T025 [P] [US1] Create `api/routes/crypto.py` - implement `/api/crypto/kline` GET endpoint
- [x] T026 [P] [US1] Create `api/routes/crypto.py` - register crypto router in `main.py`

---

## Phase 6: Route Migration - Backtest Module

**Purpose**: Migrate backtest endpoints (5 endpoints)

- [x] T027 [P] [US1] Create `api/routes/backtest.py` - implement `/api/crypto/backtest/run` POST endpoint
- [x] T028 [P] [US1] Create `api/routes/backtest.py` - implement `/api/crypto/backtest/status` GET endpoint
- [x] T029 [P] [US1] Create `api/routes/backtest.py` - implement `/api/crypto/backtest/history` GET endpoint
- [x] T030 [P] [US1] Create `api/routes/backtest.py` - implement `/api/crypto/backtest/<run_id>` GET endpoint
- [x] T031 [P] [US1] Create `api/routes/backtest.py` - implement `/api/stock/backtest/run` POST and `/api/stock/backtest/status` GET endpoints
- [x] T032 [P] [US1] Create `api/routes/backtest.py` - register backtest router in `main.py`

---

## Phase 7: Validation

**Purpose**: Verify all 26 endpoints work correctly and OpenAPI docs are generated

**Requires**: Install dependencies with `pip install -r requirements.txt`

- [x] T033 Start `uvicorn main:app --reload --port 8000` and verify server starts within 5 seconds
- [x] T034 Verify `/docs` shows all 26 endpoints listed with correct paths
- [x] T035 [US1] Test `/api/screener/index` - verify response format matches Flask exactly
- [ ] T036 [US1] Test `/api/upload` - upload a CSV and verify parse/trade matching works
- [ ] T037 [US1] Test `/api/crypto/kline` - verify crypto K-line data returns correctly
- [ ] T038 [US3] Start a screener task and verify status polling returns progress updates
- [ ] T039 [US4] Verify static files are served at `/static` and CORS headers are present
- [ ] T040 [US4] Test Vue frontend integration (update API base URL to port 8000)

---

## Phase 8: Cleanup

**Purpose**: Remove Flask app and update documentation

- [ ] T041 [P] Delete `app.py` after full validation confirms all endpoints work
- [x] T042 Update `CLAUDE.md` - change startup command from `python app.py` to `uvicorn main:app --reload`
- [x] T043 Update `README.md` - change port from 5000 to 8000, update startup instructions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all routes
- **Route Modules (Phases 3-6)**: All depend on Foundational (Phase 2)
  - Routes can proceed in parallel (T006-T009, T010-T018, T019-T026, T027-T032 can all run together)
- **Validation (Phase 7)**: Depends on ALL routes complete
- **Cleanup (Phase 8)**: Depends on Validation passing

### Parallel Opportunities

The following task groups can run in PARALLEL after Phase 2 completes:

```
Group A (Trades): T006, T007, T008, T009
Group B (Screener): T010, T011, T012, T013, T014, T015, T016, T017
Group C (Crypto): T019, T020, T021, T022, T023, T024, T025
Group D (Backtest): T027, T028, T029, T030, T031
```

All groups A, B, C, D can run simultaneously after Phase 2 completes.

---

## Implementation Strategy

### Sequential (Single Developer)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all routes)
3. Complete Phase 3: Trades
4. Complete Phase 4: Screener
5. Complete Phase 5: Crypto
6. Complete Phase 6: Backtest
7. **STOP and VALIDATE**: Phase 7 - test all endpoints
8. Phase 8: Cleanup

### Parallel (Multiple Developers)

1. Complete Phase 1 + Phase 2 together
2. Once Foundational is done:
   - Developer A: Phase 3 (Trades)
   - Developer B: Phase 4 (Screener)
   - Developer C: Phase 5 (Crypto)
   - Developer D: Phase 6 (Backtest)
3. All routes complete → Validation together
4. Cleanup

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 43 |
| Phase 1 (Setup) | 3 tasks |
| Phase 2 (Foundational) | 2 tasks |
| Phase 3 (Trades) | 4 tasks |
| Phase 4 (Screener) | 9 tasks |
| Phase 5 (Crypto) | 8 tasks |
| Phase 6 (Backtest) | 6 tasks |
| Phase 7 (Validation) | 8 tasks |
| Phase 8 (Cleanup) | 3 tasks |

### User Story Coverage

| User Story | Tasks | Description |
|------------|-------|-------------|
| US1 (API Preservation) | T006-T032, T035-T037 | All 26 endpoints migrated with exact response format |
| US2 (OpenAPI Docs) | T034 | `/docs` shows all endpoints |
| US3 (Background Tasks) | T038 | Screener status polling works |
| US4 (Static/CORS) | T039-T040 | Vue SPA served correctly |

### MVP Scope

The MVP is the complete migration (all phases). Since this is a framework migration, partial implementation provides no value - the system is only "done" when all 26 endpoints are working.

---

## Notes

- All route tasks are marked [P] because they modify different files
- Phase 2 (Foundational) MUST complete before any route work
- Route phases (3-6) can run in parallel with 4 developers
- Validation is critical - do not skip any verification step
- Keep `app.py` until ALL validations pass
