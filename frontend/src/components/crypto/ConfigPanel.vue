<script setup>
import { ref } from 'vue'

const props = defineProps({
  config: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['save'])

const apiKey = ref('')
const apiSecret = ref('')

function handleSave() {
  emit('save', apiKey.value, apiSecret.value)
}
</script>

<template>
  <div class="crypto-config-bar">
    <div class="config-row">
      <div class="config-field">
        <label class="config-label">API Key</label>
        <input
          v-model="apiKey"
          type="password"
          class="config-input"
          placeholder="Binance API Key"
        >
      </div>
      <div class="config-field">
        <label class="config-label">API Secret</label>
        <input
          v-model="apiSecret"
          type="password"
          class="config-input"
          placeholder="Binance API Secret"
        >
      </div>
      <button class="btn-config-save" :disabled="loading" @click="handleSave">
        {{ loading ? '保存中...' : '保存配置' }}
      </button>
      <span v-if="config" class="config-status">
        <template v-if="config.api_key">
          Key: ***{{ config.api_key }}
          <span v-if="config.is_running" class="status-badge running">运行中</span>
        </template>
      </span>
    </div>
  </div>
</template>

<style scoped>
.crypto-config-bar {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 20px;
}

.config-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.config-input {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: 13px;
  width: 250px;
}

.btn-config-save {
  background: var(--accent-primary);
  color: white;
  padding: 8px 20px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  transition: all var(--transition-fast);
}

.btn-config-save:hover:not(:disabled) {
  background: #4a9eff;
}

.btn-config-save:disabled {
  opacity: 0.6;
}

.config-status {
  color: var(--text-secondary);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.status-badge.running {
  background: rgba(63, 185, 80, 0.2);
  color: var(--accent-success);
}
</style>
