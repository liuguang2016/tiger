<script setup>
defineProps({
  positions: {
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
  return (val >= 0 ? '+' : '') + val.toFixed(2) + '%'
}
</script>

<template>
  <div class="position-list">
    <div
      v-for="pos in positions"
      :key="pos.symbol"
      class="position-item"
      :class="{ active: currentSymbol === pos.symbol, profit: pos.unrealized_pnl > 0, loss: pos.unrealized_pnl < 0 }"
      @click="emit('select', pos.symbol)"
    >
      <div class="position-header">
        <span class="position-symbol">{{ pos.symbol }}</span>
        <span class="position-pnl" :class="{ profit: pos.unrealized_pnl > 0, loss: pos.unrealized_pnl < 0 }">
          {{ formatMoney(pos.unrealized_pnl) }}
        </span>
      </div>
      <div class="position-info">
        <span>{{ formatPct(pos.pnl_pct) }}</span>
        <span>持仓 {{ pos.qty }}</span>
      </div>
      <div class="position-prices">
        <span>买入: {{ pos.entry_price?.toFixed(4) }}</span>
        <span>当前: {{ pos.current_price?.toFixed(4) }}</span>
      </div>
    </div>

    <div v-if="!positions.length" class="empty-list">
      <p>暂无持仓</p>
    </div>
  </div>
</template>

<style scoped>
.position-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.position-item {
  padding: 14px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
  background: var(--bg-secondary);
  margin-bottom: 4px;
}

.position-item:hover {
  background: var(--bg-primary);
  border-color: var(--border-color);
}

.position-item.active {
  border-color: var(--accent-primary);
  background: rgba(8, 145, 178, 0.06);
}

.position-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.position-symbol {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.position-pnl {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
}

.position-pnl.profit {
  color: var(--accent-success);
}

.position-pnl.loss {
  color: var(--accent-danger);
}

.position-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.position-prices {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.empty-list {
  text-align: center;
  padding: 32px;
  color: var(--text-muted);
}
</style>
