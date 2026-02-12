/**
 * 前端主交互逻辑
 * 处理文件上传、交易列表渲染、统计面板更新、K 线图交互
 */

// 全局状态
const AppState = {
    trades: [],          // 盈利交易列表
    stats: null,         // 统计信息
    activeTrade: null,   // 当前选中的交易
    sortBy: 'sell_date_desc',
};

// ============================
// 初始化
// ============================
document.addEventListener('DOMContentLoaded', () => {
    initUpload();
    initSort();
});

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
            AppState.stats = data.stats || {};

            // 显示统计和内容区域
            updateStats(AppState.stats);
            renderTradeList(AppState.trades);

            document.getElementById('stats-section').style.display = 'block';
            document.getElementById('content-section').style.display = 'block';
        } else {
            showUploadStatus(data.message || '解析失败', 'error');
        }
    } catch (err) {
        showUploadStatus('上传失败：' + err.message, 'error');
    }
}

function showUploadStatus(message, type) {
    const el = document.getElementById('upload-status');
    el.style.display = 'block';
    el.className = 'upload-status ' + type;
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
        container.innerHTML = '<div style="text-align:center;color:#6e7681;padding:32px;">没有盈利交易记录</div>';
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
                    <span class="trade-pct">+${trade.profit_pct}%</span>
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
