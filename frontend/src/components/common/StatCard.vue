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
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all var(--transition-fast);
}

.stat-card:hover {
  border-color: var(--border-light);
}

.stat-card.profit {
  border-color: rgba(63, 185, 80, 0.3);
}

.stat-card.profit .stat-value {
  color: var(--accent-success);
}

.stat-card.loss {
  border-color: rgba(248, 81, 73, 0.3);
}

.stat-card.loss .stat-value {
  color: var(--accent-danger);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono);
}
</style>
