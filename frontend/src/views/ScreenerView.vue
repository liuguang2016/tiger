<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useScreenerStore } from '../stores/screener'
import IndexBar from '../components/screener/IndexBar.vue'
import ScreenerControls from '../components/screener/ScreenerControls.vue'
import StockPool from '../components/screener/StockPool.vue'
import KLineChart from '../components/common/KLineChart.vue'

const store = useScreenerStore()

function handleParamChange({ key, value }) {
  store.params[key] = key === 'probeConfirm' ? value : Number(value)
}

function handleBtParamChange({ key, value }) {
  store.btParams[key] = Number(value)
}

async function handleSelectStock(stock) {
  await store.fetchKline(stock)
}

onMounted(() => {
  store.fetchIndex()
  store.fetchPool()
})

onUnmounted(() => {
  store.stopPolling()
  store.stopBacktestPolling()
})
</script>

<template>
  <div class="screener-view">
    <IndexBar :index-info="store.indexInfo" />

    <ScreenerControls
      :params="store.params"
      :status="store.status"
      :progress="store.progress"
      :found="store.found"
      :message="store.message"
      :bt-params="store.btParams"
      :bt-status="store.backtestStatus"
      :bt-progress="store.backtestProgress"
      :bt-results="store.backtestResults"
      @start="store.startScreening"
      @stop="store.stopPolling"
      @bt-start="store.startBacktest"
      @param-change="handleParamChange"
      @bt-param-change="handleBtParamChange"
    />

    <div class="pool-section">
      <div class="pool-layout">
        <div class="pool-list-container">
          <StockPool
            :stocks="store.pool"
            :current-stock="store.currentStock"
            @select="handleSelectStock"
            @remove="store.removeFromPool"
            @clear="store.clearPool"
          />
        </div>
        <div class="chart-panel">
          <div v-if="store.currentStock" class="chart-info">
            <span class="chart-stock-name">{{ store.currentStock.name }}</span>
            <span class="chart-stock-code">{{ store.currentStock.code }}</span>
            <span v-if="store.currentStock.drop_pct" class="chart-trade-info">
              回落 {{ store.currentStock.drop_pct.toFixed(1) }}% | 量比 {{ store.currentStock.vol_ratio?.toFixed(1) }}
            </span>
          </div>
          <KLineChart
            :data="store.klineData"
            :loading="store.klineLoading"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.screener-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.pool-section {
  margin-top: 8px;
}

.pool-layout {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 20px;
  min-height: 500px;
}

.pool-list-container {
  height: 500px;
}

.chart-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.chart-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
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

@media (max-width: 900px) {
  .pool-layout {
    grid-template-columns: 1fr;
  }
}
</style>
