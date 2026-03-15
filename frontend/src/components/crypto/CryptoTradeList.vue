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
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
}

.trade-item:hover {
  background: var(--bg-hover);
}

.trade-item.active {
  background: var(--bg-tertiary);
  border-color: var(--accent-primary);
}

.trade-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.trade-symbol {
  font-weight: 600;
  font-size: 14px;
}

.trade-pnl {
  font-family: var(--font-mono);
  font-size: 13px;
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
  gap: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.trade-side {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
}

.trade-side.BUY {
  background: rgba(63, 185, 80, 0.2);
  color: var(--accent-success);
}

.trade-side.SELL {
  background: rgba(248, 81, 73, 0.2);
  color: var(--accent-danger);
}

.trade-time {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 2px;
}

.empty-list {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
}
</style>
