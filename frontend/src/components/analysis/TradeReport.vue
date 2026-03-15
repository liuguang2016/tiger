<script setup>
import { watch, onMounted, ref } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  report: {
    type: Object,
    default: null
  }
})

const charts = ref({})

const chartRefs = {
  'chart-holding-days': null,
  'chart-profit-dist': null,
  'chart-monthly-pnl': null,
  'chart-amount-trend': null,
  'chart-board-pref': null,
  'chart-stock-top10': null
}

function initCharts() {
  Object.keys(chartRefs).forEach(id => {
    const el = document.getElementById(id)
    if (el) {
      chartRefs[id] = echarts.init(el)
      charts.value[id] = chartRefs[id]
    }
  })
}

function updateCharts() {
  if (!props.report) return

  const r = props.report

  // 持仓天数分布
  if (charts.value['chart-holding-days'] && r.holding_days_dist) {
    charts.value['chart-holding-days'].setOption({
      tooltip: { trigger: 'axis' },
      grid: { top: 20, right: 20, bottom: 30, left: 50 },
      xAxis: { type: 'category', data: r.holding_days_dist.days, axisLabel: { color: '#9ca3af' } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af' } },
      series: [{ type: 'bar', data: r.holding_days_dist.counts, itemStyle: { color: '#3b82f6' } }]
    })
  }

  // 盈亏幅度分布
  if (charts.value['chart-profit-dist'] && r.profit_dist) {
    charts.value['chart-profit-dist'].setOption({
      tooltip: { trigger: 'axis' },
      grid: { top: 20, right: 20, bottom: 30, left: 50 },
      xAxis: { type: 'category', data: r.profit_dist.ranges, axisLabel: { color: '#9ca3af', rotate: 30 } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af' } },
      series: [{ type: 'bar', data: r.profit_dist.counts, itemStyle: { color: '#8b5cf6' } }]
    })
  }

  // 月度盈亏
  if (charts.value['chart-monthly-pnl'] && r.monthly_pnl) {
    const months = Object.keys(r.monthly_pnl)
    const values = Object.values(r.monthly_pnl)
    charts.value['chart-monthly-pnl'].setOption({
      tooltip: { trigger: 'axis' },
      grid: { top: 20, right: 20, bottom: 30, left: 50 },
      xAxis: { type: 'category', data: months, axisLabel: { color: '#9ca3af' } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af' } },
      series: [{
        type: 'bar',
        data: values,
        itemStyle: {
          color: (p) => p.data >= 0 ? '#3fb950' : '#f85149'
        }
      }]
    })
  }

  // 资金规模演变
  if (charts.value['chart-amount-trend'] && r.amount_trend) {
    charts.value['chart-amount-trend'].setOption({
      tooltip: { trigger: 'axis' },
      grid: { top: 20, right: 20, bottom: 30, left: 50 },
      xAxis: { type: 'category', data: r.amount_trend.dates, axisLabel: { color: '#9ca3af' } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af' } },
      series: [{ type: 'line', data: r.amount_trend.amounts, smooth: true, itemStyle: { color: '#f59e0b' } }]
    })
  }

  // 板块偏好
  if (charts.value['chart-board-pref'] && r.board_preference) {
    const boards = Object.keys(r.board_preference)
    const profits = Object.values(r.board_preference)
    charts.value['chart-board-pref'].setOption({
      tooltip: { trigger: 'axis' },
      grid: { top: 20, right: 20, bottom: 60, left: 50 },
      xAxis: { type: 'category', data: boards, axisLabel: { color: '#9ca3af', rotate: 45 } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af' } },
      series: [{ type: 'bar', data: profits, itemStyle: { color: '#10b981' } }]
    })
  }

  // 个股盈亏 TOP10
  if (charts.value['chart-stock-top10'] && r.stock_top10) {
    const stocks = r.stock_top10.map(s => s.name)
    const profits = r.stock_top10.map(s => s.profit)
    charts.value['chart-stock-top10'].setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { top: 20, right: 20, bottom: 60, left: 80 },
      xAxis: { type: 'value', axisLabel: { color: '#9ca3af' } },
      yAxis: { type: 'category', data: stocks, axisLabel: { color: '#9ca3af' } },
      series: [{
        type: 'bar',
        data: profits,
        itemStyle: {
          color: (p) => p.data >= 0 ? '#3fb950' : '#f85149'
        }
      }]
    })
  }
}

watch(() => props.report, () => {
  setTimeout(updateCharts, 100)
}, { deep: true })

onMounted(() => {
  setTimeout(initCharts, 100)
  window.addEventListener('resize', () => {
    Object.values(charts.value).forEach(c => c?.resize())
  })
})
</script>

<template>
  <section v-if="report" class="report-section">
    <h2 class="section-title">交易风格分析报告</h2>

    <div v-if="report.tags" class="report-tags">
      <span v-for="tag in report.tags" :key="tag" class="report-tag">{{ tag }}</span>
    </div>

    <div class="report-grid">
      <div class="report-chart-card">
        <h3 class="chart-card-title">持仓天数分布</h3>
        <div id="chart-holding-days" class="report-chart"></div>
      </div>
      <div class="report-chart-card">
        <h3 class="chart-card-title">盈亏幅度分布</h3>
        <div id="chart-profit-dist" class="report-chart"></div>
      </div>
      <div class="report-chart-card">
        <h3 class="chart-card-title">月度盈亏</h3>
        <div id="chart-monthly-pnl" class="report-chart"></div>
      </div>
      <div class="report-chart-card">
        <h3 class="chart-card-title">单笔资金规模演变</h3>
        <div id="chart-amount-trend" class="report-chart"></div>
      </div>
      <div class="report-chart-card">
        <h3 class="chart-card-title">板块偏好</h3>
        <div id="chart-board-pref" class="report-chart"></div>
      </div>
      <div class="report-chart-card">
        <h3 class="chart-card-title">个股盈亏 TOP10</h3>
        <div id="chart-stock-top10" class="report-chart"></div>
      </div>
    </div>

    <div v-if="report.summary" class="report-summary">
      <h3>总结</h3>
      <p>{{ report.summary }}</p>
    </div>
  </section>
</template>

<style scoped>
.report-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
}

.report-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.report-tag {
  background: var(--accent-purple);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 16px;
}

.report-chart-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
}

.chart-card-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
  color: var(--text-secondary);
}

.report-chart {
  height: 200px;
}

.report-summary {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 20px;
  margin-top: 20px;
}

.report-summary h3 {
  font-size: 16px;
  margin-bottom: 12px;
}

.report-summary p {
  color: var(--text-secondary);
  line-height: 1.8;
}
</style>
