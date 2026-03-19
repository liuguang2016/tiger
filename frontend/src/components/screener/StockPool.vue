<script setup>
defineProps({
  stocks: {
    type: Array,
    default: () => []
  },
  currentStock: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['select', 'remove', 'clear'])

function formatPct(val) {
  if (val == null) return '-'
  return (val >= 0 ? '+' : '') + val.toFixed(2) + '%'
}

function getTagClass(tag) {
  const tagMap = {
    'pattern': 'pattern',
    'ma': 'ma',
    'signal': 'signal',
    'confidence': 'confidence',
    'probe': 'probe',
    'platform': 'platform',
  }
  return tagMap[tag] || 'price'
}
</script>

<template>
  <div class="stock-pool">
    <div class="pool-header">
      <h3 class="pool-title">
        交易池 <span class="pool-count">{{ stocks.length }}</span>
      </h3>
      <button v-if="stocks.length" class="btn-clear-pool" @click="emit('clear')">清空</button>
    </div>
    <div class="pool-list">
      <div
        v-for="stock in stocks"
        :key="stock.code"
        class="pool-card"
        :class="{ active: currentStock?.code === stock.code }"
        @click="emit('select', stock)"
      >
        <div class="pool-card-header">
          <div class="pool-card-name-wrap">
            <span class="pool-card-name">{{ stock.name }}</span>
            <span class="pool-card-code">{{ stock.code }}</span>
          </div>
          <span v-if="stock.score" class="pool-card-score">{{ stock.score.toFixed(1) }}</span>
        </div>
        <div class="pool-card-tags">
          <span class="pool-tag drop">回落 {{ stock.drop_pct?.toFixed(1) }}%</span>
          <span class="pool-tag vol">量比 {{ stock.volume_ratio?.toFixed(1) }}</span>
          <span
            v-for="tag in (stock.tags || [])"
            :key="tag"
            class="pool-tag"
            :class="getTagClass(tag)"
          >{{ tag }}</span>
          <span v-if="stock.pattern" class="pool-tag pattern">{{ stock.pattern }}</span>
        </div>
        <div v-if="stock.reason" class="pool-card-reason">{{ stock.reason }}</div>
        <button class="pool-card-remove" @click.stop="emit('remove', stock.code)">×</button>
      </div>

      <div v-if="!stocks.length" class="pool-empty">
        <p>暂无选股结果</p>
        <p class="pool-empty-hint">点击「开始筛选」扫描全A股</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stock-pool {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.pool-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.pool-title {
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pool-count {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(248, 81, 73, 0.15);
  color: var(--accent-danger, #f85149);
}

.btn-clear-pool {
  padding: 4px 12px;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-clear-pool:hover {
  color: var(--accent-danger, #f85149);
  border-color: var(--accent-danger, #f85149);
}

.pool-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.pool-list::-webkit-scrollbar {
  width: 6px;
}

.pool-list::-webkit-scrollbar-track {
  background: transparent;
}

.pool-list::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.pool-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-muted);
  font-size: 14px;
  text-align: center;
}

.pool-empty-hint {
  font-size: 12px;
  margin-top: 6px;
}

/* 交易池股票卡片 */
.pool-card {
  background: var(--bg-tertiary, #1c2128);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm, 8px);
  padding: 12px 14px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
}

.pool-card:hover {
  background: var(--bg-hover, #252c35);
  border-color: var(--accent-primary, #58a6ff);
}

.pool-card.active {
  border-color: var(--accent-primary, #58a6ff);
  background: rgba(88, 166, 255, 0.08);
}

.pool-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.pool-card-name-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.pool-card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.pool-card-code {
  font-size: 11px;
  color: var(--text-muted);
}

.pool-card-score {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-yellow, #d29922);
}

.pool-card-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.pool-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.pool-tag.drop {
  color: var(--color-green, #3fb950);
  background: rgba(63, 185, 80, 0.1);
}

.pool-tag.vol {
  color: var(--accent-danger, #f85149);
  background: rgba(248, 81, 73, 0.1);
}

.pool-tag.price {
  color: var(--text-secondary);
  background: rgba(139, 148, 158, 0.1);
}

.pool-tag.pattern {
  color: var(--color-yellow, #d29922);
  background: rgba(210, 153, 34, 0.15);
}

.pool-tag.ma {
  color: var(--accent-primary, #58a6ff);
  background: rgba(88, 166, 255, 0.12);
}

.pool-tag.signal {
  color: var(--color-purple, #bc8cff);
  background: rgba(188, 140, 255, 0.12);
}

.pool-tag.confidence {
  color: var(--color-orange, #db6d28);
  background: rgba(219, 109, 40, 0.12);
}

.pool-tag.probe {
  color: #f0883e;
  background: rgba(240, 136, 62, 0.15);
  font-weight: 600;
}

.pool-tag.platform {
  color: #a371f7;
  background: rgba(163, 113, 247, 0.12);
}

.pool-card-reason {
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pool-card-remove {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 14px;
  cursor: pointer;
  border-radius: 50%;
  display: none;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.pool-card:hover .pool-card-remove {
  display: flex;
}

.pool-card-remove:hover {
  background: var(--accent-danger, #f85149);
  color: white;
}
</style>
