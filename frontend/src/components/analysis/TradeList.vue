<script setup>
import { computed } from 'vue'

const props = defineProps({
  trades: {
    type: Array,
    default: () => []
  },
  currentTrade: {
    type: Object,
    default: null
  },
  type: {
    type: String,
    default: 'profitable'
  }
})

const emit = defineEmits(['select', 'type-change', 'sort-change'])

const sortOptions = [
  { value: 'sell_date_desc', label: '卖出日期 ↓' },
  { value: 'sell_date_asc', label: '卖出日期 ↑' },
  { value: 'profit_desc', label: '盈亏金额 ↓' },
  { value: 'profit_asc', label: '盈亏金额 ↑' },
  { value: 'profit_pct_desc', label: '盈亏比例 ↓' },
  { value: 'profit_pct_asc', label: '盈亏比例 ↑' },
  { value: 'holding_days_desc', label: '持仓天数 ↓' },
  { value: 'holding_days_asc', label: '持仓天数 ↑' }
]

const typeCounts = computed(() => {
  const counts = { profitable: 0, losing: 0 }
  props.trades.forEach(t => {
    if (t.profit > 0) counts.profitable++
    else counts.losing++
  })
  return counts
})

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
  <div class="trade-list-panel">
    <div class="panel-header">
      <div class="trade-tabs">
        <button
          class="trade-tab"
          :class="{ active: type === 'profitable' }"
          @click="emit('type-change', 'profitable')"
        >
          盈利 <span class="tab-count">{{ typeCounts.profitable }}</span>
        </button>
        <button
          class="trade-tab"
          :class="{ active: type === 'losing' }"
          @click="emit('type-change', 'losing')"
        >
          亏损 <span class="tab-count">{{ typeCounts.losing }}</span>
        </button>
      </div>
      <select class="sort-select" @change="emit('sort-change', $event.target.value)">
        <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>
    </div>

    <div class="trade-list">
      <div
        v-for="trade in trades"
        :key="trade.id"
        class="trade-item"
        :class="{ active: currentTrade?.id === trade.id, profit: trade.profit > 0, loss: trade.profit < 0 }"
        @click="emit('select', trade)"
      >
        <div class="trade-header">
          <span class="trade-stock">{{ trade.stock_name }}</span>
          <span class="trade-code">{{ trade.stock_code }}</span>
        </div>
        <div class="trade-info">
          <span class="trade-date">{{ trade.buy_date }} ~ {{ trade.sell_date }}</span>
          <span class="trade-profit" :class="{ profit: trade.profit > 0, loss: trade.profit < 0 }">
            {{ formatMoney(trade.profit) }}
          </span>
        </div>
        <div class="trade-details">
          <span>持仓 {{ trade.holding_days }} 天</span>
          <span>{{ formatPct(trade.profit_pct) }}</span>
        </div>
      </div>

      <div v-if="!trades.length" class="trade-empty">
        <p>暂无交易记录</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.trade-list-panel {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.trade-tabs {
  display: flex;
  gap: 4px;
}

.trade-tab {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  font-weight: 500;
}

.trade-tab:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.trade-tab.active {
  color: var(--accent-primary);
  background: rgba(8, 145, 178, 0.08);
}

.tab-count {
  margin-left: 6px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 400;
}

.sort-select {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 13px;
}

.sort-select:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.trade-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.trade-item {
  padding: 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  margin-bottom: 4px;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
}

.trade-item:hover {
  background: var(--bg-primary);
}

.trade-item.active {
  background: rgba(8, 145, 178, 0.06);
  border-color: var(--accent-primary);
}

.trade-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.trade-stock {
  font-weight: 500;
  font-size: 14px;
  color: var(--text-primary);
}

.trade-code {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.trade-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.trade-date {
  font-size: 12px;
  color: var(--text-secondary);
}

.trade-profit {
  font-weight: 600;
  font-family: var(--font-mono);
  font-size: 14px;
}

.trade-profit.profit {
  color: var(--accent-success);
}

.trade-profit.loss {
  color: var(--accent-danger);
}

.trade-details {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-muted);
}

.trade-empty {
  text-align: center;
  padding: 48px;
  color: var(--text-muted);
}
</style>
