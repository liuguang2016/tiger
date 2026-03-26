<script setup>
import { computed } from 'vue'

const props = defineProps({
  params: {
    type: Object,
    required: true
  },
  botStatus: {
    type: Object,
    default: () => ({})
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['start', 'stop', 'scan', 'param-change'])

const isRunning = computed(() => props.botStatus.isRunning)

function updateParam(key, value) {
  emit('param-change', { key, value })
}
</script>

<template>
  <div class="crypto-control-bar">
    <div class="crypto-params">
      <label class="param-group">
        <span class="param-label">模式</span>
        <select :value="params.mode" @change="updateParam('mode', $event.target.value)">
          <option value="paper">模拟盘</option>
          <option value="live">实盘</option>
        </select>
      </label>
      <label class="param-group">
        <span class="param-label">K线周期</span>
        <select :value="params.interval" @change="updateParam('interval', $event.target.value)">
          <option value="5m">5分钟</option>
          <option value="15m">15分钟</option>
          <option value="30m">30分钟</option>
          <option value="1h">1小时</option>
          <option value="4h">4小时</option>
          <option value="1d">1天</option>
        </select>
      </label>
      <label class="param-group">
        <span class="param-label">跌幅</span>
        <select :value="params.dropPct" @change="updateParam('dropPct', $event.target.value)">
          <option value="10">≥10%</option>
          <option value="15">≥15%</option>
          <option value="20">≥20%</option>
          <option value="25">≥25%</option>
        </select>
      </label>
      <label class="param-group">
        <span class="param-label">止损</span>
        <select :value="params.stopLoss" @change="updateParam('stopLoss', $event.target.value)">
          <option value="3">-3%</option>
          <option value="5">-5%</option>
          <option value="8">-8%</option>
        </select>
      </label>
      <label class="param-group">
        <span class="param-label">单仓</span>
        <select :value="params.maxPosPct" @change="updateParam('maxPosPct', $event.target.value)">
          <option value="5">5%</option>
          <option value="10">10%</option>
          <option value="15">15%</option>
          <option value="20">20%</option>
        </select>
      </label>
      <label class="param-group">
        <span class="param-label">持仓数</span>
        <select :value="params.maxPositions" @change="updateParam('maxPositions', $event.target.value)">
          <option value="3">3个</option>
          <option value="5">5个</option>
          <option value="8">8个</option>
          <option value="10">10个</option>
        </select>
      </label>
      <label class="param-group param-toggle">
        <input type="checkbox" :checked="params.atrStop" @change="updateParam('atrStop', $event.target.checked)">
        <span class="param-label">ATR止损</span>
      </label>
      <label class="param-group param-toggle">
        <input type="checkbox" :checked="params.trailing" @change="updateParam('trailing', $event.target.checked)">
        <span class="param-label">移动止损</span>
      </label>
      <label class="param-group param-toggle">
        <input type="checkbox" :checked="params.multiTf" @change="updateParam('multiTf', $event.target.checked)">
        <span class="param-label">多周期</span>
      </label>
      <label class="param-group param-toggle">
        <input type="checkbox" :checked="params.platformBottom" @change="updateParam('platformBottom', $event.target.checked)">
        <span class="param-label">平台底部</span>
      </label>
      <label class="param-group param-toggle">
        <input type="checkbox" :checked="params.probeConfirm" @change="updateParam('probeConfirm', $event.target.checked)">
        <span class="param-label">下探确认</span>
      </label>
      <label class="param-group param-toggle">
        <input type="checkbox" :checked="params.exitReversal" @change="updateParam('exitReversal', $event.target.checked)">
        <span class="param-label">出场反转</span>
      </label>
    </div>
    <div class="crypto-actions">
      <button class="btn-bot-start" :disabled="isRunning" @click="emit('start')">
        启动机器人
      </button>
      <button class="btn-bot-stop" :disabled="!isRunning" @click="emit('stop')">
        停止
      </button>
      <button class="btn-manual-scan" @click="emit('scan')">
        手动扫描
      </button>
      <span class="bot-status-indicator" :class="{ running: isRunning }"></span>
      <span class="bot-status-text">{{ isRunning ? '运行中' : '未启动' }}</span>
    </div>
  </div>
</template>

<style scoped>
.crypto-control-bar {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-sm);
}

.crypto-params {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 20px;
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
  padding: 8px 12px;
  font-size: 13px;
  transition: border-color var(--transition-fast);
}

.param-group select:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.param-toggle {
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

.param-toggle input {
  width: 14px;
  height: 14px;
  accent-color: var(--accent-primary);
}

.crypto-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-bot-start {
  background: var(--accent-success);
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.btn-bot-start:hover:not(:disabled) {
  background: #059669;
}

.btn-bot-start:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-bot-stop {
  background: var(--accent-danger);
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.btn-bot-stop:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-manual-scan {
  background: var(--bg-card);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.btn-manual-scan:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.bot-status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}

.bot-status-indicator.running {
  background: var(--accent-success);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.bot-status-text {
  color: var(--text-secondary);
  font-size: 13px;
}
</style>
