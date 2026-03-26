# 前端 JavaScript 转 TypeScript 迁移设计

**日期**: 2026-03-26
**项目**: Tigger 前端 TypeScript 迁移
**策略**: 渐进式迁移

---

## 1. 设计目标

- 将前端代码从 JavaScript 转换为 TypeScript
- 提升代码类型安全性
- 保持现有功能不变
- 采用渐进式迁移策略，降低风险

---

## 2. 迁移策略

### 渐进式迁移

分阶段进行，每个阶段验证通过后再进行下一阶段：

| 阶段 | 内容 | 目标 |
|------|------|------|
| Phase 1 | TypeScript 基础配置 | 建立编译环境 |
| Phase 2 | API 层类型定义 | 定义接口类型 |
| Phase 3 | Store 层迁移 | 状态管理类型化 |
| Phase 4 | Vue 组件迁移 | 组件类型完善 |

---

## 3. Phase 1: TypeScript 基础配置

### 3.1 安装依赖

```bash
npm install -D typescript vue-tsc
```

### 3.2 创建 TypeScript 配置

**文件**: `frontend/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ES2020", "DOM"],
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["vite/client"],
    "paths": {
      "@/*": ["./src/*"]
    },
    "baseUrl": "."
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.vue"],
  "exclude": ["node_modules", "dist"]
}
```

### 3.3 Vue 环境类型声明

**文件**: `frontend/src/vite-env.d.ts`

```typescript
/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
```

---

## 4. Phase 2: API 层类型定义

### 4.1 创建类型定义文件

**文件**: `frontend/src/types/index.ts`

```typescript
// ========== Trade Types ==========
export interface Trade {
  id?: number
  stock_code: string
  stock_name: string
  buy_date: string
  buy_price: number
  sell_date: string
  sell_price: number
  quantity: number
  profit: number
  profit_pct: number
  holding_days: number
}

export interface TradeStats {
  total_trades: number
  profitable_count: number
  win_rate: number
  total_profit: number
  total_loss: number
  net_profit: number
  avg_profit_pct: number
  avg_holding_days: number
}

export interface KLineData {
  dates: string[]
  ohlcv: number[][]
  volumes: number[]
  ma7: (number | null)[]
  ma25: (number | null)[]
  ma99: (number | null)[]
  symbol?: string
  buyDate?: string
  sellDate?: string
}

// ========== Screener Types ==========
export interface ScreenerParams {
  dropPct: number
  platformDays: number
  probeConfirm: boolean
  volRatio: number
  mvRange: string
  turnover: number
  maFilter: string
}

export interface ScreenerResult {
  code: string
  name: string
  score: number
  drop_pct: number
  volume_ratio: number
  tags?: string[]
  pattern?: string
  reason?: string
}

export interface IndexInfo {
  sh?: { value: number | string; change: number | string }
  sz?: { value: number | string; change: number | string }
  cyb?: { value: number | string; change: number | string }
}

export interface Strategy {
  id: string
  name: string
}

// ========== Crypto Types ==========
export interface Position {
  symbol: string
  qty: number
  entry_price: number
  current_price: number
  unrealized_pnl: number
  pnl_pct: number
}

export interface Signal {
  symbol: string
  price: number
  drop_pct: number
  time: string
}

export interface CryptoBotStatus {
  isRunning: boolean
  mode: 'paper' | 'live'
  positions: Position[]
  signals: Signal[]
  balance?: string | number
  last_scan?: string
}

export interface CryptoParams {
  mode: 'paper' | 'live'
  interval: string
  dropPct: number
  stopLoss: number
  maxPosPct: number
  maxPositions: number
  atrStop: boolean
  trailing: boolean
  multiTf: boolean
  platformBottom: boolean
  probeConfirm: boolean
  exitReversal: boolean
}

export interface CryptoTrade {
  id?: number
  symbol: string
  side: 'BUY' | 'SELL'
  price: number
  quantity: number
  qty?: number
  amount: number
  pnl: number
  pnl_pct?: number
  time?: string
  trade_time: string
}

// ========== Backtest Types ==========
export interface BacktestParams {
  universe: string
  days: number
  capital: number
  stopLoss: number
  maxPosPct: number
  maxPositions: number
}

export interface BacktestSummary {
  total_return: number
  annual_return: number
  win_rate: number
  max_drawdown: number
  profit_factor?: number
  sharpe_ratio?: number
  final_balance: number
}

export interface BacktestResults {
  summary: BacktestSummary
  equity: number[]
  trades: CryptoTrade[]
}

// ========== Report Types ==========
export interface TradeReport {
  tags?: string[]
  holding_days_dist?: { days: string[]; counts: number[] }
  profit_dist?: { ranges: string[]; counts: number[] }
  monthly_pnl?: Record<string, number>
  amount_trend?: { dates: string[]; amounts: number[] }
  board_preference?: Record<string, number>
  stock_top10?: { name: string; profit: number }[]
  summary?: string
}
```

### 4.2 转换 API 模块

**文件**: `frontend/src/api/index.ts`

- 重命名 `index.js` → `index.ts`
- 保持原有函数签名
- 为参数和返回值添加类型注解
- 使用 `any` 作为初始类型，逐步完善

```typescript
import axios from 'axios'
import type { Trade, KLineData, ScreenerResult, IndexInfo, Strategy, Position, Signal, CryptoBotStatus, CryptoParams, CryptoTrade, BacktestParams, BacktestResults, TradeReport } from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 交割单 API
export const uploadCSV = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const getTrades = (type: 'profitable' | 'losing' | 'all' = 'profitable') => {
  return api.get('/trades', { params: { type } })
}

export const getKline = (stockCode: string, buyDate?: string, sellDate?: string) => {
  return api.get('/kline', {
    params: { stock_code: stockCode, buy_date: buyDate, sell_date: sellDate }
  })
}

export const getReport = () => {
  return api.get('/report')
}

// ... 其他 API 函数保持原有签名
```

---

## 5. 迁移文件清单

### Phase 1 - 基础配置
| 文件 | 操作 |
|------|------|
| `frontend/package.json` | 添加 typescript, vue-tsc 依赖 |
| `frontend/tsconfig.json` | 新建 |
| `frontend/src/vite-env.d.ts` | 新建 |

### Phase 2 - API 层
| 文件 | 操作 |
|------|------|
| `frontend/src/types/index.ts` | 新建 |
| `frontend/src/api/index.js` | 重命名为 `.ts` |

---

## 6. 验证步骤

1. 安装依赖：`cd frontend && npm install`
2. 添加构建检查到 package.json：
   ```bash
   "typecheck": "vue-tsc --noEmit"
   ```
3. 运行构建：`npm run build`
4. 确认构建成功，无 TypeScript 错误

---

## 7. 后续阶段（未开始）

### Phase 3: Store 层迁移
- 转换 `stores/trades.js` → `stores/trades.ts`
- 转换 `stores/crypto.js` → `stores/crypto.ts`
- 转换 `stores/screener.js` → `stores/screener.ts`

### Phase 4: Vue 组件迁移
- 为所有 `.vue` 文件添加 `<script setup lang="ts">`
- 为 `defineProps` 添加类型定义
- 为 `defineEmits` 添加类型定义

---

## 8. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 类型不完整导致 any 滥用 | 渐进式添加，先用 any，后续完善 |
| 构建失败 | 每阶段验证后再进行下一阶段 |
| 现有功能受影响 | 保持原有函数签名不变 |
