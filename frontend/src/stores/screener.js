import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../api'

export const useScreenerStore = defineStore('screener', () => {
  const status = ref('idle')
  const progress = ref(0)
  const total = ref(0)
  const found = ref(0)
  const message = ref('')
  const results = ref([])
  const pool = ref([])
  const indexInfo = ref({})
  const currentStock = ref(null)
  const klineData = ref(null)
  const klineLoading = ref(false)
  const polling = ref(null)

  // 回测状态
  const backtestStatus = ref('idle')
  const backtestProgress = ref(0)
  const backtestTotal = ref(0)
  const backtestResults = ref(null)
  const backtestPolling = ref(null)

  const params = ref({
    dropPct: 15,
    platformDays: 1,
    probeConfirm: true,
    volRatio: 1.2,
    mvRange: 'all',
    turnover: 1,
    maFilter: 'none'
  })

  const btParams = ref({
    universe: 'pool',
    days: 180,
    capital: 100000,
    stopLoss: 5,
    maxPosPct: 10,
    maxPositions: 5
  })

  async function startScreening() {
    status.value = 'running'
    progress.value = 0
    found.value = 0
    message.value = '正在启动筛选...'

    try {
      await api.runScreener(params.value)
      startPolling()
    } catch (e) {
      status.value = 'error'
      message.value = e.message
    }
  }

  function startPolling() {
    polling.value = setInterval(async () => {
      try {
        const res = await api.getScreenerStatus()
        const data = res.data
        status.value = data.status
        progress.value = data.progress
        total.value = data.total
        found.value = data.found
        message.value = data.message
        indexInfo.value = data.index_info || {}

        if (data.status === 'done') {
          results.value = data.results || []
          pool.value = data.results || []
          stopPolling()
        } else if (data.status === 'error') {
          stopPolling()
        }
      } catch (e) {
        console.error('Polling error:', e)
      }
    }, 2000)
  }

  function stopPolling() {
    if (polling.value) {
      clearInterval(polling.value)
      polling.value = null
    }
  }

  async function fetchPool() {
    try {
      const res = await api.getPool()
      if (res.data.success) {
        pool.value = res.data.stocks || []
      }
    } catch (e) {
      console.error('Failed to fetch pool:', e)
    }
  }

  async function removeFromPool(stockCode) {
    try {
      await api.removeFromPool(stockCode)
      pool.value = pool.value.filter(s => s.code !== stockCode)
    } catch (e) {
      console.error('Failed to remove from pool:', e)
    }
  }

  async function clearPool() {
    try {
      await api.clearPool()
      pool.value = []
    } catch (e) {
      console.error('Failed to clear pool:', e)
    }
  }

  async function fetchIndex() {
    try {
      const res = await api.getIndex()
      if (res.data.success) {
        indexInfo.value = res.data.index || {}
      }
    } catch (e) {
      console.error('Failed to fetch index:', e)
    }
  }

  async function fetchKline(stock) {
    currentStock.value = stock
    klineLoading.value = true
    try {
      const res = await api.getKline(stock.code)
      if (res.data.success) {
        klineData.value = res.data
      }
    } finally {
      klineLoading.value = false
    }
  }

  async function startBacktest() {
    backtestStatus.value = 'running'
    backtestProgress.value = 0
    backtestResults.value = null

    try {
      await api.runStockBacktest(btParams.value)
      startBacktestPolling()
    } catch (e) {
      backtestStatus.value = 'error'
    }
  }

  function startBacktestPolling() {
    backtestPolling.value = setInterval(async () => {
      try {
        const res = await api.getStockBacktestStatus()
        const data = res.data
        backtestStatus.value = data.status
        backtestProgress.value = data.progress
        backtestTotal.value = data.total

        if (data.status === 'done') {
          backtestResults.value = {
            summary: data.summary,
            equity: data.equity,
            trades: data.trades
          }
          stopBacktestPolling()
        } else if (data.status === 'error') {
          stopBacktestPolling()
        }
      } catch (e) {
        console.error('Backtest polling error:', e)
      }
    }, 2000)
  }

  function stopBacktestPolling() {
    if (backtestPolling.value) {
      clearInterval(backtestPolling.value)
      backtestPolling.value = null
    }
  }

  function clearKline() {
    currentStock.value = null
    klineData.value = null
  }

  return {
    status,
    progress,
    total,
    found,
    message,
    results,
    pool,
    indexInfo,
    currentStock,
    klineData,
    klineLoading,
    params,
    btParams,
    backtestStatus,
    backtestProgress,
    backtestTotal,
    backtestResults,
    startScreening,
    fetchPool,
    removeFromPool,
    clearPool,
    fetchIndex,
    fetchKline,
    clearKline,
    startBacktest,
    stopPolling,
    stopBacktestPolling
  }
})
