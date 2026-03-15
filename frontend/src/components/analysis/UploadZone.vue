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
      <div class="drop-zone-icon">📂</div>
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
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all var(--transition-normal);
  background: var(--bg-secondary);
}

.drop-zone:hover,
.drop-zone.dragging {
  border-color: var(--accent-primary);
  background: rgba(88, 166, 255, 0.05);
}

.drop-zone-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.drop-zone-text {
  color: var(--text-secondary);
  margin-bottom: 16px;
}

.upload-btn {
  background: var(--accent-primary);
  color: white;
  padding: 10px 24px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.upload-btn:hover {
  background: #4a9eff;
}

.drop-zone-hint {
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 12px;
}

.status-bar {
  margin-top: 16px;
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
  background: var(--accent-purple);
  color: white;
  padding: 12px 24px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.generate-report-btn:hover {
  background: #9333ea;
}
</style>
