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
