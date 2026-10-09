/**
 * Financial Dashboard & Chart.js Visualizer
 * Supports Today, Month, and All-Time views, daily/monthly chart views,
 * and low stock warnings.
 */

let financialChart = null;
let categoryChart = null;
let currentDashboardData = null;
let selectedPeriod = 'today';
let chartMode = 'daily';

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();

    // Refresh button
    const refreshBtn = document.getElementById('btn-refresh-dashboard');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadDashboardStats();
            showToast('Dashboard metrics refreshed', 'info');
        });
    }

    // Period toggle buttons (Today, Month, All-Time)
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedPeriod = btn.dataset.period;
            updateDashboardKPIs();
        });
    });

    // Chart mode toggle (Daily vs Monthly)
    const btnDaily = document.getElementById('btn-chart-daily');
    const btnMonthly = document.getElementById('btn-chart-monthly');
    if (btnDaily && btnMonthly) {
        btnDaily.addEventListener('click', () => {
            btnDaily.classList.add('active');
            btnMonthly.classList.remove('active');
            chartMode = 'daily';
            if (currentDashboardData) renderFinancialTimeline(currentDashboardData.charts);
        });
        btnMonthly.addEventListener('click', () => {
            btnMonthly.classList.add('active');
            btnDaily.classList.remove('active');
            chartMode = 'monthly';
            if (currentDashboardData) renderFinancialTimeline(currentDashboardData.charts);
        });
    }
});

async function loadDashboardStats() {
    try {
        const res = await fetch('/api/dashboard/stats');
        const data = await res.json();
        currentDashboardData = data;

        // 1. Update KPI Cards for current period
        updateDashboardKPIs();

        // 2. Update Low Stock Banner
        updateLowStockBanner(data.inventory);

        // 3. Render Charts
        renderCharts(data.charts);

        // 4. Render Recent Transactions Table
        renderRecentTransactions(data.recent_transactions);

    } catch (err) {
        console.error('Error fetching dashboard stats:', err);
    }
}

function updateDashboardKPIs() {
    if (!currentDashboardData || !currentDashboardData.financials) return;

    const periodData = currentDashboardData.financials[selectedPeriod] || currentDashboardData.financials.all_time;
    const inv = currentDashboardData.inventory || {};

    const periodNames = {
        'today': "Today's",
        'month': "This Month's",
        'all_time': "Total"
    };
    const pLabel = periodNames[selectedPeriod] || "Total";

    // Labels
    document.getElementById('kpi-sales-label').textContent = `${pLabel} Sales`;
    document.getElementById('kpi-purchases-label').textContent = `${pLabel} Purchases`;
    document.getElementById('kpi-expenses-label').textContent = `${pLabel} Expenses`;
    document.getElementById('kpi-profit-label').textContent = `${pLabel} Net Profit`;

    // Values
    document.getElementById('kpi-sales').textContent = `₹${periodData.total_sales.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    document.getElementById('kpi-sales-count').textContent = `${periodData.sales_count} sales`;

    document.getElementById('kpi-purchases').textContent = `₹${periodData.total_purchases.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    document.getElementById('kpi-purchases-count').textContent = `${periodData.purchases_count} purchases`;

    document.getElementById('kpi-expenses').textContent = `₹${periodData.total_expenses.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    document.getElementById('kpi-expenses-count').textContent = `${periodData.expenses_count} expenses`;

    // Net Profit & Badges
    const profitEl = document.getElementById('kpi-net-profit');
    const profitBadge = document.getElementById('kpi-profit-badge');
    const itemProfitEl = document.getElementById('kpi-gross-profit-text');

    const net = periodData.net_profit;
    profitEl.textContent = `${net >= 0 ? '+' : '-'}₹${Math.abs(net).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

    if (net >= 0) {
        profitEl.className = 'kpi-value text-success';
        profitBadge.textContent = 'Net Profit';
        profitBadge.className = 'badge badge-success';
    } else {
        profitEl.className = 'kpi-value text-danger';
        profitBadge.textContent = 'Net Loss';
        profitBadge.className = 'badge badge-danger';
    }

    if (itemProfitEl) {
        itemProfitEl.textContent = `Item Margin: ₹${periodData.total_item_profit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    }

    // Inventory Stock Valuation
    document.getElementById('kpi-stock-valuation').textContent = `₹${(inv.total_valuation || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    document.getElementById('kpi-inventory-count').textContent = `${inv.total_products || 0} products (${inv.total_items || 0} items)`;
}

function updateLowStockBanner(inventory) {
    const banner = document.getElementById('low-stock-banner');
    const bannerText = document.getElementById('low-stock-banner-text');
    if (!banner || !inventory) return;

    if (inventory.low_stock_count > 0) {
        const itemNames = (inventory.low_stock_items || []).slice(0, 3).map(p => p.name).join(', ');
        const suffix = inventory.low_stock_count > 3 ? ` and ${inventory.low_stock_count - 3} more` : '';
        bannerText.innerHTML = `<strong>${inventory.low_stock_count} item(s)</strong> are low on stock (${itemNames}${suffix})`;
        banner.style.display = 'flex';
    } else {
        banner.style.display = 'none';
    }
}

function renderCharts(chartData) {
    if (!chartData) return;
    renderFinancialTimeline(chartData);
    renderCategoryDistribution(chartData.categories);
}

function renderFinancialTimeline(chartData) {
    const ctxTimeline = document.getElementById('financialTimelineChart');
    if (!ctxTimeline) return;

    if (financialChart) financialChart.destroy();

    const isDaily = chartMode === 'daily';
    const series = isDaily ? chartData.timeline : chartData.monthly;

    financialChart = new Chart(ctxTimeline, {
        type: 'bar',
        data: {
            labels: series.labels,
            datasets: [
                {
                    label: 'Sales (₹)',
                    data: series.sales,
                    backgroundColor: 'rgba(16, 185, 129, 0.85)',
                    borderColor: '#10b981',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Purchases (₹)',
                    data: series.purchases,
                    backgroundColor: 'rgba(59, 130, 246, 0.85)',
                    borderColor: '#3b82f6',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Expenses (₹)',
                    data: series.expenses,
                    backgroundColor: 'rgba(239, 68, 68, 0.85)',
                    borderColor: '#ef4444',
                    borderWidth: 1,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ₹${context.raw.toLocaleString('en-IN')}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#94a3b8',
                        font: { family: 'Inter' },
                        callback: function(value) { return '₹' + value; }
                    }
                }
            }
        }
    });
}

function renderCategoryDistribution(categories) {
    const ctxCat = document.getElementById('categoryDistributionChart');
    if (!ctxCat || !categories) return;

    if (categoryChart) categoryChart.destroy();

    categoryChart = new Chart(ctxCat, {
        type: 'doughnut',
        data: {
            labels: categories.labels,
            datasets: [{
                data: categories.values,
                backgroundColor: [
                    '#2563eb', '#10b981', '#f59e0b', '#06b6d4', '#8b5cf6', '#ec4899', '#64748b'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 }, boxWidth: 12 }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ₹${context.raw.toLocaleString('en-IN')}`;
                        }
                    }
                }
            },
            cutout: '65%'
        }
    });
}

function renderRecentTransactions(txs) {
    const tbody = document.getElementById('dashboard-recent-tbody');
    if (!tbody) return;

    if (!txs || !txs.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No transactions recorded yet.</td></tr>';
        return;
    }

    tbody.innerHTML = txs.map(t => {
        let badgeClass = 'badge-primary';
        if (t.type === 'PURCHASE') badgeClass = 'badge-purple';
        else if (t.type === 'SALE') badgeClass = 'badge-success';
        else if (t.type === 'EXPENSE') badgeClass = 'badge-danger';

        const item = t.product_name || t.category || '--';
        const qty = t.quantity ? `${t.quantity} ${t.unit || ''}` : '--';
        const party = t.party_name || t.notes || '--';

        return `
            <tr>
                <td class="code-font">#${t.id}</td>
                <td><span class="badge ${badgeClass}">${t.type}</span></td>
                <td class="fw-bold">${escapeHtml(item)}</td>
                <td>${qty}</td>
                <td class="fw-bold">₹${t.total_amount.toFixed(2)}</td>
                <td>${escapeHtml(party)}</td>
                <td class="text-muted small">${t.created_at || 'Recently'}</td>
            </tr>
        `;
    }).join('');
}
