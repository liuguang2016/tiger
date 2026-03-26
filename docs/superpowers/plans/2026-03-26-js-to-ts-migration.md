# Frontend JavaScript to TypeScript Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert frontend from JavaScript to TypeScript using progressive migration strategy, starting with API layer.

**Architecture:** Phased approach - each phase validates before moving to next. Phase 1 establishes TypeScript tooling, Phase 2 types the API layer.

**Tech Stack:** TypeScript 5.4+, vue-tsc, Vite

---

## Phase 1: TypeScript Foundation

### Task 1: Install TypeScript Dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Add TypeScript dependencies**

Modify `frontend/package.json` devDependencies:
```json
"devDependencies": {
  "@vitejs/plugin-vue": "^5.0.4",
  "typescript": "^5.4.0",
  "vue-tsc": "^2.0.0",
  "vite": "^5.2.0"
}
```

- [ ] **Step 2: Install dependencies**

Run: `cd frontend && npm install`
Expected: npm installs typescript and vue-tsc

- [ ] **Step 3: Add typecheck script to package.json**

Modify `frontend/package.json` scripts section:
```json
"scripts": {
  "dev": "vite",
  "build": "vite build",
  "preview": "vite preview",
  "typecheck": "vue-tsc --noEmit"
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add TypeScript dependencies"
```

---

### Task 2: Create tsconfig.json

**Files:**
- Create: `frontend/tsconfig.json`

- [ ] **Step 1: Create TypeScript configuration**

Create `frontend/tsconfig.json`:
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
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.tsx", "src/**/*.vue"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/tsconfig.json
git commit -m "feat: add TypeScript configuration"
```

---

### Task 3: Create Vue Environment Type Declarations

**Files:**
- Create: `frontend/src/vite-env.d.ts`

- [ ] **Step 1: Create vite-env.d.ts**

Create `frontend/src/vite-env.d.ts`:
```typescript
/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/vite-env.d.ts
git commit -m "feat: add Vue environment type declarations"
```

---

## Phase 2: API Layer Type Definitions

### Task 4: Create Types Definition File

**Files:**
- Create: `frontend/src/types/index.ts`

- [ ] **Step 1: Create types/index.ts with all type definitions**

Create `frontend/src/types/index.ts`:
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

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add TypeScript type definitions for API layer"
```

---

### Task 5: Convert API Module to TypeScript

**Files:**
- Create: `frontend/src/api/index.ts` (replace `frontend/src/api/index.js`)

- [ ] **Step 1: Read existing API file to understand all functions**

Already read: `frontend/src/api/index.js`

- [ ] **Step 2: Create TypeScript version of API module**

Create `frontend/src/api/index.ts`:
```typescript
import axios, { AxiosInstance } from 'axios'
import type {
  Trade,
  KLineData,
  ScreenerParams,
  ScreenerResult,
  IndexInfo,
  Strategy,
  CryptoBotStatus,
  CryptoParams,
  CryptoTrade,
  BacktestParams,
  BacktestResults,
  TradeReport
} from '@/types'

const api: AxiosInstance = axios.create({
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

// 选股 API
export const runScreener = (params: ScreenerParams) => {
  return api.post('/screener/run', params)
}

export const getScreenerStatus = () => {
  return api.get('/screener/status')
}

export const getIndex = () => {
  return api.get('/screener/index')
}

export const getPool = () => {
  return api.get('/screener/pool')
}

export const removeFromPool = (stockCode: string) => {
  return api.delete(`/screener/pool/${stockCode}`)
}

export const clearPool = () => {
  return api.delete('/screener/pool')
}

export const listStrategies = () => {
  return api.get('/screener/strategies')
}

export const runStrategy = (strategyId: string) => {
  return api.post('/screener/strategy/run', { strategy_id: strategyId })
}

// 数字货币 API
export const getCryptoConfig = () => {
  return api.get('/crypto/config')
}

export const saveCryptoConfig = (apiKey: string, apiSecret: string, params: CryptoParams) => {
  return api.post('/crypto/config', { api_key: apiKey, api_secret: apiSecret, params })
}

export const startCryptoBot = (params: CryptoParams) => {
  return api.post('/crypto/bot/start', params)
}

export const stopCryptoBot = () => {
  return api.post('/crypto/bot/stop')
}

export const getCryptoBotStatus = () => {
  return api.get('/crypto/bot/status')
}

export const manualScan = () => {
  return api.post('/crypto/bot/scan')
}

export const getCryptoTrades = (limit = 100, symbol?: string) => {
  return api.get('/crypto/trades', { params: { limit, symbol } })
}

export const getCryptoKline = (symbol: string, interval = '4h', limit = 200) => {
  return api.get('/crypto/kline', { params: { symbol, interval, limit } })
}

// 回测 API
export const runCryptoBacktest = (params: BacktestParams) => {
  return api.post('/crypto/backtest/run', params)
}

export const getCryptoBacktestStatus = () => {
  return api.get('/crypto/backtest/status')
}

export const getCryptoBacktestHistory = (limit = 20) => {
  return api.get('/crypto/backtest/history', { params: { limit } })
}

export const runStockBacktest = (params: BacktestParams) => {
  return api.post('/stock/backtest/run', params)
}

export const getStockBacktestStatus = () => {
  return api.get('/stock/backtest/status')
}

export default api
```

- [ ] **Step 3: Delete old JavaScript file**

Run: `rm frontend/src/api/index.js`

- [ ] **Step 4: Verify build works**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/index.ts
git rm frontend/src/api/index.js
git commit -m "feat: convert API module to TypeScript"
```

---

## Verification

- [ ] **Run full type check**

Run: `cd frontend && npm run typecheck`
Expected: No TypeScript errors (or only legitimate warnings)

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Install TypeScript deps | package.json |
| 2 | Create tsconfig.json | tsconfig.json |
| 3 | Create Vue type declarations | src/vite-env.d.ts |
| 4 | Create type definitions | src/types/index.ts |
| 5 | Convert API module | src/api/index.ts → src/api/index.js deleted |

**Total: 5 tasks**

**Future Phases (not in this plan):**
- Phase 3: Store layer migration (3 Pinia stores)
- Phase 4: Vue component migration (17 components)
