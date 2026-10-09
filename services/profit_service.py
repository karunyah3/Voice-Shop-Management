"""
Financial Analytics and Profit & Loss Service.
Calculates sales revenue, purchase costs, overhead expenses, item profit (gross margin),
operating profit, and net profit across Today, This Month, and All-Time periods.
Prepares structured metrics and series for interactive dashboard charts.
"""
from typing import Dict, Any, List, Optional
from database.database import query_db
from config import Config

class ProfitService:
    def __init__(self, db_path: str = None):
        self.db_path = db_path

    def _query_period_metrics(self, date_clause: str = "") -> Dict[str, Any]:
        """
        Helper to calculate financial KPIs with optional date filter clause.
        Formula:
        - Total Sales: Sum of sale amounts
        - Total Purchases: Sum of purchase amounts
        - Total Expenses: Sum of overhead expenses
        - Total Item Profit (Gross Margin): Sum of ((Selling Price - Cost Price) * Quantity) on sold items
        - Operating Profit: Item Profit (Gross Margin) - Total Expenses
        - Net Cashflow Profit: Total Sales - Total Purchases - Total Expenses
        """
        where_sale = "WHERE type = 'SALE'" + (f" AND {date_clause}" if date_clause else "")
        where_purch = "WHERE type = 'PURCHASE'" + (f" AND {date_clause}" if date_clause else "")
        where_exp = "WHERE type = 'EXPENSE'" + (f" AND {date_clause}" if date_clause else "")

        sales_row = query_db(f"""
            SELECT 
                COUNT(*) as count,
                COALESCE(SUM(total_amount), 0) as total_sales,
                COALESCE(SUM(profit), 0) as total_item_profit
            FROM transactions 
            {where_sale}
        """, one=True, db_path=self.db_path)

        purchases_row = query_db(f"""
            SELECT 
                COUNT(*) as count,
                COALESCE(SUM(total_amount), 0) as total_purchases
            FROM transactions 
            {where_purch}
        """, one=True, db_path=self.db_path)

        expenses_row = query_db(f"""
            SELECT 
                COUNT(*) as count,
                COALESCE(SUM(total_amount), 0) as total_expenses
            FROM transactions 
            {where_exp}
        """, one=True, db_path=self.db_path)

        total_sales = float(sales_row['total_sales']) if sales_row else 0.0
        sales_count = int(sales_row['count']) if sales_row else 0
        total_item_profit = float(sales_row['total_item_profit']) if sales_row else 0.0

        total_purchases = float(purchases_row['total_purchases']) if purchases_row else 0.0
        purchases_count = int(purchases_row['count']) if purchases_row else 0

        total_expenses = float(expenses_row['total_expenses']) if expenses_row else 0.0
        expenses_count = int(expenses_row['count']) if expenses_row else 0

        # Net Profit = Total Sales - Total Purchases - Total Expenses
        net_profit = round(total_sales - total_purchases - total_expenses, 2)
        
        # Operating Profit = Gross Item Margin on Sold Goods - Overhead Expenses
        operating_profit = round(total_item_profit - total_expenses, 2)

        # Margin percentage on sales
        profit_margin = round((net_profit / total_sales * 100), 1) if total_sales > 0 else 0.0
        gross_margin = round((total_item_profit / total_sales * 100), 1) if total_sales > 0 else 0.0

        return {
            "total_sales": round(total_sales, 2),
            "sales_count": sales_count,
            "total_purchases": round(total_purchases, 2),
            "purchases_count": purchases_count,
            "total_expenses": round(total_expenses, 2),
            "expenses_count": expenses_count,
            "total_item_profit": round(total_item_profit, 2),
            "gross_margin": gross_margin,
            "operating_profit": operating_profit,
            "net_profit": net_profit,
            "profit_margin": profit_margin,
            "is_profit": net_profit >= 0,
            "currency": Config.CURRENCY_SYMBOL
        }

    def get_financial_summary(self, period: str = "all") -> Dict[str, Any]:
        """
        Calculate financial metrics for requested period: 'today', 'month', or 'all'.
        """
        if period == "today":
            date_clause = "DATE(created_at) = DATE('now', 'localtime')"
        elif period == "month":
            date_clause = "strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now', 'localtime')"
        else:
            date_clause = ""

        return self._query_period_metrics(date_clause)

    def get_comprehensive_summary(self) -> Dict[str, Any]:
        """
        Return structured dictionary with Today, This Month, and All-Time financial breakdowns.
        """
        today_metrics = self.get_financial_summary("today")
        month_metrics = self.get_financial_summary("month")
        all_time_metrics = self.get_financial_summary("all")

        return {
            "today": today_metrics,
            "month": month_metrics,
            "all_time": all_time_metrics,
            "currency": Config.CURRENCY_SYMBOL
        }

    def get_chart_data(self) -> Dict[str, Any]:
        """
        Generate time-series and category breakdowns for Chart.js dashboard visualizers.
        Includes 14-day daily distribution and monthly summary.
        """
        # 1. Daily distribution (last 14 recorded days)
        daily_rows = query_db("""
            SELECT 
                DATE(created_at) as tx_date,
                SUM(CASE WHEN type = 'SALE' THEN total_amount ELSE 0 END) as sales,
                SUM(CASE WHEN type = 'PURCHASE' THEN total_amount ELSE 0 END) as purchases,
                SUM(CASE WHEN type = 'EXPENSE' THEN total_amount ELSE 0 END) as expenses,
                SUM(CASE WHEN type = 'SALE' THEN profit ELSE 0 END) as item_profit
            FROM transactions
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) ASC
            LIMIT 14
        """, db_path=self.db_path)

        dates = []
        sales_series = []
        purchases_series = []
        expenses_series = []
        profit_series = []

        for r in daily_rows:
            dates.append(r['tx_date'] or 'Today')
            sales_series.append(round(float(r['sales']), 2))
            purchases_series.append(round(float(r['purchases']), 2))
            expenses_series.append(round(float(r['expenses']), 2))
            profit_series.append(round(float(r['item_profit']), 2))

        # 2. Monthly distribution (last 6 months)
        monthly_rows = query_db("""
            SELECT 
                strftime('%Y-%m', created_at) as month_label,
                SUM(CASE WHEN type = 'SALE' THEN total_amount ELSE 0 END) as sales,
                SUM(CASE WHEN type = 'PURCHASE' THEN total_amount ELSE 0 END) as purchases,
                SUM(CASE WHEN type = 'EXPENSE' THEN total_amount ELSE 0 END) as expenses
            FROM transactions
            GROUP BY strftime('%Y-%m', created_at)
            ORDER BY month_label ASC
            LIMIT 6
        """, db_path=self.db_path)

        month_labels = []
        month_sales = []
        month_purchases = []
        month_expenses = []

        for m in monthly_rows:
            month_labels.append(m['month_label'] or 'Current Month')
            month_sales.append(round(float(m['sales']), 2))
            month_purchases.append(round(float(m['purchases']), 2))
            month_expenses.append(round(float(m['expenses']), 2))

        # 3. Category Breakdown for Sales
        cat_rows = query_db("""
            SELECT 
                COALESCE(category, 'General') as category_name,
                SUM(total_amount) as total
            FROM transactions
            WHERE type = 'SALE'
            GROUP BY category
            ORDER BY total DESC
        """, db_path=self.db_path)

        category_labels = [r['category_name'] for r in cat_rows]
        category_values = [round(float(r['total']), 2) for r in cat_rows]

        return {
            "timeline": {
                "labels": dates if dates else ["Today"],
                "sales": sales_series if sales_series else [0],
                "purchases": purchases_series if purchases_series else [0],
                "expenses": expenses_series if expenses_series else [0],
                "profit": profit_series if profit_series else [0]
            },
            "monthly": {
                "labels": month_labels if month_labels else ["This Month"],
                "sales": month_sales if month_sales else [0],
                "purchases": month_purchases if month_purchases else [0],
                "expenses": month_expenses if month_expenses else [0]
            },
            "categories": {
                "labels": category_labels if category_labels else ["General"],
                "values": category_values if category_values else [0]
            }
        }
