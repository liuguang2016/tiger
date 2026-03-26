<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useCryptoStore } from '../stores/crypto'
import ConfigPanel from '../components/crypto/ConfigPanel.vue'
import BotControls from '../components/crypto/BotControls.vue'
import SignalList from '../components/crypto/SignalList.vue'
import PositionList from '../components/crypto/PositionList.vue'
import CryptoTradeList from '../components/crypto/CryptoTradeList.vue'
import KLineChart from '../components/common/KLineChart.vue'

const store = useCryptoStore()

const activeTab = ref('signals')

const dashboard = computed(() => store.dashboard)

const listComponent = computed(() => {
  switch (activeTab.value) {
    case 'signals':
      return SignalList
    case 'positions':
      return PositionList
    case 'trades':
      return CryptoTradeList
    default:
      return SignalList
  }
})

const listProps = computed(() => {
  switch (activeTab.value) {
    case 'signals':
      return { signals: store.botStatus.signals || [], currentSymbol: store.currentSymbol }
    case 'positions':
      return { positions: store.botStatus.positions || [], currentSymbol: store.currentSymbol }
    case 'trades':
      return { trades: store.trades, currentSymbol: store.currentSymbol }
    default:
      return {}
  }
})

function formatMoney(val) {
  if (val == null || val === '--') return '--'
  return (val >= 0 ? '+' : '') + val.toFixed(2)
}

function handleParamChange({ key, value }) {
  const paramMap = {
    mode: 'mode',
    interval: 'interval',
    dropPct: 'dropPct',
    stopLoss: 'stopLoss',
    maxPosPct: 'maxPosPct',
    maxPositions: 'maxPositions',
    atrStop: 'atrStop',
    trailing: 'trailing',
    multiTf: 'multiTf',
    platformBottom: 'platformBottom',
    probeConfirm: 'probeConfirm',
    exitReversal: 'exitReversal'
  }
  const storeKey = paramMap[key]
  if (storeKey) {
    if (['atrStop', 'trailing', 'multiTf', 'platformBottom', 'probeConfirm', 'exitReversal'].includes(key)) {
      store.params[key] = value
    } else {
      store.params[key] = Number(value)
    }
  }
}

async function handleSelectSymbol(symbol) {
  await store.fetchKline(symbol)
}

async function handleSaveConfig(apiKey, apiSecret) {
  await store.saveConfig(apiKey, apiSecret)
}

onMounted(() => {
  store.fetchConfig()
  store.fetchBotStatus()
  store.fetchTrades()

  // 定时刷新状态
  const interval = setInterval(() => {
    store.fetchBotStatus()
  }, 5000)

  onUnmounted(() => {
    clearInterval(interval)
    store.stopBacktestPolling()
  })
})
</script>

<template>
  <div class="crypto-view">
    <ConfigPanel
      :config="store.config"
      :loading="store.loading"
      @save="handleSaveConfig"
    />

    <BotControls
      :params="store.params"
      :bot-status="store.botStatus"
      :loading="store.loading"
      @start="store.startBot"
      @stop="store.stopBot"
      @scan="store.manualScan"
      @param-change="handleParamChange"
    />

    <!-- 账户仪表盘 -->
    <div class="crypto-dashboard">
      <div class="dash-card">
        <span class="dash-label">USDT 余额</span>
        <span class="dash-value">{{ dashboard.balance }}</span>
      </div>
      <div class="dash-card">
        <span class="dash-label">持仓数</span>
        <span class="dash-value">{{ dashboard.posCount }}</span>
      </div>
      <div class="dash-card">
        <span class="dash-label">浮动盈亏</span>
        <span class="dash-value" :class="{ profit: dashboard.unrealized > 0, loss: dashboard.unrealized < 0 }">
          {{ formatMoney(dashboard.unrealized) }}
        </span>
      </div>
      <div class="dash-card">
        <span class="dash-label">历史胜率</span>
        <span class="dash-value">{{ dashboard.winRate }}</span>
      </div>
      <div class="dash-card">
        <span class="dash-label">累计盈亏</span>
        <span class="dash-value" :class="{ profit: dashboard.totalPnl > 0, loss: dashboard.totalPnl < 0 }">
          {{ formatMoney(dashboard.totalPnl) }}
        </span>
      </div>
      <div class="dash-card">
        <span class="dash-label">上次扫描</span>
        <span class="dash-value small">{{ dashboard.lastScan }}</span>
      </div>
    </div>

    <!-- 回测面板 -->
    <section class="backtest-section">
      <div class="backtest-header">
        <h3 class="backtest-title">策略回测</h3>
      </div>
      <div class="backtest-controls">
        <label class="param-group">
          <span class="param-label">回测天数</span>
          <select :value="store.btParams.days" @change="store.btParams.days = Number($event.target.value)">
            <option value="30">30天</option>
            <option value="90">90天</option>
            <option value="180">180天</option>
            <option value="365">1年</option>
          </select>
        </label>
        <label class="param-group">
          <span class="param-label">初始资金</span>
          <select :value="store.btParams.capital" @change="store.btParams.capital = Number($event.target.value)">
            <option value="1000">1,000 USDT</option>
            <option value="5000">5,000 USDT</option>
            <option value="10000">10,000 USDT</option>
            <option value="50000">50,000 USDT</option>
          </select>
        </label>
        <button class="btn-run-backtest" :disabled="store.backtestStatus === 'running'" @click="store.startBacktest">
          {{ store.backtestStatus === 'running' ? '回测中...' : '运行回测' }}
        </button>
      </div>
      <div v-if="store.backtestStatus === 'running'" class="progress-bar">
        <div class="progress-bar-track">
          <div class="progress-bar-fill" :style="{ width: store.backtestProgress + '%' }"></div>
        </div>
      </div>
      <div v-if="store.backtestResults" class="bt-results">
        <div class="bt-metrics-grid">
          <div class="bt-metric-card">
            <span class="bt-metric-label">总收益</span>
            <span class="bt-metric-value" :class="{ positive: store.backtestResults.summary?.total_return > 0 }">
              {{ (store.backtestResults.summary?.total_return || 0).toFixed(2) }}%
            </span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">年化收益</span>
            <span class="bt-metric-value" :class="{ positive: store.backtestResults.summary?.annual_return > 0 }">
              {{ (store.backtestResults.summary?.annual_return || 0).toFixed(2) }}%
            </span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">胜率</span>
            <span class="bt-metric-value">{{ (store.backtestResults.summary?.win_rate || 0).toFixed(1) }}%</span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">最大回撤</span>
            <span class="bt-metric-value negative">{{ (store.backtestResults.summary?.max_drawdown || 0).toFixed(2) }}%</span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">盈亏比</span>
            <span class="bt-metric-value">{{ (store.backtestResults.summary?.profit_factor || 0).toFixed(2) }}</span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">夏普比率</span>
            <span class="bt-metric-value">{{ (store.backtestResults.summary?.sharpe_ratio || 0).toFixed(2) }}</span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">交易笔数</span>
            <span class="bt-metric-value">{{ store.backtestResults.trades?.length || 0 }}</span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">最终资金</span>
            <span class="bt-metric-value">{{ (store.backtestResults.summary?.final_balance || 0).toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 主内容区 -->
    <div class="crypto-main-section">
      <div class="crypto-layout">
        <div class="crypto-list-panel">
          <div class="crypto-tabs">
            <button
              class="crypto-tab"
              :class="{ active: activeTab === 'signals' }"
              @click="activeTab = 'signals'"
            >
              信号
            </button>
            <button
              class="crypto-tab"
              :class="{ active: activeTab === 'positions' }"
              @click="activeTab = 'positions'"
            >
              持仓
            </button>
            <button
              class="crypto-tab"
              :class="{ active: activeTab === 'trades' }"
              @click="activeTab = 'trades'"
            >
              交易记录
            </button>
          </div>
          <div class="crypto-list-container">
            <component
              :is="listComponent"
              v-bind="listProps"
              @select="handleSelectSymbol"
            />
          </div>
        </div>

        <div class="crypto-chart-panel">
          <div v-if="store.currentSymbol" class="chart-info">
            <span class="chart-stock-name">{{ store.currentSymbol }}</span>
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
.crypto-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.crypto-dashboard {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
}

.dash-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: var(--shadow-sm);
}

.dash-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.dash-value {
  font-size: 20px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.dash-value.small {
  font-size: 13px;
}

.dash-value.profit {
  color: var(--accent-success);
}

.dash-value.loss {
  color: var(--accent-danger);
}

.backtest-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 24px;
  box-shadow: var(--shadow-sm);
}

.backtest-header {
  margin-bottom: 20px;
}

.backtest-title {
  font-size: 16px;
  font-weight: 600;
}

.backtest-controls {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.param-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.param-group select {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 13px;
  transition: border-color var(--transition-fast);
}

.param-group select:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.btn-run-backtest {
  background: var(--accent-primary);
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.btn-run-backtest:disabled {
  opacity: 0.6;
}

.progress-bar {
  margin-top: 16px;
}

.progress-bar-track {
  height: 6px;
  background: var(--bg-secondary);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--accent-primary);
}

.bt-results {
  margin-top: 24px;
}

.bt-metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 16px;
}

.bt-metric-card {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bt-metric-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.bt-metric-value {
  font-size: 18px;
  font-weight: 600;
  font-family: var(--font-mono);
}

.bt-metric-value.positive {
  color: var(--accent-success);
}

.bt-metric-value.negative {
  color: var(--accent-danger);
}

.crypto-main-section {
  margin-top: 0;
}

.crypto-layout {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 24px;
  min-height: 520px;
}

.crypto-list-panel {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.crypto-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.crypto-tab {
  flex: 1;
  padding: 14px 20px;
  text-align: center;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  border-bottom: 2px solid transparent;
}

.crypto-tab:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}

.crypto-tab.active {
  color: var(--accent-primary);
  border-bottom-color: var(--accent-primary);
}

.crypto-list-container {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.crypto-chart-panel {
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
  gap: 12px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.chart-stock-name {
  font-weight: 600;
  font-size: 16px;
}

@media (max-width: 1024px) {
  .crypto-layout {
    grid-template-columns: 1fr;
  }
}
</style>
