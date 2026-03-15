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
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
}

.position-item:hover {
  background: var(--bg-hover);
}

.position-item.active {
  background: var(--bg-tertiary);
  border-color: var(--accent-primary);
}

.position-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.position-symbol {
  font-weight: 600;
  font-size: 14px;
}

.position-pnl {
  font-family: var(--font-mono);
  font-size: 13px;
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
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 2px;
}

.position-prices {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-muted);
}

.empty-list {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
}
</style>
