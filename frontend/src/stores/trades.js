import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../api'

export const useTradesStore = defineStore('trades', () => {
  const trades = ref([])
  const stats = ref(null)
  const loading = ref(false)
  const uploading = ref(false)
  const currentTrade = ref(null)
  const klineData = ref(null)
  const klineLoading = ref(false)
  const report = ref(null)
  const hasData = ref(false)
  const currentType = ref('profitable')
  const sortBy = ref('sell_date_desc')

  const sortedTrades = computed(() => {
    const t = [...trades.value]
    const [field, order] = sortBy.value.split('_')
    const desc = order === 'desc'

    t.sort((a, b) => {
      let valA = a[field]
      let valB = b[field]
      if (field === 'sell_date' || field === 'buy_date') {
        valA = new Date(valA)
        valB = new Date(valB)
      }
      if (valA < valB) return desc ? 1 : -1
      if (valA > valB) return desc ? -1 : 1
      return 0
    })
    return t
  })

  async function uploadFile(file) {
    uploading.value = true
    try {
      const res = await api.uploadCSV(file)
      if (res.data.success) {
        trades.value = res.data.trades || []
        stats.value = res.data.stats
        hasData.value = true
        return res.data
      }
      throw new Error(res.data.message)
    } finally {
      uploading.value = false
    }
  }

  async function fetchTrades(type = 'profitable') {
    currentType.value = type
    loading.value = true
    try {
      const res = await api.getTrades(type)
      if (res.data.success) {
        trades.value = res.data.trades || []
        stats.value = res.data.stats
        hasData.value = true
      }
    } finally {
      loading.value = false
    }
  }

  async function fetchKline(trade) {
    currentTrade.value = trade
    klineLoading.value = true
    try {
      const res = await api.getKline(
        trade.stock_code,
        trade.buy_date,
        trade.sell_date
      )
      if (res.data.success) {
        klineData.value = {
          ...res.data,
          buyDate: trade.buy_date,
          sellDate: trade.sell_date
        }
      }
    } finally {
      klineLoading.value = false
    }
  }

  async function generateReport() {
    try {
      const res = await api.getReport()
      if (res.data.success) {
        report.value = res.data.report
      }
    } catch (e) {
      console.error('Failed to generate report:', e)
    }
  }

  function setSort(sort) {
    sortBy.value = sort
  }

  function clearKline() {
    currentTrade.value = null
    klineData.value = null
  }

  return {
    trades,
    stats,
    loading,
    uploading,
    currentTrade,
    klineData,
    klineLoading,
    report,
    hasData,
    currentType,
    sortBy,
    sortedTrades,
    uploadFile,
    fetchTrades,
    fetchKline,
    generateReport,
    setSort,
    clearKline
  }
})
