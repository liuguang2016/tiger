<script setup>
import { computed, onMounted } from 'vue'
import { useTradesStore } from '../stores/trades'
import UploadZone from '../components/analysis/UploadZone.vue'
import TradeList from '../components/analysis/TradeList.vue'
import TradeReport from '../components/analysis/TradeReport.vue'
import KLineChart from '../components/common/KLineChart.vue'
import StatCard from '../components/common/StatCard.vue'

const store = useTradesStore()

const stats = computed(() => store.stats)
const hasData = computed(() => store.hasData)

function formatMoney(val) {
  if (val == null) return '-'
  return (val >= 0 ? '+' : '') + val.toFixed(2)
}

function formatPct(val) {
  if (val == null) return '-'
  return (val >= 0 ? '+' : '') + (val * 100).toFixed(2) + '%'
}

async function handleUpload(file) {
  await store.uploadFile(file)
}

async function handleGenerateReport() {
  await store.generateReport()
}

async function handleTypeChange(type) {
  await store.fetchTrades(type)
}

async function handleSortChange(sort) {
  store.setSort(sort)
}

async function handleSelectTrade(trade) {
  await store.fetchKline(trade)
}

onMounted(() => {
  if (store.hasData) {
    store.fetchTrades()
  }
})
</script>

<template>
  <div class="analysis-view">
    <UploadZone
      :uploading="store.uploading"
      :has-data="hasData"
      @upload="handleUpload"
      @generate-report="handleGenerateReport"
    />

    <TradeReport v-if="store.report" :report="store.report" />

    <section v-if="hasData" class="stats-section">
      <h2 class="section-title">交易统计概览</h2>
      <div class="stats-grid">
        <StatCard label="总交易笔数" :value="stats?.total_trades || 0" />
        <StatCard label="盈利笔数" :value="stats?.profitable_count || 0" variant="profit" />
        <StatCard label="胜率" :value="formatPct(stats?.win_rate)" />
        <StatCard label="总盈利" :value="formatMoney(stats?.total_profit)" variant="profit" />
        <StatCard label="总亏损" :value="formatMoney(stats?.total_loss)" variant="loss" />
        <StatCard label="净盈利" :value="formatMoney(stats?.net_profit)" :variant="stats?.net_profit > 0 ? 'profit' : ''" />
        <StatCard label="平均盈利比例" :value="formatPct(stats?.avg_profit_pct)" />
        <StatCard label="平均持仓天数" :value="(stats?.avg_holding_days || 0).toFixed(1) + ' 天'" />
      </div>
    </section>

    <section v-if="hasData" class="content-section">
      <div class="content-layout">
        <div class="trade-list-container">
          <TradeList
            :trades="store.sortedTrades"
            :current-trade="store.currentTrade"
            :type="store.currentType"
            @select="handleSelectTrade"
            @type-change="handleTypeChange"
            @sort-change="handleSortChange"
          />
        </div>
        <div class="chart-panel">
          <div v-if="store.currentTrade" class="chart-info">
            <span class="chart-stock-name">{{ store.currentTrade.stock_name }}</span>
            <span class="chart-stock-code">{{ store.currentTrade.stock_code }}</span>
            <span class="chart-trade-info">
              {{ store.currentTrade.buy_date }} ~ {{ store.currentTrade.sell_date }}
            </span>
          </div>
          <KLineChart
            :data="store.klineData"
            :loading="store.klineLoading"
            @click="() => {}"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.analysis-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.content-layout {
  display: grid;
  grid-template-columns: 400px 1fr;
  gap: 24px;
  min-height: 520px;
}

.trade-list-container {
  height: 520px;
}

.chart-panel {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 20px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-sm);
}

.chart-info {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.chart-stock-name {
  font-weight: 600;
  font-size: 16px;
}

.chart-stock-code {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 13px;
}

.chart-trade-info {
  color: var(--text-secondary);
  font-size: 13px;
}

@media (max-width: 1024px) {
  .content-layout {
    grid-template-columns: 1fr;
  }

  .trade-list-container {
    height: 400px;
  }
}
</style>
