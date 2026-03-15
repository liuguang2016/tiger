<script setup>
defineProps({
  indexInfo: {
    type: Object,
    default: () => ({})
  }
})

function formatValue(val) {
  if (val == null) return '--'
  return typeof val === 'number' ? val.toFixed(2) : val
}

function formatChange(val) {
  if (val == null) return '--'
  const v = typeof val === 'number' ? val : parseFloat(val)
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}
</script>

<template>
  <div class="index-bar">
    <div class="index-item">
      <span class="index-name">上证指数</span>
      <span class="index-value">{{ formatValue(indexInfo.sh?.value) }}</span>
      <span class="index-change" :class="{ positive: indexInfo.sh?.change > 0, negative: indexInfo.sh?.change < 0 }">
        {{ formatChange(indexInfo.sh?.change) }}
      </span>
    </div>
    <div class="index-item">
      <span class="index-name">深证成指</span>
      <span class="index-value">{{ formatValue(indexInfo.sz?.value) }}</span>
      <span class="index-change" :class="{ positive: indexInfo.sz?.change > 0, negative: indexInfo.sz?.change < 0 }">
        {{ formatChange(indexInfo.sz?.change) }}
      </span>
    </div>
    <div class="index-item">
      <span class="index-name">创业板指</span>
      <span class="index-value">{{ formatValue(indexInfo.cyb?.value) }}</span>
      <span class="index-change" :class="{ positive: indexInfo.cyb?.change > 0, negative: indexInfo.cyb?.change < 0 }">
        {{ formatChange(indexInfo.cyb?.change) }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.index-bar {
  display: flex;
  gap: 24px;
  padding: 12px 20px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
}

.index-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.index-name {
  color: var(--text-secondary);
  font-size: 13px;
}

.index-value {
  font-weight: 600;
  font-family: var(--font-mono);
  font-size: 15px;
}

.index-change {
  font-size: 13px;
  font-family: var(--font-mono);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.index-change.positive {
  color: var(--accent-success);
  background: rgba(63, 185, 80, 0.1);
}

.index-change.negative {
  color: var(--accent-danger);
  background: rgba(248, 81, 73, 0.1);
}
</style>
