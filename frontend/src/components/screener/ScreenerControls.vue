<script setup>
import { computed } from 'vue'

const props = defineProps({
  params: {
    type: Object,
    required: true
  },
  status: {
    type: String,
    default: 'idle'
  },
  progress: {
    type: Number,
    default: 0
  },
  found: {
    type: Number,
    default: 0
  },
  message: {
    type: String,
    default: ''
  },
  btParams: {
    type: Object,
    required: true
  },
  btStatus: {
    type: String,
    default: 'idle'
  },
  btProgress: {
    type: Number,
    default: 0
  },
  btResults: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['start', 'stop', 'bt-start', 'bt-param-change', 'param-change'])

const isRunning = computed(() => props.status === 'running')
const isBtRunning = computed(() => props.btStatus === 'running')

function updateParam(key, value) {
  emit('param-change', { key, value })
}

function updateBtParam(key, value) {
  emit('bt-param-change', { key, value })
}
</script>

<template>
  <div class="screener-controls">
    <section class="screening-section">
      <h3 class="section-title">筛选参数</h3>
      <div class="params-grid">
        <label class="param-group">
          <span class="param-label">回落幅度</span>
          <select :value="params.dropPct" @change="updateParam('dropPct', $event.target.value)">
            <option value="10">≥10%</option>
            <option value="15">≥15%</option>
            <option value="20">≥20%</option>
            <option value="25">≥25%</option>
          </select>
        </label>
        <label class="param-group">
          <span class="param-label">底部天数</span>
          <select :value="params.platformDays" @change="updateParam('platformDays', $event.target.value)">
            <option value="1">≥1天</option>
            <option value="2">≥2天</option>
            <option value="3">≥3天</option>
          </select>
        </label>
        <label class="param-group param-toggle">
          <input type="checkbox" :checked="params.probeConfirm" @change="updateParam('probeConfirm', $event.target.checked)">
          <span class="param-label">下探确认</span>
        </label>
        <label class="param-group">
          <span class="param-label">量比阈值</span>
          <select :value="params.volRatio" @change="updateParam('volRatio', $event.target.value)">
            <option value="0.8">≥0.8</option>
            <option value="1.0">≥1.0</option>
            <option value="1.2">≥1.2</option>
            <option value="1.5">≥1.5</option>
          </select>
        </label>
        <label class="param-group">
          <span class="param-label">市值范围</span>
          <select :value="params.mvRange" @change="updateParam('mvRange', $event.target.value)">
            <option value="all">不限(&lt;5000亿)</option>
            <option value="small">小盘(20-100亿)</option>
            <option value="mid">中盘(100-500亿)</option>
          </select>
        </label>
        <label class="param-group">
          <span class="param-label">换手率</span>
          <select :value="params.turnover" @change="updateParam('turnover', $event.target.value)">
            <option value="1">≥1%</option>
            <option value="2">≥2%</option>
            <option value="3">≥3%</option>
          </select>
        </label>
        <label class="param-group">
          <span class="param-label">均线条件</span>
          <select :value="params.maFilter" @change="updateParam('maFilter', $event.target.value)">
            <option value="none">不限</option>
            <option value="ma5_turn">MA5拐头</option>
            <option value="golden_cross">金叉</option>
          </select>
        </label>
      </div>
      <div class="action-row">
        <button class="btn-screen" :disabled="isRunning" @click="emit('start')">
          {{ isRunning ? '筛选中...' : '开始筛选' }}
        </button>
        <button v-if="isRunning" class="btn-stop" @click="emit('stop')">停止</button>
      </div>
      <div v-if="isRunning" class="progress-bar">
        <div class="progress-bar-track">
          <div class="progress-bar-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <span class="progress-text">{{ message }} ({{ found }} 只)</span>
      </div>
    </section>

    <section class="backtest-section">
      <h3 class="section-title">策略回测</h3>
      <div class="params-grid">
        <label class="param-group">
          <span class="param-label">股票范围</span>
          <select :value="btParams.universe" @change="updateBtParam('universe', $event.target.value)">
            <option value="pool">交易池股票</option>
            <option value="all">全A股(成交额前800)</option>
          </select>
        </label>
        <label class="param-group">
          <span class="param-label">回测天数</span>
          <select :value="btParams.days" @change="updateBtParam('days', $event.target.value)">
            <option value="90">90天</option>
            <option value="180">180天</option>
            <option value="365">1年</option>
          </select>
        </label>
        <label class="param-group">
          <span class="param-label">初始资金</span>
          <select :value="btParams.capital" @change="updateBtParam('capital', $event.target.value)">
            <option value="100000">10万</option>
            <option value="500000">50万</option>
            <option value="1000000">100万</option>
          </select>
        </label>
        <label class="param-group">
          <span class="param-label">止损</span>
          <select :value="btParams.stopLoss" @change="updateBtParam('stopLoss', $event.target.value)">
            <option value="3">-3%</option>
            <option value="5">-5%</option>
            <option value="8">-8%</option>
          </select>
        </label>
        <label class="param-group">
          <span class="param-label">单仓</span>
          <select :value="btParams.maxPosPct" @change="updateBtParam('maxPosPct', $event.target.value)">
            <option value="5">5%</option>
            <option value="10">10%</option>
            <option value="15">15%</option>
          </select>
        </label>
        <label class="param-group">
          <span class="param-label">持仓数</span>
          <select :value="btParams.maxPositions" @change="updateBtParam('maxPositions', $event.target.value)">
            <option value="3">3只</option>
            <option value="5">5只</option>
            <option value="8">8只</option>
          </select>
        </label>
      </div>
      <div class="action-row">
        <button class="btn-run-backtest" :disabled="isBtRunning" @click="emit('bt-start')">
          {{ isBtRunning ? '回测中...' : '运行回测' }}
        </button>
      </div>
      <div v-if="isBtRunning" class="progress-bar">
        <div class="progress-bar-track">
          <div class="progress-bar-fill" :style="{ width: btProgress + '%' }"></div>
        </div>
        <span class="progress-text">回测进行中...</span>
      </div>

      <div v-if="btResults" class="bt-results">
        <div class="bt-metrics-grid">
          <div class="bt-metric-card">
            <span class="bt-metric-label">总收益</span>
            <span class="bt-metric-value" :class="{ positive: btResults.summary?.total_return > 0 }">
              {{ (btResults.summary?.total_return || 0).toFixed(2) }}%
            </span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">年化收益</span>
            <span class="bt-metric-value" :class="{ positive: btResults.summary?.annual_return > 0 }">
              {{ (btResults.summary?.annual_return || 0).toFixed(2) }}%
            </span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">胜率</span>
            <span class="bt-metric-value">{{ (btResults.summary?.win_rate || 0).toFixed(1) }}%</span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">最大回撤</span>
            <span class="bt-metric-value negative">{{ (btResults.summary?.max_drawdown || 0).toFixed(2) }}%</span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">交易笔数</span>
            <span class="bt-metric-value">{{ btResults.trades?.length || 0 }}</span>
          </div>
          <div class="bt-metric-card">
            <span class="bt-metric-label">最终资金</span>
            <span class="bt-metric-value">{{ (btResults.summary?.final_balance || 0).toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.screener-controls {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-bottom: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
}

.params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.param-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.param-group select {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 8px;
  font-size: 13px;
}

.param-toggle {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.param-toggle input {
  width: 16px;
  height: 16px;
  accent-color: var(--accent-primary);
}

.action-row {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.btn-screen,
.btn-run-backtest {
  background: var(--accent-primary);
  color: white;
  padding: 10px 24px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.btn-screen:hover:not(:disabled),
.btn-run-backtest:hover:not(:disabled) {
  background: #4a9eff;
}

.btn-screen:disabled,
.btn-run-backtest:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-stop {
  background: var(--accent-danger);
  color: white;
  padding: 10px 24px;
  border-radius: var(--radius-md);
  font-size: 14px;
}

.progress-bar {
  margin-top: 16px;
}

.progress-bar-track {
  height: 8px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--accent-primary);
  transition: width 0.3s ease;
}

.progress-text {
  display: block;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.bt-results {
  margin-top: 20px;
}

.bt-metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
}

.bt-metric-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bt-metric-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.bt-metric-value {
  font-size: 16px;
  font-weight: 600;
  font-family: var(--font-mono);
}

.bt-metric-value.positive {
  color: var(--accent-success);
}

.bt-metric-value.negative {
  color: var(--accent-danger);
}
</style>
