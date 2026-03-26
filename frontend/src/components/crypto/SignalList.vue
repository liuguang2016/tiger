<script setup>
defineProps({
  signals: {
    type: Array,
    default: () => []
  },
  currentSymbol: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['select'])

function formatPct(val) {
  if (val == null) return '-'
  return (val >= 0 ? '+' : '') + val.toFixed(2) + '%'
}
</script>

<template>
  <div class="signal-list">
    <div
      v-for="signal in signals"
      :key="signal.symbol"
      class="signal-item"
      :class="{ active: currentSymbol === signal.symbol }"
      @click="emit('select', signal.symbol)"
    >
      <div class="signal-header">
        <span class="signal-symbol">{{ signal.symbol }}</span>
        <span class="signal-price">{{ signal.price?.toFixed(4) }}</span>
      </div>
      <div class="signal-info">
        <span>回落 {{ signal.drop_pct?.toFixed(1) }}%</span>
        <span class="signal-time">{{ signal.time }}</span>
      </div>
    </div>

    <div v-if="!signals.length" class="empty-list">
      <p>暂无信号</p>
    </div>
  </div>
</template>

<style scoped>
.signal-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.signal-item {
  padding: 12px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
  background: var(--bg-secondary);
  margin-bottom: 4px;
}

.signal-item:hover {
  background: var(--bg-primary);
  border-color: var(--border-color);
}

.signal-item.active {
  border-color: var(--accent-primary);
  background: rgba(8, 145, 178, 0.06);
}

.signal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.signal-symbol {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.signal-price {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-secondary);
}

.signal-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}

.signal-time {
  color: var(--text-muted);
}

.empty-list {
  text-align: center;
  padding: 32px;
  color: var(--text-muted);
}
</style>
