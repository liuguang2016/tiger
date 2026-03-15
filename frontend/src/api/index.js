import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 交割单 API
export const uploadCSV = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const getTrades = (type = 'profitable') => {
  return api.get('/trades', { params: { type } })
}

export const getKline = (stockCode, buyDate, sellDate) => {
  return api.get('/kline', {
    params: { stock_code: stockCode, buy_date: buyDate, sell_date: sellDate }
  })
}

export const getReport = () => {
  return api.get('/report')
}

// 选股 API
export const runScreener = (params) => {
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

export const removeFromPool = (stockCode) => {
  return api.delete(`/screener/pool/${stockCode}`)
}

export const clearPool = () => {
  return api.delete('/screener/pool')
}

// 数字货币 API
export const getCryptoConfig = () => {
  return api.get('/crypto/config')
}

export const saveCryptoConfig = (apiKey, apiSecret, params) => {
  return api.post('/crypto/config', { api_key: apiKey, api_secret: apiSecret, params })
}

export const startCryptoBot = (params) => {
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

export const getCryptoTrades = (limit = 100, symbol) => {
  return api.get('/crypto/trades', { params: { limit, symbol } })
}

export const getCryptoKline = (symbol, interval = '4h', limit = 200) => {
  return api.get('/crypto/kline', { params: { symbol, interval, limit } })
}

// 回测 API
export const runCryptoBacktest = (params) => {
  return api.post('/crypto/backtest/run', params)
}

export const getCryptoBacktestStatus = () => {
  return api.get('/crypto/backtest/status')
}

export const getCryptoBacktestHistory = (limit = 20) => {
  return api.get('/crypto/backtest/history', { params: { limit } })
}

export const runStockBacktest = (params) => {
  return api.post('/stock/backtest/run', params)
}

export const getStockBacktestStatus = () => {
  return api.get('/stock/backtest/status')
}

export default api
