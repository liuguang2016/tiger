/**
 * 前端主交互逻辑
 * 处理文件上传、交易列表渲染、统计面板更新、K 线图交互
 */

// 全局状态
const AppState = {
    trades: [],          // 当前 Tab 显示的交易列表
    losingTrades: null,  // 亏损交易缓存（懒加载）
    profitableTrades: null, // 盈利交易缓存
    stats: null,         // 统计信息
    activeTrade: null,   // 当前选中的交易
    activeTab: 'profitable', // 当前 Tab
    sortBy: 'sell_date_desc',
};

// 报告图表实例（用于 resize 和 dispose）
let reportChartInstances = [];

// ============================
// 初始化
// ============================
// 选股页面状态
const PickState = {
    poolStocks: [],
    activePoolStock: null,
    screening: false,
    pollTimer: null,
};

let poolChartInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    initNav();
    initUpload();
    initSort();
    initTabs();
    initReportBtn();
    restoreFromDB();
    initStockPick();
});

// ============================
// 导航菜单切换
// ============================
function initNav() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetPage = item.dataset.page;

            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            const pageEl = document.getElementById('page-' + targetPage);
            if (pageEl) pageEl.classList.add('active');

            if (targetPage === 'stock-pick') {
                loadPoolStocks();
                loadIndexInfo();
            }

            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
            }, 50);
        });
    });
}

/**
 * 页面刷新后自动从服务端数据库恢复数据
 * 如果数据库有交易数据，直接展示统计面板和交易列表
 */
async function restoreFromDB() {
    try {
        const resp = await fetch('/api/trades?type=profitable');
        const data = await resp.json();

        if (!data.success || !data.trades || data.trades.length === 0) {
            return; // 数据库无数据，保持初始上传页面
        }

        // 恢复前端状态
        AppState.trades = data.trades;
        AppState.profitableTrades = data.trades;
        AppState.losingTrades = null;
        AppState.activeTab = 'profitable';
        AppState.stats = data.stats;

        // 渲染统计面板和交易列表
        updateStats(AppState.stats);
        updateTabCounts();
        resetTabHighlight();
        renderTradeList(AppState.trades);

        // 显示各区域
        document.getElementById('stats-section').style.display = 'block';
        document.getElementById('content-section').style.display = 'block';

        // 数据已恢复，折叠上传区域，只保留紧凑状态栏
        document.getElementById('drop-zone').style.display = 'none';
        const bar = document.getElementById('status-bar');
        bar.style.display = 'flex';
        bar.className = 'status-bar';
        const statusEl = document.getElementById('upload-status');
        statusEl.innerHTML =
            `已加载历史交易记录：${AppState.stats.total_trades} 笔交易，` +
            `其中盈利 ${AppState.stats.profitable_count} 笔 ` +
            `<a href="javascript:void(0)" id="reupload-link" style="color:inherit;text-decoration:underline;margin-left:12px;">重新上传交割单</a>`;
        document.getElementById('reupload-link').addEventListener('click', () => {
            document.getElementById('drop-zone').style.display = '';
            bar.style.display = 'none';
        });

        // 显示报告按钮（在状态栏右侧）
        const reportBtn = document.getElementById('generate-report-btn');
        reportBtn.style.display = 'inline-block';
        reportBtn.textContent = '生成交易风格分析报告';
        reportBtn.disabled = false;
    } catch (err) {
        // 静默失败，不影响正常使用
        console.log('恢复数据库数据失败:', err.message);
    }
}

// ============================
// 文件上传
// ============================
function initUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    // 点击上传
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    // 拖拽上传
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });
}

async function uploadFile(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showUploadStatus('请上传 CSV 格式文件', 'error');
        return;
    }

    showUploadStatus('正在上传和解析...', 'success');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch('/api/upload', {
            method: 'POST',
            body: formData,
        });

        const data = await resp.json();

        if (data.success) {
            showUploadStatus(
                `${data.message} | 配对完成：${data.stats.total_trades} 笔交易，` +
                `其中盈利 ${data.stats.profitable_count} 笔`,
                'success'
            );

            AppState.trades = data.trades || [];
            AppState.profitableTrades = data.trades || [];
            AppState.losingTrades = null; // 清除亏损缓存，下次切换时重新加载
            AppState.activeTab = 'profitable';
            AppState.stats = data.stats || {};

            // 显示统计和内容区域
            updateStats(AppState.stats);
            updateTabCounts();
            resetTabHighlight();
            renderTradeList(AppState.trades);

            document.getElementById('stats-section').style.display = 'block';
            document.getElementById('content-section').style.display = 'block';

            // 显示报告按钮，隐藏旧报告
            const reportBtn = document.getElementById('generate-report-btn');
            reportBtn.style.display = 'inline-block';
            reportBtn.textContent = '生成交易风格分析报告';
            reportBtn.disabled = false;
            document.getElementById('report-section').style.display = 'none';
        } else {
            showUploadStatus(data.message || '解析失败', 'error');
            document.getElementById('generate-report-btn').style.display = 'none';
        }
    } catch (err) {
        showUploadStatus('上传失败：' + err.message, 'error');
        document.getElementById('generate-report-btn').style.display = 'none';
    }
}

function showUploadStatus(message, type) {
    const bar = document.getElementById('status-bar');
    const el = document.getElementById('upload-status');
    bar.style.display = 'flex';
    bar.className = 'status-bar' + (type === 'error' ? ' error' : '');
    el.textContent = message;
}

// ============================
// 统计面板
// ============================
function updateStats(stats) {
    setText('stat-total', stats.total_trades);
    setText('stat-profitable', stats.profitable_count);
    setText('stat-winrate', stats.win_rate + '%');
    setText('stat-total-profit', formatMoney(stats.total_profit));
    setText('stat-total-loss', formatMoney(stats.total_loss));

    const netEl = document.getElementById('stat-net-profit');
    netEl.textContent = formatMoney(stats.net_profit);
    netEl.style.color = stats.net_profit >= 0 ? '#f85149' : '#3fb950';

    setText('stat-avg-pct', stats.avg_profit_pct + '%');
    setText('stat-avg-days', stats.avg_holding_days + ' 天');
}

// ============================
// 交易列表
// ============================
function initSort() {
    const sortSelect = document.getElementById('sort-select');
    sortSelect.addEventListener('change', (e) => {
        AppState.sortBy = e.target.value;
        sortAndRenderTrades();
    });
}

function initTabs() {
    document.querySelectorAll('.trade-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const type = tab.dataset.type;
            if (type === AppState.activeTab) return;
            switchTab(type);
        });
    });
}

async function switchTab(type) {
    AppState.activeTab = type;

    // 更新 Tab 高亮
    document.querySelectorAll('.trade-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.type === type);
    });

    // 检查缓存，没有则从 API 加载
    if (type === 'profitable') {
        if (AppState.profitableTrades) {
            AppState.trades = AppState.profitableTrades;
            sortAndRenderTrades();
        } else {
            await loadTrades('profitable');
        }
    } else {
        if (AppState.losingTrades) {
            AppState.trades = AppState.losingTrades;
            sortAndRenderTrades();
        } else {
            await loadTrades('losing');
        }
    }

    // 清除 K 线选中状态
    AppState.activeTrade = null;
}

async function loadTrades(type) {
    const container = document.getElementById('trade-list');
    container.innerHTML = '<div style="text-align:center;color:#6e7681;padding:32px;">加载中...</div>';

    try {
        const resp = await fetch(`/api/trades?type=${type}`);
        const data = await resp.json();
        if (data.success) {
            const trades = data.trades || [];
            if (type === 'profitable') {
                AppState.profitableTrades = trades;
            } else {
                AppState.losingTrades = trades;
            }
            AppState.trades = trades;
            sortAndRenderTrades();
        }
    } catch (err) {
        container.innerHTML = `<div style="text-align:center;color:#f85149;padding:32px;">加载失败: ${err.message}</div>`;
    }
}

function updateTabCounts() {
    const profCount = AppState.stats?.profitable_count ?? 0;
    const loseCount = AppState.stats?.losing_count ?? 0;
    setText('tab-count-profitable', profCount);
    setText('tab-count-losing', loseCount);
}

function resetTabHighlight() {
    document.querySelectorAll('.trade-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.type === 'profitable');
    });
}

function sortAndRenderTrades() {
    const trades = [...AppState.trades];
    const [field, direction] = AppState.sortBy.split('_').reduce((acc, part) => {
        if (part === 'asc' || part === 'desc') {
            acc[1] = part;
        } else {
            acc[0] = acc[0] ? acc[0] + '_' + part : part;
        }
        return acc;
    }, ['', 'desc']);

    trades.sort((a, b) => {
        let valA = a[field];
        let valB = b[field];

        // 字符串比较（日期）
        if (typeof valA === 'string') {
            return direction === 'asc'
                ? valA.localeCompare(valB)
                : valB.localeCompare(valA);
        }

        // 数字比较
        return direction === 'asc' ? valA - valB : valB - valA;
    });

    renderTradeList(trades);
}

function renderTradeList(trades) {
    const container = document.getElementById('trade-list');
    container.innerHTML = '';

    if (trades.length === 0) {
        const label = AppState.activeTab === 'profitable' ? '盈利' : '亏损';
        container.innerHTML = `<div style="text-align:center;color:#6e7681;padding:32px;">没有${label}交易记录</div>`;
        return;
    }

    trades.forEach((trade, idx) => {
        const card = document.createElement('div');
        card.className = 'trade-card';
        card.dataset.index = idx;

        const isActive = AppState.activeTrade &&
            AppState.activeTrade.stock_code === trade.stock_code &&
            AppState.activeTrade.buy_date === trade.buy_date &&
            AppState.activeTrade.sell_date === trade.sell_date;

        if (isActive) {
            card.classList.add('active');
        }

        card.innerHTML = `
            <div class="trade-card-header">
                <div>
                    <span class="trade-stock-name">${escapeHtml(trade.stock_name || trade.stock_code)}</span>
                    <span class="trade-stock-code">${trade.stock_code}</span>
                </div>
                <span class="trade-profit ${trade.profit >= 0 ? '' : 'loss'}">
                    ${trade.profit >= 0 ? '+' : ''}${formatMoney(trade.profit)}
                </span>
            </div>
            <div class="trade-card-body">
                <div class="trade-dates">
                    <span>${trade.buy_date}</span>
                    <span class="trade-arrow">→</span>
                    <span>${trade.sell_date}</span>
                </div>
                <div class="trade-meta">
                    <span class="trade-pct ${trade.profit_pct >= 0 ? '' : 'loss'}">${trade.profit_pct >= 0 ? '+' : ''}${trade.profit_pct}%</span>
                    <span class="trade-days">${trade.holding_days}天</span>
                </div>
            </div>
        `;

        card.addEventListener('click', () => {
            selectTrade(trade, card);
        });

        container.appendChild(card);
    });
}

// ============================
// 选中交易 → 加载 K 线
// ============================
async function selectTrade(trade, cardEl) {
    // 更新选中状态
    AppState.activeTrade = trade;

    document.querySelectorAll('.trade-card.active').forEach(el => {
        el.classList.remove('active');
    });
    if (cardEl) {
        cardEl.classList.add('active');
    }

    // 显示交易信息
    const chartInfo = document.getElementById('chart-info');
    chartInfo.style.display = 'flex';
    document.getElementById('chart-stock-name').textContent = trade.stock_name || trade.stock_code;
    document.getElementById('chart-stock-code').textContent = trade.stock_code;
    document.getElementById('chart-trade-info').textContent =
        `买入 ${trade.buy_date} @ ${trade.buy_price} → 卖出 ${trade.sell_date} @ ${trade.sell_price} | ` +
        `盈利 ${formatMoney(trade.profit)} (${trade.profit_pct}%) | 持仓 ${trade.holding_days} 天`;

    // 显示加载状态
    showChartLoading(true);

    try {
        const params = new URLSearchParams({
            stock_code: trade.stock_code,
            buy_date: trade.buy_date,
            sell_date: trade.sell_date,
        });

        const resp = await fetch(`/api/kline?${params}`);
        const data = await resp.json();

        showChartLoading(false);

        if (data.success) {
            renderKlineChart(data, trade);
        } else {
            showChartError(data.message || '获取 K 线数据失败');
        }
    } catch (err) {
        showChartLoading(false);
        showChartError('请求失败：' + err.message);
    }
}

function showChartLoading(show) {
    const loading = document.getElementById('chart-loading');
    const placeholder = document.getElementById('chart-placeholder');
    const chartEl = document.getElementById('kline-chart');

    if (show) {
        loading.style.display = 'flex';
        placeholder.style.display = 'none';
        chartEl.style.display = 'none';
    } else {
        loading.style.display = 'none';
        chartEl.style.display = 'block';
    }
}

function showChartError(message) {
    const placeholder = document.getElementById('chart-placeholder');
    const chartEl = document.getElementById('kline-chart');
    chartEl.style.display = 'none';
    placeholder.style.display = 'flex';
    placeholder.innerHTML = `<p style="color:#f85149;">${escapeHtml(message)}</p>`;
}

// ============================
// 工具函数
// ============================
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function formatMoney(val) {
    if (val == null) return '-';
    const num = parseFloat(val);
    if (isNaN(num)) return '-';
    // 加千位分隔符
    return num.toLocaleString('zh-CN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ============================
// 交易风格分析报告
// ============================
function initReportBtn() {
    const btn = document.getElementById('generate-report-btn');
    btn.addEventListener('click', generateReport);
}

async function generateReport() {
    const btn = document.getElementById('generate-report-btn');
    btn.disabled = true;
    btn.textContent = '正在生成报告...';

    try {
        const resp = await fetch('/api/report');
        const data = await resp.json();

        if (data.success && data.report && !data.report.empty) {
            renderReport(data.report);
            document.getElementById('report-section').style.display = 'block';
            document.getElementById('report-section').scrollIntoView({ behavior: 'smooth' });
            btn.textContent = '重新生成报告';
        } else {
            alert(data.report?.message || data.message || '生成报告失败');
            btn.textContent = '生成交易风格分析报告';
        }
    } catch (err) {
        alert('请求失败：' + err.message);
        btn.textContent = '生成交易风格分析报告';
    }

    btn.disabled = false;
}

function renderReport(report) {
    // 销毁旧图表
    reportChartInstances.forEach(c => c.dispose());
    reportChartInstances = [];

    // 风格标签
    renderTags(report.tags || []);

    // 6 个图表
    renderHoldingDaysChart(report.holding_days_dist || []);
    renderProfitDistChart(report.profit_pct_dist || []);
    renderMonthlyPnlChart(report.monthly_pnl || []);
    renderAmountTrendChart(report.amount_trend || []);
    renderBoardPrefChart(report.board_pref || []);
    renderStockTop10Chart(report.stock_top10 || []);

    // 文字总结
    renderSummary(report.summary || {});

    // resize 处理
    window.addEventListener('resize', () => {
        reportChartInstances.forEach(c => c.resize());
    });
}

function _initChart(domId) {
    const el = document.getElementById(domId);
    if (!el) return null;
    const chart = echarts.init(el, 'dark');
    reportChartInstances.push(chart);
    return chart;
}

// --- 风格标签 ---
function renderTags(tags) {
    const container = document.getElementById('report-tags');
    container.innerHTML = tags.map(t =>
        `<span class="report-tag">${escapeHtml(t)}</span>`
    ).join('');
}

// --- 持仓天数分布（饼图）---
function renderHoldingDaysChart(data) {
    const chart = _initChart('chart-holding-days');
    if (!chart) return;
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: '{b}: {c}笔 ({d}%)' },
        legend: { bottom: 0, textStyle: { color: '#8b949e', fontSize: 11 } },
        series: [{
            type: 'pie',
            radius: ['35%', '65%'],
            center: ['50%', '45%'],
            avoidLabelOverlap: true,
            itemStyle: { borderRadius: 4, borderColor: '#161b22', borderWidth: 2 },
            label: { show: true, color: '#e6edf3', fontSize: 12, formatter: '{b}\n{d}%' },
            data: data.map((d, i) => ({
                name: d.label,
                value: d.count,
                itemStyle: { color: ['#58a6ff', '#bc8cff', '#d29922', '#3fb950'][i] },
            })),
        }],
    });
}

// --- 盈亏幅度分布（柱状图）---
function renderProfitDistChart(data) {
    const chart = _initChart('chart-profit-dist');
    if (!chart) return;
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: '8%', right: '5%', top: '8%', bottom: '15%' },
        xAxis: {
            type: 'category',
            data: data.map(d => d.label),
            axisLabel: { color: '#8b949e', fontSize: 10, rotate: 25 },
            axisLine: { lineStyle: { color: '#30363d' } },
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#8b949e', fontSize: 10 },
            splitLine: { lineStyle: { color: '#21262d' } },
        },
        series: [{
            type: 'bar',
            barWidth: '50%',
            data: data.map(d => ({
                value: d.count,
                itemStyle: {
                    color: d.label.startsWith('亏')
                        ? '#3fb950'
                        : '#f85149',
                },
            })),
        }],
    });
}

// --- 月度盈亏（正负柱状图）---
function renderMonthlyPnlChart(data) {
    const chart = _initChart('chart-monthly-pnl');
    if (!chart) return;
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: function (params) {
                let html = `<div style="font-weight:600">${params[0].axisValue}</div>`;
                params.forEach(p => {
                    html += `<div style="color:${p.color}">${p.seriesName}: ${p.value.toLocaleString()}</div>`;
                });
                return html;
            },
        },
        legend: { bottom: 0, textStyle: { color: '#8b949e', fontSize: 11 } },
        grid: { left: '10%', right: '5%', top: '8%', bottom: '18%' },
        xAxis: {
            type: 'category',
            data: data.map(d => d.month),
            axisLabel: { color: '#8b949e', fontSize: 10 },
            axisLine: { lineStyle: { color: '#30363d' } },
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#8b949e', fontSize: 10, formatter: v => (v / 10000).toFixed(1) + '万' },
            splitLine: { lineStyle: { color: '#21262d' } },
        },
        series: [
            {
                name: '盈利',
                type: 'bar',
                stack: 'pnl',
                data: data.map(d => d.profit),
                itemStyle: { color: '#f85149' },
            },
            {
                name: '亏损',
                type: 'bar',
                stack: 'pnl',
                data: data.map(d => d.loss),
                itemStyle: { color: '#3fb950' },
            },
        ],
    });
}

// --- 单笔资金规模演变（折线图）---
function renderAmountTrendChart(data) {
    const chart = _initChart('chart-amount-trend');
    if (!chart) return;
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            formatter: p => `${p[0].axisValue}<br/>平均单笔: ${Number(p[0].value).toLocaleString()} 元`,
        },
        grid: { left: '12%', right: '5%', top: '8%', bottom: '12%' },
        xAxis: {
            type: 'category',
            data: data.map(d => d.month),
            axisLabel: { color: '#8b949e', fontSize: 10 },
            axisLine: { lineStyle: { color: '#30363d' } },
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#8b949e', fontSize: 10, formatter: v => (v / 10000).toFixed(1) + '万' },
            splitLine: { lineStyle: { color: '#21262d' } },
        },
        series: [{
            type: 'line',
            data: data.map(d => d.avg_amount),
            smooth: true,
            symbol: 'circle',
            symbolSize: 8,
            lineStyle: { color: '#58a6ff', width: 2 },
            itemStyle: { color: '#58a6ff' },
            areaStyle: { color: 'rgba(88,166,255,0.1)' },
        }],
    });
}

// --- 板块偏好（环形图）---
function renderBoardPrefChart(data) {
    const chart = _initChart('chart-board-pref');
    if (!chart) return;
    const colors = ['#f85149', '#58a6ff', '#bc8cff', '#d29922', '#3fb950'];
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: '{b}: {c}笔 ({d}%)' },
        legend: { bottom: 0, textStyle: { color: '#8b949e', fontSize: 11 } },
        series: [{
            type: 'pie',
            radius: ['40%', '65%'],
            center: ['50%', '45%'],
            itemStyle: { borderRadius: 4, borderColor: '#161b22', borderWidth: 2 },
            label: { show: true, color: '#e6edf3', fontSize: 12, formatter: '{b}\n{d}%' },
            data: data.map((d, i) => ({
                name: d.label,
                value: d.count,
                itemStyle: { color: colors[i % colors.length] },
            })),
        }],
    });
}

// --- 个股盈亏 TOP10（横向柱状图）---
function renderStockTop10Chart(data) {
    const chart = _initChart('chart-stock-top10');
    if (!chart) return;
    // 从下到上，让最大的在上面
    const reversed = [...data].reverse();
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: p => `${p[0].name}<br/>盈亏: ${Number(p[0].value).toLocaleString()} 元`,
        },
        grid: { left: '25%', right: '8%', top: '5%', bottom: '5%' },
        xAxis: {
            type: 'value',
            axisLabel: { color: '#8b949e', fontSize: 10 },
            splitLine: { lineStyle: { color: '#21262d' } },
        },
        yAxis: {
            type: 'category',
            data: reversed.map(d => d.name || d.code),
            axisLabel: { color: '#e6edf3', fontSize: 11 },
            axisLine: { lineStyle: { color: '#30363d' } },
        },
        series: [{
            type: 'bar',
            data: reversed.map(d => ({
                value: d.profit,
                itemStyle: { color: d.profit >= 0 ? '#f85149' : '#3fb950' },
            })),
            barWidth: '55%',
        }],
    });
}

// --- 文字总结 ---
function renderSummary(summary) {
    const container = document.getElementById('report-summary');
    let html = '';

    if (summary.strengths && summary.strengths.length > 0) {
        html += `
            <div class="summary-block strengths">
                <div class="summary-block-title strengths">&#9650; 交易优势</div>
                <ul class="summary-list">
                    ${summary.strengths.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    if (summary.suggestions && summary.suggestions.length > 0) {
        html += `
            <div class="summary-block suggestions">
                <div class="summary-block-title suggestions">&#9654; 改进建议</div>
                <ul class="summary-list">
                    ${summary.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    container.innerHTML = html;
}

// ============================
// 个人选股页面
// ============================

function initStockPick() {
    document.getElementById('btn-start-screen').addEventListener('click', startScreening);
    document.getElementById('btn-clear-pool').addEventListener('click', clearPool);
    loadPoolStocks();
    loadIndexInfo();
}

async function loadIndexInfo() {
    try {
        const resp = await fetch('/api/screener/index');
        const data = await resp.json();
        if (data.success && data.index) {
            renderIndexBar(data.index);
        }
    } catch (_) {}
}

function renderIndexBar(info) {
    const shVal = document.getElementById('idx-sh-val');
    const shChg = document.getElementById('idx-sh-chg');
    const szVal = document.getElementById('idx-sz-val');
    const szChg = document.getElementById('idx-sz-chg');

    if (info.sh_close) {
        shVal.textContent = Number(info.sh_close).toFixed(2);
        const shPct = info.sh_change_pct || 0;
        shChg.textContent = `${shPct >= 0 ? '+' : ''}${shPct}%`;
        shChg.className = 'index-change ' + (shPct >= 0 ? 'up' : 'down');
    }
    if (info.sz_close) {
        szVal.textContent = Number(info.sz_close).toFixed(2);
        const szPct = info.sz_change_pct || 0;
        szChg.textContent = `${szPct >= 0 ? '+' : ''}${szPct}%`;
        szChg.className = 'index-change ' + (szPct >= 0 ? 'up' : 'down');
    }
}

async function startScreening() {
    if (PickState.screening) return;
    PickState.screening = true;

    const btn = document.getElementById('btn-start-screen');
    btn.disabled = true;
    btn.textContent = '筛选中...';

    const progressEl = document.getElementById('screener-progress');
    progressEl.style.display = 'flex';

    const dropPct = parseInt(document.getElementById('param-drop-pct').value);
    const volRatio = parseFloat(document.getElementById('param-vol-ratio').value);

    try {
        await fetch('/api/screener/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ drop_pct: dropPct, volume_ratio: volRatio }),
        });
        pollScreenerStatus();
    } catch (err) {
        showProgressText('启动筛选失败: ' + err.message);
        resetScreenBtn();
    }
}

function pollScreenerStatus() {
    if (PickState.pollTimer) clearTimeout(PickState.pollTimer);

    PickState.pollTimer = setTimeout(async () => {
        try {
            const resp = await fetch('/api/screener/status');
            const data = await resp.json();

            if (data.index_info && data.index_info.sh_close) {
                renderIndexBar(data.index_info);
            }

            const pct = data.total > 0 ? Math.round((data.progress / data.total) * 100) : 0;
            document.getElementById('progress-bar-fill').style.width = pct + '%';
            showProgressText(data.message + (data.found > 0 ? ` | 已发现 ${data.found} 只` : ''));

            if (data.status === 'done') {
                resetScreenBtn();
                if (data.results && data.results.length > 0) {
                    showProgressText(`筛选完成！共 ${data.results.length} 只符合条件`);
                }
                loadPoolStocks();
                return;
            }

            if (data.status === 'error') {
                showProgressText(data.message);
                resetScreenBtn();
                return;
            }

            pollScreenerStatus();
        } catch (err) {
            showProgressText('轮询失败: ' + err.message);
            pollScreenerStatus();
        }
    }, 2000);
}

function showProgressText(msg) {
    document.getElementById('progress-text').textContent = msg;
}

function resetScreenBtn() {
    PickState.screening = false;
    const btn = document.getElementById('btn-start-screen');
    btn.disabled = false;
    btn.textContent = '开始筛选';
}

async function loadPoolStocks() {
    try {
        const resp = await fetch('/api/screener/pool');
        const data = await resp.json();
        if (data.success) {
            PickState.poolStocks = data.stocks || [];
            renderPoolList(PickState.poolStocks);
        }
    } catch (_) {}
}

function renderPoolList(stocks) {
    const container = document.getElementById('pool-list');
    const countEl = document.getElementById('pool-count');
    countEl.textContent = stocks.length;

    if (stocks.length === 0) {
        container.innerHTML = `
            <div class="pool-empty">
                <p>暂无选股结果</p>
                <p class="pool-empty-hint">点击「开始筛选」扫描全A股</p>
            </div>`;
        return;
    }

    container.innerHTML = '';
    stocks.forEach((stock) => {
        const card = document.createElement('div');
        card.className = 'pool-card';
        if (PickState.activePoolStock &&
            PickState.activePoolStock.stock_code === stock.stock_code) {
            card.classList.add('active');
        }

        const changeCls = stock.change_pct >= 0 ? 'up' : 'down';
        const changeSign = stock.change_pct >= 0 ? '+' : '';

        card.innerHTML = `
            <div class="pool-card-header">
                <div>
                    <span class="pool-card-name">${escapeHtml(stock.stock_name)}</span>
                    <span class="pool-card-code">${stock.stock_code}</span>
                </div>
                <span class="pool-card-score">${stock.score}分</span>
            </div>
            <div class="pool-card-tags">
                <span class="pool-tag drop">跌${stock.drop_pct}%</span>
                <span class="pool-tag vol">量比${stock.volume_ratio}</span>
                <span class="pool-tag price">${stock.close_price} (${changeSign}${stock.change_pct}%)</span>
            </div>
            <button class="pool-card-remove" title="移除">&times;</button>
        `;

        card.addEventListener('click', (e) => {
            if (e.target.closest('.pool-card-remove')) return;
            selectPoolStock(stock, card);
        });

        card.querySelector('.pool-card-remove').addEventListener('click', (e) => {
            e.stopPropagation();
            removePoolStock(stock.stock_code);
        });

        container.appendChild(card);
    });
}

async function selectPoolStock(stock, cardEl) {
    PickState.activePoolStock = stock;

    document.querySelectorAll('.pool-card.active').forEach(el => el.classList.remove('active'));
    if (cardEl) cardEl.classList.add('active');

    const info = document.getElementById('pool-chart-info');
    info.style.display = 'flex';
    document.getElementById('pool-stock-name').textContent = stock.stock_name;
    document.getElementById('pool-stock-code').textContent = stock.stock_code;
    document.getElementById('pool-stock-meta').textContent =
        `评分 ${stock.score} | 跌幅 ${stock.drop_pct}% | 量比 ${stock.volume_ratio} | ${stock.reason || ''}`;

    showPoolChartLoading(true);

    try {
        const params = new URLSearchParams({ stock_code: stock.stock_code });
        const resp = await fetch(`/api/kline?${params}`);
        const data = await resp.json();

        showPoolChartLoading(false);

        if (data.success) {
            renderPoolKlineChart(data, stock);
        } else {
            showPoolChartError(data.message || '获取K线数据失败');
        }
    } catch (err) {
        showPoolChartLoading(false);
        showPoolChartError('请求失败: ' + err.message);
    }
}

function renderPoolKlineChart(data, stock) {
    const container = document.getElementById('pool-kline-chart');
    if (poolChartInstance) {
        poolChartInstance.dispose();
    }
    poolChartInstance = echarts.init(container, 'dark');

    window.addEventListener('resize', () => {
        if (poolChartInstance) poolChartInstance.resize();
    });

    const { dates, ohlcv, volumes, ma5, ma10, ma20, ma60 } = data;

    const volumeColors = ohlcv.map(item => item[1] >= item[0] ? 1 : -1);

    const zoomStart = Math.max(0, 100 - (80 / Math.max(dates.length, 1)) * 100);

    const option = {
        backgroundColor: 'transparent',
        animation: false,
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross', crossStyle: { color: '#6e7681' } },
            backgroundColor: 'rgba(22, 27, 34, 0.95)',
            borderColor: '#30363d',
            textStyle: { color: '#e6edf3', fontSize: 12 },
            formatter: function (params) {
                if (!params || params.length === 0) return '';
                const date = params[0].axisValue;
                let html = `<div style="font-weight:600;margin-bottom:6px;">${date}</div>`;
                params.forEach(p => {
                    if (p.seriesName === 'K线' && p.data) {
                        const d = p.data;
                        const color = d[1] >= d[0] ? '#f85149' : '#3fb950';
                        html += `<div style="color:${color}">开: ${d[0]} 收: ${d[1]}<br/>低: ${d[2]} 高: ${d[3]}</div>`;
                    } else if (p.seriesName === '成交量') {
                        html += `<div>成交量: ${formatVolume(p.data)}</div>`;
                    } else if (p.seriesName && p.seriesName.startsWith('MA') && p.data != null) {
                        html += `<div><span style="color:${p.color}">${p.seriesName}: ${p.data}</span></div>`;
                    }
                });
                return html;
            },
        },
        axisPointer: { link: [{ xAxisIndex: [0, 1] }] },
        grid: [
            { left: '8%', right: '3%', top: '5%', height: '55%' },
            { left: '8%', right: '3%', top: '68%', height: '18%' },
        ],
        xAxis: [
            {
                type: 'category', data: dates, gridIndex: 0,
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: { color: '#8b949e', fontSize: 10 },
                splitLine: { show: false }, boundaryGap: true,
                axisPointer: { show: true },
            },
            {
                type: 'category', data: dates, gridIndex: 1,
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: { show: false },
                splitLine: { show: false }, boundaryGap: true,
                axisPointer: { show: true },
            },
        ],
        yAxis: [
            {
                type: 'value', gridIndex: 0, scale: true,
                splitArea: { show: false },
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: { color: '#8b949e', fontSize: 10 },
                splitLine: { lineStyle: { color: '#21262d' } },
            },
            {
                type: 'value', gridIndex: 1, scale: true, splitNumber: 2,
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: {
                    color: '#8b949e', fontSize: 10,
                    formatter: val => formatVolume(val),
                },
                splitLine: { lineStyle: { color: '#21262d' } },
            },
        ],
        dataZoom: [
            { type: 'inside', xAxisIndex: [0, 1], start: zoomStart, end: 100 },
            {
                type: 'slider', xAxisIndex: [0, 1], start: zoomStart, end: 100,
                top: '90%', height: 24,
                borderColor: '#30363d',
                fillerColor: 'rgba(88, 166, 255, 0.15)',
                handleStyle: { color: '#58a6ff' },
                textStyle: { color: '#8b949e' },
            },
        ],
        series: [
            {
                name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
                data: ohlcv,
                itemStyle: {
                    color: '#f85149', color0: '#3fb950',
                    borderColor: '#f85149', borderColor0: '#3fb950',
                },
            },
            {
                name: 'MA5', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                data: ma5, smooth: true, showSymbol: false,
                lineStyle: { width: 1, color: '#d29922' },
            },
            {
                name: 'MA10', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                data: ma10, smooth: true, showSymbol: false,
                lineStyle: { width: 1, color: '#58a6ff' },
            },
            {
                name: 'MA20', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                data: ma20, smooth: true, showSymbol: false,
                lineStyle: { width: 1, color: '#bc8cff' },
            },
            {
                name: 'MA60', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                data: ma60, smooth: true, showSymbol: false,
                lineStyle: { width: 1, color: '#3fb950' },
            },
            {
                name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
                data: volumes,
                itemStyle: {
                    color: function (params) {
                        const idx = params.dataIndex;
                        return idx < volumeColors.length && volumeColors[idx] > 0
                            ? '#f85149' : '#3fb950';
                    },
                },
            },
        ],
    };

    poolChartInstance.setOption(option, true);
}

function showPoolChartLoading(show) {
    const loading = document.getElementById('pool-chart-loading');
    const placeholder = document.getElementById('pool-chart-placeholder');
    const chartEl = document.getElementById('pool-kline-chart');

    if (show) {
        loading.style.display = 'flex';
        placeholder.style.display = 'none';
        chartEl.style.display = 'none';
    } else {
        loading.style.display = 'none';
        chartEl.style.display = 'block';
    }
}

function showPoolChartError(message) {
    const placeholder = document.getElementById('pool-chart-placeholder');
    const chartEl = document.getElementById('pool-kline-chart');
    chartEl.style.display = 'none';
    placeholder.style.display = 'flex';
    placeholder.innerHTML = `<p style="color:#f85149;">${escapeHtml(message)}</p>`;
}

async function removePoolStock(stockCode) {
    try {
        await fetch(`/api/screener/pool/${stockCode}`, { method: 'DELETE' });
        if (PickState.activePoolStock &&
            PickState.activePoolStock.stock_code === stockCode) {
            PickState.activePoolStock = null;
            document.getElementById('pool-chart-info').style.display = 'none';
            document.getElementById('pool-kline-chart').style.display = 'none';
            document.getElementById('pool-chart-placeholder').style.display = 'flex';
            document.getElementById('pool-chart-placeholder').innerHTML =
                '<p>从左侧交易池选择一只股票<br>查看 K 线走势</p>';
        }
        loadPoolStocks();
    } catch (_) {}
}

async function clearPool() {
    if (!confirm('确定清空交易池？')) return;
    try {
        await fetch('/api/screener/pool', { method: 'DELETE' });
        PickState.activePoolStock = null;
        PickState.poolStocks = [];
        renderPoolList([]);

        document.getElementById('pool-chart-info').style.display = 'none';
        document.getElementById('pool-kline-chart').style.display = 'none';
        const ph = document.getElementById('pool-chart-placeholder');
        ph.style.display = 'flex';
        ph.innerHTML = '<p>从左侧交易池选择一只股票<br>查看 K 线走势</p>';
    } catch (_) {}
}
