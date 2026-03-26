<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['click'])

const chartRef = ref(null)
let chart = null

const chartData = computed(() => {
  if (!props.data) return null
  const { dates, ohlcv, volumes, ma7, ma25, ma99 } = props.data
  return { dates, ohlcv, volumes, ma7, ma25, ma99 }
})

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  chart.on('click', (params) => {
    emit('click', params)
  })
}

function updateChart() {
  if (!chart || !chartData.value) return

  const { dates, ohlcv, volumes, ma7, ma25, ma99 } = chartData.value

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' }
    },
    grid: [
      { left: 60, right: 20, top: 20, height: '60%' },
      { left: 60, right: 20, top: '75%', height: '15%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0,
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af', fontSize: 10 },
        splitLine: { show: false }
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { show: false },
        splitLine: { show: false }
      }
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        scale: true,
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1f2937' } }
      },
      {
        type: 'value',
        gridIndex: 1,
        scale: true,
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af', fontSize: 10 },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlcv,
        itemStyle: {
          color: '#3fb950',
          color0: '#f85149',
          borderColor: '#3fb950',
          borderColor0: '#f85149'
        }
      },
      { name: 'MA7', type: 'line', data: ma7, smooth: true, lineStyle: { width: 1, color: '#f59e0b' }, symbol: 'none' },
      { name: 'MA25', type: 'line', data: ma25, smooth: true, lineStyle: { width: 1, color: '#8b5cf6' }, symbol: 'none' },
      { name: 'MA99', type: 'line', data: ma99, smooth: true, lineStyle: { width: 1, color: '#3b82f6' }, symbol: 'none' },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: (params) => {
            const idx = params.dataIndex
            if (ohlcv[idx] && ohlcv[idx][1] >= ohlcv[idx][0]) {
              return 'rgba(63, 185, 80, 0.5)'
            }
            return 'rgba(248, 81, 73, 0.5)'
          }
        }
      }
    ],
    markLine: {
      silent: true,
      lineStyle: { type: 'dashed', color: '#6b7280' },
      label: { color: '#9ca3af', fontSize: 10 },
      data: []
    }
  }

  // 添加买卖标记线
  if (props.data.buyDate || props.data.sellDate) {
    const { buyDate, sellDate } = props.data
    const idxMap = {}
    dates.forEach((d, i) => { idxMap[d] = i })

    if (buyDate && idxMap[buyDate] !== undefined) {
      option.series[0].markLine = {
        ...option.series[0].markLine,
        data: [{ xAxis: idxMap[buyDate], label: { formatter: '买入' } }]
      }
    }
  }

  chart.setOption(option)
}

watch(() => props.data, () => {
  updateChart()
}, { deep: true })

watch(() => props.loading, (val) => {
  if (!val && chart) {
    setTimeout(updateChart, 100)
  }
})

onMounted(() => {
  initChart()
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
})
</script>

<template>
  <div class="kline-chart-wrapper">
    <div v-if="loading" class="chart-loading">
      <div class="spinner"></div>
      <p>正在加载 K 线数据...</p>
    </div>
    <div v-else-if="!data" class="chart-placeholder">
      <p>{{ title || '请选择一项查看 K 线图' }}</p>
    </div>
    <div ref="chartRef" class="kline-chart"></div>
  </div>
</template>

<style scoped>
.kline-chart-wrapper {
  width: 100%;
  height: 100%;
  min-height: 400px;
  position: relative;
  background: var(--bg-card);
  border-radius: var(--radius-md);
}

.kline-chart {
  width: 100%;
  height: 100%;
}

.chart-placeholder,
.chart-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 12px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
