import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../api'

export const useCryptoStore = defineStore('crypto', () => {
  const config = ref(null)
  const botStatus = ref({
    isRunning: false,
    mode: 'paper',
    positions: [],
    signals: []
  })
  const trades = ref([])
  const tradeStats = ref(null)
  const currentSymbol = ref(null)
  const klineData = ref(null)
  const klineLoading = ref(false)
  const loading = ref(false)

  // 回测状态
  const backtestStatus = ref('idle')
  const backtestProgress = ref(0)
  const backtestTotal = ref(0)
  const backtestResults = ref(null)
  const backtestPolling = ref(null)

  const params = ref({
    mode: 'paper',
    interval: '4h',
    dropPct: 15,
    stopLoss: 5,
    maxPosPct: 10,
    maxPositions: 5,
    atrStop: true,
    trailing: true,
    multiTf: true,
    platformBottom: true,
    probeConfirm: true,
    platformCandles: 20,
    exitReversal: true
  })

  const btParams = ref({
    days: 180,
    capital: 10000
  })

  // 仪表盘数据
  const dashboard = computed(() => {
    const positions = botStatus.value.positions || []
    const unrealized = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0)
    return {
      balance: botStatus.value.balance || '--',
      posCount: `${positions.length} / params.value.maxPositions`,
      unrealized,
      winRate: tradeStats.value?.win_rate || '--',
      totalPnl: tradeStats.value?.total_pnl || '--',
      lastScan: botStatus.value.last_scan || '--'
    }
  })

  async function fetchConfig() {
    try {
      const res = await api.getCryptoConfig()
      if (res.data.success) {
        config.value = res.data.config
      }
    } catch (e) {
      console.error('Failed to fetch config:', e)
    }
  }

  async function saveConfig(apiKey, apiSecret) {
    loading.value = true
    try {
      const res = await api.saveCryptoConfig(apiKey, apiSecret, params.value)
      if (res.data.success) {
        await fetchConfig()
        return { connected: res.data.connected, auth_ok: res.data.auth_ok }
      }
      throw new Error(res.data.message)
    } finally {
      loading.value = false
    }
  }

  async function fetchBotStatus() {
    try {
      const res = await api.getCryptoBotStatus()
      if (res.data.success) {
        botStatus.value = res.data
      }
    } catch (e) {
      console.error('Failed to fetch bot status:', e)
    }
  }

  async function startBot() {
    try {
      const res = await api.startCryptoBot(params.value)
      if (res.data.success) {
        await fetchBotStatus()
      }
    } catch (e) {
      console.error('Failed to start bot:', e)
    }
  }

  async function stopBot() {
    try {
      await api.stopCryptoBot()
      await fetchBotStatus()
    } catch (e) {
      console.error('Failed to stop bot:', e)
    }
  }

  async function manualScan() {
    try {
      const res = await api.manualScan()
      if (res.data.success) {
        botStatus.value.signals = res.data.signals || []
        await fetchBotStatus()
      }
    } catch (e) {
      console.error('Failed to manual scan:', e)
    }
  }

  async function fetchTrades() {
    try {
      const res = await api.getCryptoTrades()
      if (res.data.success) {
        trades.value = res.data.trades || []
        tradeStats.value = res.data.stats
      }
    } catch (e) {
      console.error('Failed to fetch trades:', e)
    }
  }

  async function fetchKline(symbol, interval = '4h') {
    currentSymbol.value = symbol
    klineLoading.value = true
    try {
      const res = await api.getCryptoKline(symbol, interval)
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
      await api.runCryptoBacktest(btParams.value)
      startBacktestPolling()
    } catch (e) {
      backtestStatus.value = 'error'
    }
  }

  function startBacktestPolling() {
    backtestPolling.value = setInterval(async () => {
      try {
        const res = await api.getCryptoBacktestStatus()
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
    currentSymbol.value = null
    klineData.value = null
  }

  return {
    config,
    botStatus,
    trades,
    tradeStats,
    currentSymbol,
    klineData,
    klineLoading,
    loading,
    params,
    btParams,
    backtestStatus,
    backtestProgress,
    backtestTotal,
    backtestResults,
    dashboard,
    fetchConfig,
    saveConfig,
    fetchBotStatus,
    startBot,
    stopBot,
    manualScan,
    fetchTrades,
    fetchKline,
    startBacktest,
    stopBacktestPolling,
    clearKline
  }
})
