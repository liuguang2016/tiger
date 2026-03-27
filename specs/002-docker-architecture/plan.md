# Implementation Plan: Docker Architecture Migration

**Branch**: `002-docker-architecture` | **Date**: 2026-03-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-docker-architecture/spec.md`

---

## Summary

将项目从 SQLite + FastAPI 直接服务架构迁移到 Docker 容器化部署：Nginx 反向代理 + FastAPI (Backend) + PostgreSQL (Docker)。支持本地开发和生产部署两种模式，使用同一套 docker-compose.yml。

---

## Technical Context

**Language/Version**: Python 3.14, Node 20+, Docker Engine 20.10+, Docker Compose 2.0+
**Primary Dependencies**: FastAPI, Vue 3, PostgreSQL 16, Nginx alpine
**Storage**: PostgreSQL 16 (via Docker), SQLite (迁移后归档)
**Testing**: 手动验证 + docker-compose up
**Target Platform**: Linux VPS/云服务器 (Ubuntu 20.04+)
**Project Type**: Web Service (Full-stack: Vue + FastAPI + PostgreSQL)
**Performance Goals**: 生产镜像 < 500MB, 启动时间 < 60s
**Constraints**: 开发/生产使用同一套配置, 不破坏现有业务逻辑
**Scale/Scope**: 单台服务器, 小规模部署

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Data Integrity | ✅ PASS | PostgreSQL 提供 ACID 保证，比 SQLite 更适合生产 |
| II. Graceful Degradation | ✅ PASS | Docker Compose 独立管理各服务，一服务挂不影响其他 |
| III. Risk Management | N/A | 非交易逻辑变更 |
| IV. Module Autonomy | ✅ PASS | Nginx/Backend/PostgreSQL 完全独立容器 |
| V. Observable Operations | ⚠️ CONSIDER | 日志需配置 Docker logging driver |

**Violations**: 无严重违规。日志配置需在 docker-compose 中指定。

---

## Project Structure

### Documentation (this feature)

```text
specs/002-docker-architecture/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output (N/A - 技术栈已确定)
├── data-model.md        # Phase 1 output (N/A - DB schema不变)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - 内部API)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root) - 新增文件

```text
tigger/
├── docker/
│   └── nginx/
│       └── nginx.conf           # Nginx 配置
├── docker-compose.yml           # 开发 + 生产共用
├── docker-compose.prod.yml      # 生产覆盖 (可选)
├── Dockerfile                   # 后端多阶段构建
├── .env.example                 # 环境变量模板
├── scripts/
│   └── migrate_sqlite_to_pg.py # SQLite → PostgreSQL 迁移
├── backend/
│   └── services/
│       └── database.py          # 修改: 支持 PostgreSQL
└── frontend/
    └── (Vue 构建产物)
```

**Structure Decision**: Web application (Option 2). 前后端分离，Nginx 统一入口。

---

## Complexity Tracking

> 无复杂度违规。所有变更都是新增文件，不修改现有业务逻辑。

---

## Phase 1: Implementation Tasks

### Task 1: 创建 Docker 基础设施

**Files to create/modify:**
- `docker/nginx/nginx.conf` (new)
- `docker-compose.yml` (new)
- `docker-compose.prod.yml` (new)
- `Dockerfile` (new)
- `.env.example` (new)

**Verification**: `docker-compose config` 无语法错误

---

### Task 2: 修改后端 database.py 支持 PostgreSQL

**Files to modify:**
- `backend/services/database.py` (modify)

**Changes:**
- 添加 `DATABASE_URL` 环境变量支持
- 添加 `psycopg2` 依赖
- 替换 SQLite 连接为 PostgreSQL 连接
- SQL 语法调整: `datetime('now','localtime')` → `NOW()`, `INSERT OR REPLACE` → `ON CONFLICT`

**Verification**: `python -c "from services.database import get_conn; print('OK')"`

---

### Task 3: 创建数据迁移脚本

**Files to create:**
- `scripts/migrate_sqlite_to_pg.py` (new)

**Steps:**
1. 连接源 SQLite (`data/trades.db`)
2. 连接目标 PostgreSQL
3. 创建表结构 (PostgreSQL 语法)
4. 批量迁移 8 张表数据
5. 验证记录数

**Verification**: 迁移后 PostgreSQL 记录数 == SQLite 记录数

---

### Task 4: 更新依赖配置

**Files to modify:**
- `backend/requirements.txt` (add psycopg2-binary)
- `frontend/package.json` (可能需要调整构建配置)

**Verification**: `pip install -r backend/requirements.txt` 成功

---

### Task 5: 验证完整流程

**Steps:**
1. 构建镜像: `docker-compose build`
2. 启动服务: `docker-compose up -d`
3. 检查健康: `curl http://localhost/api/trades`
4. 数据迁移: `python scripts/migrate_sqlite_to_pg.py`
5. 功能验证: 前端 `http://localhost` 正常访问

---

## Implementation Notes

### 多阶段 Dockerfile

```dockerfile
# Stage 1: Builder
FROM python:3.14-slim AS builder
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.14-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY backend/ ./backend/
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8002"]
```

### docker-compose 开发模式

```yaml
services:
  postgres:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: tigger
      POSTGRES_USER: tigger
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

  backend:
    build: .
    volumes:
      - ./backend:/app/backend  # 开发模式热重载
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    depends_on:
      - postgres

  nginx:
    image: nginx:alpine
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/conf.d/default.conf
      - ./frontend/dist:/usr/share/nginx/html
    ports:
      - "80:80"
    depends_on:
      - backend
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|----------|-------------|
| 1 | `docker-compose up` 启动全部服务 | `docker-compose ps` 显示 3 个 running |
| 2 | 前端 `http://localhost` 正常显示 | curl 返回 HTML |
| 3 | 后端 API `/api/trades` 正常响应 | curl 返回 JSON |
| 4 | PostgreSQL 数据持久化 | 重启后数据仍在 |
| 5 | 迁移脚本成功执行 | 8 张表数据完整迁移 |
| 6 | 生产镜像 < 500MB | `docker images` 检查 |
| 7 | 代码热重载 (开发模式) | 修改代码后无需重建 |
