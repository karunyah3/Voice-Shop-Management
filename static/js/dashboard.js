/**
 * Financial Dashboard & Chart.js Visualizer
 */

let financialChart = null;
let categoryChart = null;

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();

    const refreshBtn = document.getElementById('btn-refresh-dashboard');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadDashboardStats();
            showToast('Dashboard metrics refreshed', 'info');
        });
    }
});

async function loadDashboardStats() {
    try {
        const res = await fetch('/api/dashboard/stats');
        const data = await res.json();

        // 1. Update KPI Cards
        const fin = data.financials;
        document.getElementById('kpi-sales').textContent = `₹${fin.total_sales.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        document.getElementById('kpi-sales-count').textContent = `${fin.sales_count} sales`;

        document.getElementById('kpi-purchases').textContent = `₹${fin.total_purchases.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        document.getElementById('kpi-purchases-count').textContent = `${fin.purchases_count} purchases`;

        document.getElementById('kpi-expenses').textContent = `₹${fin.total_expenses.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        document.getElementById('kpi-expenses-count').textContent = `${fin.expenses_count} expenses`;

        // Net Profit & Badge
        const profitEl = document.getElementById('kpi-net-profit');
        const profitBadge = document.getElementById('kpi-profit-badge');
        profitEl.textContent = `${fin.net_profit >= 0 ? '+' : '-'}₹${Math.abs(fin.net_profit).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        
        if (fin.net_profit >= 0) {
            profitEl.className = 'kpi-value text-success';
            profitBadge.textContent = 'Net Profit';
            profitBadge.className = 'badge badge-success';
        } else {
            profitEl.className = 'kpi-value text-danger';
            profitBadge.textContent = 'Net Loss';
            profitBadge.className = 'badge badge-danger';
        }

        document.getElementById('kpi-margin-text').textContent = `Margin: ${fin.profit_margin}%`;

        // Inventory Stock Valuation
        const inv = data.inventory;
        document.getElementById('kpi-stock-valuation').textContent = `₹${inv.total_valuation.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        document.getElementById('kpi-inventory-count').textContent = `${inv.total_products} products (${inv.total_items} items)`;

        // 2. Render Charts
        renderCharts(data.charts);

        // 3. Render Recent Transactions Table
        renderRecentTransactions(data.recent_transactions);

    } catch (err) {
        console.error('Error fetching dashboard stats:', err);
    }
}

function renderCharts(chartData) {
    const timeline = chartData.timeline;
    const categories = chartData.categories;

    // Timeline Chart (Sales vs Purchases vs Expenses)
    const ctxTimeline = document.getElementById('financialTimelineChart');
    if (ctxTimeline) {
        if (financialChart) financialChart.destroy();

        financialChart = new Chart(ctxTimeline, {
            type: 'bar',
            data: {
                labels: timeline.labels,
                datasets: [
                    {
                        label: 'Sales (₹)',
                        data: timeline.sales,
                        backgroundColor: 'rgba(16, 185, 129, 0.8)',
                        borderColor: '#10b981',
                        borderWidth: 1,
                        borderRadius: 4
                    },
                    {
                        label: 'Purchases (₹)',
                        data: timeline.purchases,
                        backgroundColor: 'rgba(59, 130, 246, 0.8)',
                        borderColor: '#3b82f6',
                        borderWidth: 1,
                        borderRadius: 4
                    },
                    {
                        label: 'Expenses (₹)',
                        data: timeline.expenses,
                        backgroundColor: 'rgba(239, 68, 68, 0.8)',
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
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    }
                }
            }
        });
    }

    // Category Doughnut Chart
    const ctxCat = document.getElementById('categoryDistributionChart');
    if (ctxCat) {
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
                    }
                },
                cutout: '65%'
            }
        });
    }
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
                <td class="fw-bold">${item}</td>
                <td>${qty}</td>
                <td class="fw-bold">₹${t.total_amount.toFixed(2)}</td>
                <td>${party}</td>
                <td class="text-muted small">${t.created_at || 'Recently'}</td>
            </tr>
        `;
    }).join('');
}
