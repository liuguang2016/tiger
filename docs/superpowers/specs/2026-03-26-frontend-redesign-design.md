# 前端界面重构设计方案

**日期**: 2026-03-26
**项目**: Tigger 前端界面简约化改造
**风格**: 简约轻量 + 清晰层次留白

---

## 1. 设计目标

- 打造简约、轻量的现代界面
- 提升信息层次感，增加留白呼吸空间
- 去除 emoji，使用精致 SVG 图标
- 保持功能完整，优化视觉体验

---

## 2. 配色规范

### 色彩系统
```
背景主色:     #f8f6f3  (暖米白)
背景卡片:     #ffffff  (纯白)
背景次要:     #f1f5f9  (浅灰)
边框:         #e2e8f0  (淡灰)
文字主色:     #1e293b  (深灰)
文字次要:     #64748b  (中灰)
文字弱化:     #94a3b8  (浅灰)
强调色:       #0891b2  (青色)
成功色:       #10b981  (绿色)
亏损色:       #ef4444  (红色)
警告色:       #f59e0b  (橙色)
```

### CSS Variables
```css
:root {
  --bg-primary: #f8f6f3;
  --bg-card: #ffffff;
  --bg-secondary: #f1f5f9;
  --border-color: #e2e8f0;
  --text-primary: #1e293b;
  --text-secondary: #64748b;
  --text-muted: #94a3b8;
  --accent-primary: #0891b2;
  --accent-success: #10b981;
  --accent-danger: #ef4444;
  --accent-warning: #f59e0b;
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
}
```

---

## 3. 导航栏

### 设计
- 高度: 56px
- 背景: 纯白 `#ffffff`
- 底部边框: 1px solid `#e2e8f0`
- Logo 颜色: 青色 `#0891b2`

### 导航项
- 去 emoji，纯文字
- 默认: 灰色 `#64748b`
- 悬停: 深灰 `#1e293b`
- 选中: 青色 `#0891b2` + 2px 青色下划线
- 内边距: 12px 20px
- 圆角: 6px（仅悬停/选中态）

---

## 4. 卡片系统

### 通用卡片
- 背景: `#ffffff`
- 圆角: 12px
- 阴影: `0 1px 3px rgba(0,0,0,0.06)`
- 内边距: 20-24px
- 元素间距: 16-20px

### 统计卡片 (StatCard)
- 背景: `#ffffff`
- 内边距: 20px
- 标签: 12px, `#64748b`
- 数值: 24px, `#1e293b`, font-weight 600
- 底部留白增加 50%

### 图表面板
- 背景: `#ffffff`
- 圆角: 12px
- 内边距: 20px
- 股票信息与图表间距: 16px

---

## 5. 列表/表格

### 设计原则
- 行高增加，提升可读性
- 无竖线分隔，靠间距区分
- 悬停背景: `#f8f6f3`

### 交易列表
- 行高: 52px
- 内边距: 16px 水平
- 分隔线: 1px solid `#f1f5f9`
- 股票名称: 14px, `#1e293b`
- 代码/日期: 12px, `#94a3b8`

---

## 6. 按钮系统

### 主按钮
- 背景: `#0891b2`
- 文字: `#ffffff`
- 圆角: 8px
- 内边距: 10px 20px
- 悬停: 背景加深 10%

### 次按钮
- 背景: `#ffffff`
- 边框: 1px solid `#e2e8f0`
- 文字: `#64748b`
- 圆角: 8px
- 悬停: 背景 `#f8f6f3`

### 危险按钮
- 背景: `#ef4444`
- 文字: `#ffffff`

---

## 7. 标签页 (Tabs)

### 设计
- 背景分隔: 无
- 选中态: 文字青色 `#0891b2` + 底部 2px 青色边框
- 未选中: 文字 `#64748b`
- 内边距: 14px 20px
- 间距均匀分布

---

## 8. 输入控件

### Select 下拉框
- 背景: `#ffffff`
- 边框: 1px solid `#e2e8f0`
- 圆角: 6px
- 内边距: 10px 14px
- 聚焦: 边框青色 `#0891b2`

### 上传区域
- 背景: `#f8f6f3`
- 边框: 2px dashed `#e2e8f0`
- 圆角: 12px
- 悬停: 边框青色

---

## 9. 页面结构调整

### 整体布局
- 最大宽度: 1400px（收缩两边留白）
- 内边距: 32px（桌面）
- 元素间距: 24px（增加 50%）

### 主内容区
- 上边距: 32px
- 卡片间距: 24px

---

## 10. 组件清单

| 组件 | 改动说明 |
|------|----------|
| NavBar | 去 emoji，文字导航，青色选中态 |
| StatCard | 阴影加深，数值更大，留白增加 |
| UploadZone | 边框样式，暖色背景 |
| TradeList | 行高增加，悬停效果 |
| KLineChart | 白色背景，圆角卡片 |
| IndexBar | 暖白背景，青色数值 |
| StockPool | 卡片化，去边框 |
| BotControls | 按钮统一样式 |
| ConfigPanel | 内边距增加 |
| CryptoTradeList | 间距优化 |

---

## 11. 实施文件清单

### 需要修改的文件
```
frontend/src/styles/variables.css     - 配色系统
frontend/src/App.vue                  - 布局调整
frontend/src/components/common/NavBar.vue
frontend/src/components/common/StatCard.vue
frontend/src/components/common/KLineChart.vue
frontend/src/components/analysis/UploadZone.vue
frontend/src/components/analysis/TradeList.vue
frontend/src/components/analysis/TradeReport.vue
frontend/src/components/screener/IndexBar.vue
frontend/src/components/screener/ScreenerControls.vue
frontend/src/components/screener/StockPool.vue
frontend/src/components/crypto/ConfigPanel.vue
frontend/src/components/crypto/BotControls.vue
frontend/src/components/crypto/SignalList.vue
frontend/src/components/crypto/PositionList.vue
frontend/src/components/crypto/CryptoTradeList.vue
frontend/src/views/AnalysisView.vue
frontend/src/views/ScreenerView.vue
frontend/src/views/CryptoView.vue
```

---

## 12. 实施顺序

1. **variables.css** - 全局样式变量
2. **NavBar** - 导航栏改造
3. **StatCard** - 统计卡片
4. **UploadZone** - 上传组件
5. **TradeList** - 交易列表
6. **KLineChart** - K线图容器
7. **IndexBar** - 指数条
8. **StockPool** - 股票池
9. **BotControls** - 机器人控制
10. **ConfigPanel** - 配置面板
11. **各 View 页面** - 布局调整

---

## 13. 验证标准

- [ ] 页面背景为暖米白 `#f8f6f3`
- [ ] 卡片为纯白，带轻阴影
- [ ] 导航无 emoji，有青色选中态
- [ ] 统计数值清晰可读
- [ ] 元素间距明显增大
- [ ] 按钮样式统一
- [ ] 整体感觉简约、轻量、有呼吸感
