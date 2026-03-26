<script setup>
defineProps({
  trades: {
    type: Array,
    default: () => []
  },
  currentSymbol: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['select'])

function formatMoney(val) {
  if (val == null) return '-'
  return (val >= 0 ? '+' : '') + val.toFixed(2)
}

function formatPct(val) {
  if (val == null) return '-'
  return (val >= 0 ? '+' : '') + (val * 100).toFixed(2) + '%'
}
</script>

<template>
  <div class="trade-list">
    <div
      v-for="trade in trades"
      :key="trade.id"
      class="trade-item"
      :class="{ active: currentSymbol === trade.symbol, profit: trade.pnl > 0, loss: trade.pnl < 0 }"
      @click="emit('select', trade.symbol)"
    >
      <div class="trade-header">
        <span class="trade-symbol">{{ trade.symbol }}</span>
        <span class="trade-pnl" :class="{ profit: trade.pnl > 0, loss: trade.pnl < 0 }">
          {{ formatMoney(trade.pnl) }}
        </span>
      </div>
      <div class="trade-info">
        <span class="trade-side" :class="trade.side">{{ trade.side === 'BUY' ? '买入' : '卖出' }}</span>
        <span>{{ trade.qty }}</span>
        <span class="trade-pct">{{ formatPct(trade.pnl_pct) }}</span>
      </div>
      <div class="trade-time">
        {{ trade.time }}
      </div>
    </div>

    <div v-if="!trades.length" class="empty-list">
      <p>暂无交易记录</p>
    </div>
  </div>
</template>

<style scoped>
.trade-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 400px;
  overflow-y: auto;
}

.trade-item {
  padding: 14px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
  background: var(--bg-secondary);
  margin-bottom: 4px;
}

.trade-item:hover {
  background: var(--bg-primary);
  border-color: var(--border-color);
}

.trade-item.active {
  border-color: var(--accent-primary);
  background: rgba(8, 145, 178, 0.06);
}

.trade-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.trade-symbol {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.trade-pnl {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
}

.trade-pnl.profit {
  color: var(--accent-success);
}

.trade-pnl.loss {
  color: var(--accent-danger);
}

.trade-info {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.trade-side {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.trade-side.BUY {
  background: rgba(16, 185, 129, 0.12);
  color: var(--accent-success);
}

.trade-side.SELL {
  background: rgba(239, 68, 68, 0.12);
  color: var(--accent-danger);
}

.trade-time {
  font-size: 11px;
  color: var(--text-muted);
}

.empty-list {
  text-align: center;
  padding: 32px;
  color: var(--text-muted);
}
</style>
