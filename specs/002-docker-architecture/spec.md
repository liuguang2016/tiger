# Docker 架构改造规范

**Feature Name**: Docker-based Full-stack Deployment
**Date**: 2026-03-26
**Status**: Draft

---

## 1. 背景与目标

### 当前状态
- Backend: FastAPI (Python) 运行在 port 8002
- Frontend: Vue 3 构建产物由 FastAPI static files 服务
- Database: SQLite (`data/trades.db`)，需迁移到 PostgreSQL

### 目标
- 使用 Docker + Docker Compose 管理本地开发和生产部署
- 前后端分离：Nginx 分别代理前端(80)和后端(8002)
- PostgreSQL 通过 Docker 容器运行
- 一次性迁移 SQLite 数据到 PostgreSQL

### 约束
- 部署目标：单台 VPS/云服务器
- 开发/生产使用同一套 docker-compose.yml
- 不破坏现有后端代码结构（保持 FastAPI + SQLAlchemy 风格）

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────┐
│                   Nginx (:80)                    │
│  ┌──────────────────┐  ┌─────────────────────┐  │
│  │  静态资源         │  │  /api/* 反向代理     │  │
│  │  (Frontend dist) │  │  → backend:8002     │  │
│  └──────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
         ┌────▼────┐          ┌──────▼──────┐
         │Backend  │          │  PostgreSQL │
         │FastAPI  │          │    :5432    │
         │ :8002   │          └─────────────┘
         └─────────┘
```

### 组件说明

| 组件 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| Nginx | nginx:alpine | 80 | 反向代理 + 静态文件服务 |
| Backend | python:3.14-slim | 8002 | FastAPI 应用 |
| PostgreSQL | postgres:16-alpine | 5432 | 数据库 |

---

## 3. 目录结构

```
tigger/
├── docker/
│   └── nginx/
│       └── nginx.conf           # Nginx 配置
├── docker-compose.yml           # 统一的 Compose 文件（开发+生产）
├── Dockerfile                   # 后端构建（多阶段构建）
├── .env.example                 # 环境变量模板
├── backend/
│   └── services/database.py     # 保持 SQLAlchemy 风格（稍后迁移）
├── scripts/
│   └── migrate_sqlite_to_pg.py  # SQLite → PostgreSQL 迁移脚本
└── data/                        # SQLite 数据（迁移后不再使用）
```

---

## 4. 详细设计

### 4.1 环境变量配置 (.env.example)

```env
# Database
POSTGRES_DB=tigger
POSTGRES_USER=tigger
POSTGRES_PASSWORD=your_secure_password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Backend
DATABASE_URL=postgresql://tigger:your_secure_password@postgres:5432/tigger
BACKEND_PORT=8002

# Frontend (build args)
VITE_API_BASE_URL=/api
```

### 4.2 Docker Compose 结构

**开发模式** (`docker-compose.yml` 默认):
- 所有服务运行在本地
- Volume 挂载代码目录（热重载）
- PostgreSQL 数据持久化到 named volume

**生产模式** (`docker-compose.yml` + `docker-compose.prod.yml`):
- 只读文件系统
- 优化镜像大小
- 无需 volume 挂载

### 4.3 Nginx 配置

```nginx
server {
    listen 80;
    server_name _;

    # 前端静态文件
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://backend:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4.4 后端 Dockerfile (多阶段构建)

**阶段 1 - Builder**: 安装依赖，复制代码
**阶段 2 - Runtime**: 精简镜像，只复制必要文件

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.14-slim AS builder

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.14-slim AS runtime

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY backend/ ./backend/
COPY --from=builder /usr/local/bin /usr/local/bin

ENV PYTHONPATH=/app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8002"]
```

### 4.5 数据迁移脚本

**脚本位置**: `scripts/migrate_sqlite_to_pg.py`

**迁移步骤**:
1. 读取 SQLite `data/trades.db`
2. 连接 PostgreSQL
3. 执行 `CREATE TABLE` (PostgreSQL 语法)
4. 批量 INSERT 数据
5. 验证记录数一致
6. 输出迁移报告

**PostgreSQL 语法差异处理**:
| SQLite | PostgreSQL |
|--------|------------|
| `AUTOINCREMENT` | `SERIAL` / `GENERATED ALWAYS AS IDENTITY` |
| `datetime('now', 'localtime')` | `NOW()` |
| `PRAGMA journal_mode=WAL` | PostgreSQL WAL (默认) |
| `INSERT OR REPLACE` | `ON CONFLICT DO UPDATE` |

### 4.6 后端 database.py 修改

修改 `database.py` 以支持 PostgreSQL:
- 使用 `DATABASE_URL` 环境变量
- 替换 `sqlite3` 为 `psycopg2` 或 `asyncpg`
- SQLAlchemy 2.0 兼容语法

**不修改的地方**:
- 表结构定义 (DDL)
- 业务逻辑函数
- API 路由

---

## 5. 用户场景

### 场景 1: 本地开发

**步骤**:
1. 克隆代码
2. 复制 `.env.example` → `.env`
3. 运行 `docker-compose up`
4. 访问 `http://localhost` 查看前端
5. API: `http://localhost/api/*`

**预期结果**:
- 前端正常显示
- 后端 API 正常工作
- PostgreSQL 数据持久化

### 场景 2: 数据迁移

**步骤**:
1. 确保 SQLite 数据存在 (`data/trades.db`)
2. 启动 PostgreSQL 容器
3. 运行迁移脚本 `python scripts/migrate_sqlite_to_pg.py`
4. 验证数据完整性

**预期结果**:
- 所有表数据迁移到 PostgreSQL
- 记录数一致
- 可删除 SQLite 文件

### 场景 3: 生产部署

**步骤**:
1. 服务器安装 Docker
2. 克隆项目
3. 配置 `.env`
4. 运行 `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
5. 配置 Nginx 反向代理（或使用容器自带 80 端口）

**预期结果**:
- 服务正常运行
- 镜像大小优化
- 数据持久化

---

## 6. 验收标准

### 开发环境
- [ ] `docker-compose up` 能启动全部服务
- [ ] 前端 `http://localhost` 正常访问
- [ ] 后端 API 正常工作
- [ ] PostgreSQL 数据持久化
- [ ] 代码修改能热重载

### 数据迁移
- [ ] 迁移脚本能成功执行
- [ ] 所有 8 张表数据完整迁移
- [ ] 迁移后记录数与 SQLite 一致

### 生产部署
- [ ] Docker 镜像 < 500MB
- [ ] 无需代码挂载即可运行
- [ ] `docker-compose.prod.yml` 正常工作

### 功能回归
- [ ] 原 SQLite 功能不受影响（迁移后）
- [ ] API 响应格式不变

---

## 7. 依赖项

### Python 包 (backend/requirements.txt)
- `psycopg2-binary` 或 `asyncpg` (PostgreSQL 驱动)
- 其他保持不变

### Docker 资源
- Docker Engine 20.10+
- Docker Compose 2.0+
- 磁盘空间: ~1GB (开发), ~800MB (生产优化后)

---

## 8. 已知限制

1. **热重载**: Python 代码挂载在开发模式下可热重载，但 uvicorn `--reload` 需确认工作正常
2. **Windows**: 未测试 Windows Docker Desktop 兼容性
3. **ARM**: 树莓派 (ARM) 需使用 `postgres:16-arm64` 镜像
4. **数据迁移时机**: 迁移脚本在 PostgreSQL 启动后、Backend 启动前执行

---

## 9. 后续优化 (不包含在当前范围)

- HTTPS 支持 (Let's Encrypt)
- 自动备份策略
- Kubernetes 部署配置
- CI/CD 流水线

---

## 10. 假设

1. 用户有 Docker 基础知识和命令行操作能力
2. 生产服务器为 Linux (Ubuntu 20.04+)
3. 不需要容器 orchestration 工具 (Swarm/Kubernetes)
4. SQLite 数据量 < 1GB，迁移时间可接受
