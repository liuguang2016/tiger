<script setup>
defineProps({
  label: {
    type: String,
    required: true
  },
  value: {
    type: [String, Number],
    default: '-'
  },
  variant: {
    type: String,
    default: '',
    validator: (v) => ['', 'profit', 'loss'].includes(v)
  }
})
</script>

<template>
  <div class="stat-card" :class="variant">
    <span class="stat-label">{{ label }}</span>
    <span class="stat-value">{{ value }}</span>
  </div>
</template>

<style scoped>
.stat-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-fast);
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
}

.stat-card.profit .stat-value {
  color: var(--accent-success);
}

.stat-card.loss .stat-value {
  color: var(--accent-danger);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono);
  line-height: 1.2;
}
</style>
