<script setup>
defineProps({
  items: {
    type: Array,
    required: true
  },
  active: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['navigate'])
</script>

<template>
  <header class="header">
    <div class="header-inner">
      <h1 class="header-title">Tigger</h1>
      <nav class="main-nav">
        <button
          v-for="item in items"
          :key="item.id"
          class="nav-item"
          :class="{ active: active === item.id }"
          @click="emit('navigate', item.id)"
        >
          {{ item.label }}
        </button>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.header {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-inner {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  height: 56px;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--accent-primary);
  margin-right: 48px;
}

.main-nav {
  display: flex;
  gap: 4px;
}

.nav-item {
  padding: 8px 20px;
  border-radius: 6px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  font-size: 14px;
  font-weight: 500;
  position: relative;
}

.nav-item:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}

.nav-item.active {
  color: var(--accent-primary);
}

.nav-item.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 20px;
  right: 20px;
  height: 2px;
  background: var(--accent-primary);
  border-radius: 2px 2px 0 0;
}
</style>
