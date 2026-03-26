<script setup>
import { ref } from 'vue'
import NavBar from './components/common/NavBar.vue'
import AnalysisView from './views/AnalysisView.vue'
import ScreenerView from './views/ScreenerView.vue'
import CryptoView from './views/CryptoView.vue'

const currentView = ref('analysis')

const navItems = [
  { id: 'analysis', label: '交割单分析' },
  { id: 'stock-pick', label: '个人选股' },
  { id: 'crypto', label: '数字货币' }
]

function onNavigate(view) {
  currentView.value = view
}
</script>

<template>
  <div class="app">
    <NavBar :items="navItems" :active="currentView" @navigate="onNavigate" />
    <main class="main-container">
      <AnalysisView v-if="currentView === 'analysis'" />
      <ScreenerView v-else-if="currentView === 'stock-pick'" />
      <CryptoView v-else-if="currentView === 'crypto'" />
    </main>
    <footer class="footer">
      <p>Tigger - A 股 & 数字货币交易分析系统</p>
    </footer>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-container {
  flex: 1;
  padding: 32px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

.footer {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
}
</style>
