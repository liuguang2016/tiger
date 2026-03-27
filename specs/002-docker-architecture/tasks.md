# Tasks: Docker Architecture Migration

**Input**: Design documents from `/specs/002-docker-architecture/`
**Prerequisites**: plan.md, spec.md
**Tests**: None explicitly requested (manual verification)

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Docker Infrastructure)

**Purpose**: Create Docker configuration files

- [X] T001 [P] Create directory structure: `docker/nginx/`, `scripts/`
- [X] T002 [P] Create `docker/nginx/nginx.conf` with reverse proxy config
- [X] T003 [P] Create `.env.example` with database and backend env vars
- [X] T004 [P] Create `Dockerfile` with multi-stage Python build
- [X] T005 [P] Create `docker-compose.yml` with postgres, backend, nginx services
- [X] T006 [P] Create `docker-compose.prod.yml` with production overrides
- [X] T007 Verify `docker-compose config` passes without errors ✅

---

## Phase 2: Foundational (PostgreSQL Support)

**Purpose**: Modify backend to support PostgreSQL (blocks all user stories)

**⚠️ CRITICAL**: Must complete before any user story can be validated

- [X] T008 Add `psycopg2-binary` to `backend/requirements.txt`
- [X] T009 Modify `backend/services/database.py`: add DATABASE_URL env var support, replace sqlite3 with psycopg2, convert SQL syntax (datetime → NOW(), INSERT OR REPLACE → ON CONFLICT)
- [X] T010 Verify `python -c "from backend.services.database import get_conn; print('OK')"` works ✅

---

## Phase 3: User Story 1 - 本地开发 (Priority: P1) 🎯 MVP

**Goal**: `docker-compose up` starts all services and application works

**Independent Test**: `curl http://localhost/api/trades` returns valid JSON

### Implementation

- [X] T011 [P] [US1] Build backend image: `docker-compose build backend` ✅
- [X] T012 [P] [US1] Start all services: `docker-compose up -d` ✅
- [X] T013 [US1] Verify postgres running: `docker-compose ps` shows 3 services ✅
- [X] T014 [US1] Verify frontend accessible: `curl http://localhost:8080` returns HTML ✅
- [X] T015 [US1] Verify API proxy works: `curl http://localhost:8080/api/trades` returns JSON ✅
- [ ] T016 [US1] Verify hot-reload (backend volume mount): modify backend file, restart, changes reflect

**Checkpoint**: Local development environment works end-to-end

---

## Phase 4: User Story 2 - 数据迁移 (Priority: P1)

**Goal**: SQLite data migrates successfully to PostgreSQL

**Independent Test**: PostgreSQL record count == SQLite record count for all 8 tables

### Implementation

- [X] T017 [P] [US2] Create `scripts/migrate_sqlite_to_pg.py` - connect to SQLite
- [X] T018 [P] [US2] Create PostgreSQL table schemas (8 tables with SERIAL instead of AUTOINCREMENT)
- [ ] T019 [US2] Implement batch data migration for all 8 tables
- [ ] T020 [US2] Add record count verification (source vs target)
- [ ] T021 [US2] Test migration: run script, verify all tables migrated correctly

**Checkpoint**: Data migration script works, SQLite data lives in PostgreSQL

---

## Phase 5: User Story 3 - 生产部署 (Priority: P2)

**Goal**: Production-optimized deployment with small image size

**Independent Test**: `docker-compose -f docker-compose.yml -f docker-compose.prod.yml config` works, image < 500MB

### Implementation

- [ ] T022 [P] [US3] Optimize Dockerfile runtime stage (remove builder, copy only needed files)
- [ ] T023 [P] [US3] Add Docker logging config to docker-compose.prod.yml
- [X] T024 [US3] Verify image size < 500MB: `docker images | grep tigger` ✅ (439MB)
- [ ] T025 [US3] Verify production compose config: `docker-compose -f docker-compose.yml -f docker-compose.prod.yml config`

**Checkpoint**: Production deployment configuration works and image is optimized

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T026 [P] Update `quickstart.md` with actual commands and verification steps
- [ ] T027 [P] Update `CLAUDE.md` with Docker commands (cd backend omitted, docker-compose usage)
- [ ] T028 Verify all acceptance criteria from spec.md:
  - `docker-compose up` starts all services
  - Frontend `http://localhost` accessible
  - API `/api/trades` returns JSON
  - PostgreSQL data persists across restarts
  - Migration script completes all 8 tables
  - Image < 500MB
  - Hot-reload works in dev mode
- [ ] T029 [P] Commit all Docker infrastructure files

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 (本地开发) should complete first as it validates the infrastructure
  - US2 (数据迁移) can start after US1 (needs running postgres)
  - US3 (生产部署) can start after US1 (needs working compose)
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational - validates Docker infra works
- **User Story 2 (P1)**: Starts after US1 - needs running PostgreSQL container
- **User Story 3 (P2)**: Starts after US1 - needs working docker-compose

### Within Each User Story

- Docker/tasks can proceed in parallel (marked [P])
- Verification tasks depend on implementation tasks
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- US1 implementation tasks T011, T012 can run in parallel with T013-T016
- US2 migration script creation T017-T018 can run in parallel
- Polish tasks T026, T027 can run in parallel

---

## Parallel Example

```bash
# Phase 1 Setup - all 6 tasks can run in parallel:
T001: Create directory structure
T002: Create nginx.conf
T003: Create .env.example
T004: Create Dockerfile
T005: Create docker-compose.yml
T006: Create docker-compose.prod.yml

# Phase 4 US2 - migration script:
T017: Create migration script (SQLite connection)
T018: Create PG schemas (parallel with T017)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (本地开发)
4. **STOP and VALIDATE**: `docker-compose up -d` works, `curl http://localhost/api/trades` returns JSON
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Infrastructure ready
2. US1 → Local dev works (MVP!)
3. US2 → Data migration works
4. US3 → Production optimized

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- This is infrastructure work - manual verification replaces automated tests
