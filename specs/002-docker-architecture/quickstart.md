# Docker 架构 - 快速开始

## 前置要求

- Docker Engine 20.10+
- Docker Compose 2.0+
- Node.js 20+ (仅前端构建)

## 本地开发

```bash
# 1. 复制环境变量模板
cp .env.example .env
# 编辑 .env，设置 POSTGRES_PASSWORD

# 2. 构建前端 (需要在容器外构建)
cd frontend
pnpm install
pnpm run build
cd ..

# 3. 启动全部服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 访问
# 前端: http://localhost:8080
# API:  http://localhost:8080/api/*
# API 文档: http://localhost:8080/docs
```

## 生产部署

```bash
# 1. 复制环境变量
cp .env.example .env
# 编辑 .env

# 2. 构建前端
cd frontend && pnpm run build && cd ..

# 3. 构建并启动 (使用生产配置)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. 检查状态
docker-compose ps
```

## 数据迁移

```bash
# 1. 确保 SQLite 数据存在
ls data/trades.db

# 2. 启动 PostgreSQL (如果未启动)
docker-compose up -d postgres

# 3. 运行迁移脚本
python scripts/migrate_sqlite_to_pg.py

# 4. 验证
docker-compose exec postgres psql -U tigger -d tigger -c "SELECT COUNT(*) FROM matched_trades"
```

## 常用命令

```bash
# 停止服务
docker-compose down

# 停止并删除数据卷 (慎用!)
docker-compose down -v

# 重建镜像
docker-compose build --no-cache

# 查看日志
docker-compose logs -f [service]

# 进入后端容器
docker-compose exec backend bash

# 进入 PostgreSQL
docker-compose exec postgres psql -U tigger -d tigger
```

## 验证清单

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| 前端可访问 | `curl http://localhost` | 返回 HTML |
| API 可用 | `curl http://localhost/api/trades` | 返回 JSON |
| PostgreSQL 运行 | `docker-compose ps` | 3 个服务 running |
| 数据迁移 | `python scripts/migrate_sqlite_to_pg.py` | 8 张表全部迁移 |
| 镜像大小 | `docker images \| grep tigger` | < 500MB |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_DB` | tigger | 数据库名 |
| `POSTGRES_USER` | tigger | 用户名 |
| `POSTGRES_PASSWORD` | (必填) | 数据库密码 |
| `POSTGRES_HOST` | postgres | 主机名 |
| `POSTGRES_PORT` | 5432 | 端口 |
| `DATABASE_URL` | 自动生成 | 完整连接字符串 |
