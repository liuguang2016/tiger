<script setup>
defineProps({
  stocks: {
    type: Array,
    default: () => []
  },
  currentStock: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['select', 'remove', 'clear'])

function formatPct(val) {
  if (val == null) return '-'
  return (val >= 0 ? '+' : '') + val.toFixed(2) + '%'
}
</script>

<template>
  <div class="stock-pool">
    <div class="pool-header">
      <h3 class="pool-title">
        交易池 <span class="pool-count">{{ stocks.length }}</span>
      </h3>
      <button v-if="stocks.length" class="btn-clear-pool" @click="emit('clear')">清空</button>
    </div>
    <div class="pool-list">
      <div
        v-for="stock in stocks"
        :key="stock.code"
        class="pool-item"
        :class="{ active: currentStock?.code === stock.code }"
        @click="emit('select', stock)"
      >
        <div class="pool-item-header">
          <span class="stock-name">{{ stock.name }}</span>
          <span class="stock-code">{{ stock.code }}</span>
          <button class="btn-remove" @click.stop="emit('remove', stock.code)">×</button>
        </div>
        <div class="pool-item-info">
          <span>回落 {{ stock.drop_pct?.toFixed(1) }}%</span>
          <span>量比 {{ stock.vol_ratio?.toFixed(1) }}</span>
        </div>
        <div v-if="stock.reason" class="pool-item-reason">{{ stock.reason }}</div>
      </div>

      <div v-if="!stocks.length" class="pool-empty">
        <p>暂无选股结果</p>
        <p class="pool-empty-hint">点击「开始筛选」扫描全A股</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stock-pool {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.pool-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.pool-title {
  font-size: 14px;
  font-weight: 600;
}

.pool-count {
  color: var(--accent-primary);
  margin-left: 8px;
}

.btn-clear-pool {
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  padding: 4px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.btn-clear-pool:hover {
  background: var(--accent-danger);
  color: white;
  border-color: var(--accent-danger);
}

.pool-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.pool-item {
  padding: 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  margin-bottom: 4px;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
}

.pool-item:hover {
  background: var(--bg-hover);
}

.pool-item.active {
  background: var(--bg-tertiary);
  border-color: var(--accent-primary);
}

.pool-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.stock-name {
  font-weight: 500;
  color: var(--text-primary);
}

.stock-code {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.btn-remove {
  margin-left: auto;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  color: var(--text-muted);
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}

.btn-remove:hover {
  background: var(--accent-danger);
  color: white;
}

.pool-item-info {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.pool-item-reason {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pool-empty {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}

.pool-empty-hint {
  font-size: 12px;
  margin-top: 8px;
}
</style>
