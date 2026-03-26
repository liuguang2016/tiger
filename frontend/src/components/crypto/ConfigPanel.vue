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
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-sm);
}

.config-row {
  display: flex;
  align-items: flex-end;
  gap: 20px;
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
  font-weight: 500;
}

.config-input {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 13px;
  width: 250px;
  transition: border-color var(--transition-fast);
}

.config-input:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.btn-config-save {
  background: var(--accent-primary);
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.btn-config-save:hover:not(:disabled) {
  background: #077a8a;
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
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
}

.status-badge.running {
  background: rgba(16, 185, 129, 0.12);
  color: var(--accent-success);
}
</style>
