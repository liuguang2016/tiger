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
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.header {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  padding: 0 20px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-inner {
  max-width: 1600px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  height: 56px;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--accent-primary);
  margin-right: 40px;
}

.main-nav {
  display: flex;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  font-size: 14px;
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.nav-icon {
  font-size: 16px;
}
</style>
