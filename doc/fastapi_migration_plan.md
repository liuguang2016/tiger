# FastAPI 改造计划

## Context

当前项目使用 Flask 作为后端框架，已有的功能包括：
- A股/数字货币交易分析
- 交割单CSV上传、成交匹配、风格分析
- 股票池筛选（春跌反弹策略）
- 加密货币自动交易机器人（模拟/实盘）
- 回测引擎（加密货币 + 股票）

改造原因：FastAPI 更现代化的 ASGI 框架，支持异步、自动 OpenAPI 文档、类型安全。

## 改造范围

**不变：**
- `services/` 下所有业务逻辑模块（parser, matcher, analyzer, screener, crypto_trader 等）
- 前端 Vue 3 SPA（保持不变）
- SQLite 数据库结构

**变更：**
- `app.py` → FastAPI 应用
- 新增 `api/` 目录存放路由模块

---

## 项目结构

```
tigger/
├── main.py                      # FastAPI 入口
├── api/
│   ├── __init__.py
│   ├── response.py              # 响应格式化（保持 {success: True} 兼容）
│   └── routes/
│       ├── __init__.py
│       ├── trades.py            # /api/upload, /api/trades, /api/kline, /api/report
│       ├── screener.py          # /api/screener/*
│       ├── crypto.py            # /api/crypto/*
│       └── backtest.py          # /api/crypto/backtest/*, /api/stock/backtest/*
├── requirements.txt             # 添加 fastapi, uvicorn, python-multipart
└── app.py                       # 改造完成后删除
```

---

## 关键设计决策

### 1. 响应格式（保持兼容）
```python
# api/response.py
def success_response(data: dict) -> JSONResponse:
    return JSONResponse(content={"success": True, **data})

def error_response(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(content={"success": False, "message": message}, status_code=status_code)
```

### 2. 后台任务（保持现有线程模式）
`services/screener.py`、`crypto_backtest.py` 等已自行管理 `threading.Thread`，无需改造。
FastAPI 用 `BackgroundTasks` 做生命周期钩子，但后台任务本身不变。

### 3. 启动/关闭
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()  # 启动时初始化数据库
    yield
    # 关闭时自动清理（services 自己管）
```

### 4. 静态文件 + CORS
```python
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```

---

## 实施步骤

### Phase 1: 基础设施
1. 更新 `requirements.txt` 添加依赖
2. 创建 `api/response.py` 响应工具
3. 创建 `main.py` 骨架

### Phase 2: 路由迁移（逐模块）
4. 创建 `api/routes/trades.py` — 4个端点
5. 创建 `api/routes/screener.py` — 9个端点
6. 创建 `api/routes/crypto.py` — 9个端点
7. 创建 `api/routes/backtest.py` — 5个端点

### Phase 3: 验证
8. 启动 `uvicorn main:app --reload --port 8000`
9. 测试全部 26 个端点
10. 前端通过 Vite 代理或 CORS 联调

### Phase 4: 收尾
11. 删除原 `app.py`
12. 更新启动命令文档

---

## 需修改的文件清单

| 文件 | 操作 |
|------|------|
| `requirements.txt` | 添加 `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`, `python-multipart>=0.0.20` |
| `main.py` | 新建 — FastAPI 应用、路由注册、生命周期、CORS |
| `api/__init__.py` | 新建 |
| `api/response.py` | 新建 — success_response, error_response |
| `api/routes/__init__.py` | 新建 |
| `api/routes/trades.py` | 新建 — 4个路由 |
| `api/routes/screener.py` | 新建 — 9个路由 |
| `api/routes/crypto.py` | 新建 — 9个路由 |
| `api/routes/backtest.py` | 新建 — 5个路由 |
| `app.py` | 删除 |

---

## 验证方式

1. 启动：`uvicorn main:app --reload --port 8000`
2. 访问 `http://127.0.0.1:8000/docs` 查看自动生成的 OpenAPI 文档
3. 前端测试所有功能：
   - CSV 上传 + 成交匹配
   - 股票池筛选（启动任务 + 轮询状态）
   - 加密货币 K线 + 机器人启停
   - 回测运行 + 轮询结果
4. 对比 FastAPI 和原 Flask 的响应格式是否一致
