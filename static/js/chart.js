/**
 * ECharts K 线图渲染模块
 * 蜡烛图 + 均线(MA5/10/20/60) + 成交量 + 买卖点标记
 */

// 图表实例
let klineChartInstance = null;

/**
 * 初始化或获取图表实例
 */
function getChartInstance() {
    const container = document.getElementById('kline-chart');
    if (!container) return null;

    if (klineChartInstance) {
        klineChartInstance.dispose();
    }
    klineChartInstance = echarts.init(container, 'dark');

    // 响应窗口大小变化
    window.addEventListener('resize', () => {
        if (klineChartInstance) {
            klineChartInstance.resize();
        }
    });

    return klineChartInstance;
}

/**
 * 渲染 K 线图
 * @param {Object} data - K 线数据
 * @param {string} data.stock_code - 股票代码
 * @param {string[]} data.dates - 日期数组
 * @param {number[][]} data.ohlcv - [[open, close, low, high], ...]
 * @param {number[]} data.volumes - 成交量数组
 * @param {number[]} data.ma5 - MA5 数组
 * @param {number[]} data.ma10 - MA10 数组
 * @param {number[]} data.ma20 - MA20 数组
 * @param {number[]} data.ma60 - MA60 数组
 * @param {string} data.buy_date - 买入日期
 * @param {string} data.sell_date - 卖出日期
 * @param {Object} tradeInfo - 交易信息（买入价、卖出价等）
 */
function renderKlineChart(data, tradeInfo) {
    const chart = getChartInstance();
    if (!chart) return;

    const { dates, ohlcv, volumes, ma5, ma10, ma20, ma60, buy_date, sell_date } = data;

    // 计算成交量颜色（涨红跌绿）
    const volumeColors = ohlcv.map(item => {
        // item: [open, close, low, high]
        return item[1] >= item[0] ? 1 : -1; // close >= open 为涨
    });

    // 构建买入/卖出标记点
    const markPoints = [];

    if (buy_date && tradeInfo) {
        const buyIdx = dates.indexOf(buy_date);
        if (buyIdx !== -1) {
            markPoints.push({
                name: '买入',
                coord: [buy_date, ohlcv[buyIdx][2] * 0.995], // low 价格下方
                value: '买 ' + tradeInfo.buy_price,
                itemStyle: { color: '#f85149' },
                symbol: 'arrow',
                symbolSize: 14,
                symbolRotate: 0,
                label: {
                    show: true,
                    position: 'bottom',
                    color: '#f85149',
                    fontSize: 11,
                    fontWeight: 'bold',
                    formatter: '{b}\n{c}',
                },
            });
        }
    }

    if (sell_date && tradeInfo) {
        const sellIdx = dates.indexOf(sell_date);
        if (sellIdx !== -1) {
            markPoints.push({
                name: '卖出',
                coord: [sell_date, ohlcv[sellIdx][3] * 1.005], // high 价格上方
                value: '卖 ' + tradeInfo.sell_price,
                itemStyle: { color: '#3fb950' },
                symbol: 'arrow',
                symbolSize: 14,
                symbolRotate: 180,
                label: {
                    show: true,
                    position: 'top',
                    color: '#3fb950',
                    fontSize: 11,
                    fontWeight: 'bold',
                    formatter: '{b}\n{c}',
                },
            });
        }
    }

    // 计算 dataZoom 的初始范围，确保买卖区间在可视范围内
    let zoomStart = 0;
    let zoomEnd = 100;
    if (dates.length > 0) {
        const buyIdx = buy_date ? dates.indexOf(buy_date) : -1;
        const sellIdx = sell_date ? dates.indexOf(sell_date) : -1;

        if (buyIdx !== -1 && sellIdx !== -1) {
            // 在买卖区间前后各留一些空间
            const padding = Math.max(Math.floor(dates.length * 0.05), 5);
            const startIdx = Math.max(0, buyIdx - padding);
            const endIdx = Math.min(dates.length - 1, sellIdx + padding);
            zoomStart = (startIdx / dates.length) * 100;
            zoomEnd = (endIdx / dates.length) * 100;
        }
    }

    const option = {
        backgroundColor: 'transparent',
        animation: false,
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                crossStyle: { color: '#6e7681' },
            },
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
                        html += `<div style="color:${color}">`;
                        html += `开: ${d[0]} 收: ${d[1]}<br/>`;
                        html += `低: ${d[2]} 高: ${d[3]}`;
                        html += `</div>`;
                    } else if (p.seriesName === '成交量') {
                        html += `<div>成交量: ${formatVolume(p.data)}</div>`;
                    } else if (p.seriesName && p.seriesName.startsWith('MA') && p.data != null) {
                        html += `<div><span style="color:${p.color}">${p.seriesName}: ${p.data}</span></div>`;
                    }
                });
                return html;
            },
        },
        axisPointer: {
            link: [{ xAxisIndex: [0, 1] }],
        },
        grid: [
            {
                // K 线区域
                left: '8%',
                right: '3%',
                top: '5%',
                height: '55%',
            },
            {
                // 成交量区域
                left: '8%',
                right: '3%',
                top: '68%',
                height: '18%',
            },
        ],
        xAxis: [
            {
                type: 'category',
                data: dates,
                gridIndex: 0,
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: { color: '#8b949e', fontSize: 10 },
                splitLine: { show: false },
                boundaryGap: true,
                axisPointer: { show: true },
            },
            {
                type: 'category',
                data: dates,
                gridIndex: 1,
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: { show: false },
                splitLine: { show: false },
                boundaryGap: true,
                axisPointer: { show: true },
            },
        ],
        yAxis: [
            {
                // K 线 Y 轴
                type: 'value',
                gridIndex: 0,
                scale: true,
                splitArea: { show: false },
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: { color: '#8b949e', fontSize: 10 },
                splitLine: { lineStyle: { color: '#21262d' } },
            },
            {
                // 成交量 Y 轴
                type: 'value',
                gridIndex: 1,
                scale: true,
                splitNumber: 2,
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: {
                    color: '#8b949e',
                    fontSize: 10,
                    formatter: function (val) {
                        return formatVolume(val);
                    },
                },
                splitLine: { lineStyle: { color: '#21262d' } },
            },
        ],
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1],
                start: zoomStart,
                end: zoomEnd,
            },
            {
                type: 'slider',
                xAxisIndex: [0, 1],
                start: zoomStart,
                end: zoomEnd,
                top: '90%',
                height: 24,
                borderColor: '#30363d',
                fillerColor: 'rgba(88, 166, 255, 0.15)',
                handleStyle: { color: '#58a6ff' },
                textStyle: { color: '#8b949e' },
            },
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: ohlcv,
                itemStyle: {
                    color: '#f85149',        // 涨 - 红色填充
                    color0: '#3fb950',       // 跌 - 绿色填充
                    borderColor: '#f85149',  // 涨 - 红色边框
                    borderColor0: '#3fb950', // 跌 - 绿色边框
                },
                markPoint: {
                    data: markPoints,
                    animation: false,
                },
                // 买入-卖出区间高亮
                markArea: buy_date && sell_date ? {
                    silent: true,
                    itemStyle: {
                        color: 'rgba(88, 166, 255, 0.06)',
                    },
                    data: [[
                        { xAxis: buy_date },
                        { xAxis: sell_date },
                    ]],
                } : undefined,
            },
            // MA5
            {
                name: 'MA5',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: ma5,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#d29922' },
            },
            // MA10
            {
                name: 'MA10',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: ma10,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#58a6ff' },
            },
            // MA20
            {
                name: 'MA20',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: ma20,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#bc8cff' },
            },
            // MA60
            {
                name: 'MA60',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: ma60,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#3fb950' },
            },
            // 成交量
            {
                name: '成交量',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: volumes,
                itemStyle: {
                    color: function (params) {
                        const idx = params.dataIndex;
                        if (idx < volumeColors.length) {
                            return volumeColors[idx] > 0 ? '#f85149' : '#3fb950';
                        }
                        return '#8b949e';
                    },
                },
            },
        ],
    };

    chart.setOption(option, true);
}

/**
 * 格式化成交量为易读格式
 */
function formatVolume(val) {
    if (val == null) return '-';
    if (val >= 100000000) return (val / 100000000).toFixed(1) + '亿';
    if (val >= 10000) return (val / 10000).toFixed(0) + '万';
    return val.toString();
}

/**
 * 销毁图表
 */
function disposeChart() {
    if (klineChartInstance) {
        klineChartInstance.dispose();
        klineChartInstance = null;
    }
}
