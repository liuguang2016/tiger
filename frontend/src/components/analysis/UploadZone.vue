<script setup>
import { ref } from 'vue'

const emit = defineEmits(['upload', 'generate-report'])

defineProps({
  uploading: {
    type: Boolean,
    default: false
  },
  hasData: {
    type: Boolean,
    default: false
  }
})

const isDragging = ref(false)
const fileInput = ref(null)

function onDragOver(e) {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave() {
  isDragging.value = false
}

function onDrop(e) {
  e.preventDefault()
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file && file.name.endsWith('.csv')) {
    emit('upload', file)
  }
}

function onFileSelect(e) {
  const file = e.target.files[0]
  if (file) {
    emit('upload', file)
  }
}

function triggerFileSelect() {
  fileInput.value?.click()
}
</script>

<template>
  <div class="upload-section">
    <div
      class="drop-zone"
      :class="{ dragging: isDragging }"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
      @click="triggerFileSelect"
    >
      <svg class="drop-zone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M12 11v4m0 0l-2-2m2 2l2-2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <p class="drop-zone-text">拖拽 CSV 交割单到此处，或</p>
      <button class="upload-btn">选择文件</button>
      <p class="drop-zone-hint">支持常见券商导出的 CSV 格式交割单</p>
      <input
        ref="fileInput"
        type="file"
        accept=".csv"
        hidden
        @change="onFileSelect"
      >
    </div>

    <div v-if="uploading" class="status-bar">
      <div class="upload-status">
        <div class="spinner"></div>
        <span>正在上传和解析...</span>
      </div>
    </div>

    <div v-if="hasData && !uploading" class="status-bar">
      <button class="generate-report-btn" @click="emit('generate-report')">
        生成交易风格分析报告
      </button>
    </div>
  </div>
</template>

<style scoped>
.upload-section {
  margin-bottom: 24px;
}

.drop-zone {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: 48px;
  text-align: center;
  cursor: pointer;
  transition: all var(--transition-normal);
  background: var(--bg-primary);
}

.drop-zone:hover,
.drop-zone.dragging {
  border-color: var(--accent-primary);
  background: rgba(8, 145, 178, 0.04);
}

.drop-zone-icon {
  width: 48px;
  height: 48px;
  color: var(--accent-primary);
  margin: 0 auto 16px;
}

.drop-zone-text {
  color: var(--text-secondary);
  margin-bottom: 16px;
  font-size: 14px;
}

.upload-btn {
  background: var(--accent-primary);
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.upload-btn:hover {
  background: #077a8a;
}

.drop-zone-hint {
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 12px;
}

.status-bar {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.upload-status {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-secondary);
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border-color);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.generate-report-btn {
  background: var(--accent-primary);
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.generate-report-btn:hover {
  background: #077a8a;
}
</style>
