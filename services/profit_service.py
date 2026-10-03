"""
Financial Analytics and Profit & Loss Service.
Calculates sales revenue, purchase costs, overhead expenses, net profit,
and prepares structured metrics for dashboard charts.
"""
from typing import Dict, Any, List
from database.database import query_db
from config import Config

class ProfitService:
    def __init__(self, db_path: str = None):
        self.db_path = db_path

    def get_financial_summary(self) -> Dict[str, Any]:
        """
        Calculate key financial indicators:
        - Total Sales Revenue
        - Total Purchases Cost
        - Total Expenses
        - Total Direct Sales Profit (Item Margin)
        - Net Profit = Total Sales - Total Purchases - Total Expenses
        - Operating Profit = Direct Sales Profit - Total Expenses
        """
        # Aggregate Sales
        sales_row = query_db("""
            SELECT 
                COUNT(*) as count,
                COALESCE(SUM(total_amount), 0) as total_sales,
                COALESCE(SUM(profit), 0) as total_item_profit
            FROM transactions 
            WHERE type = 'SALE'
        """, one=True, db_path=self.db_path)

        # Aggregate Purchases
        purchases_row = query_db("""
            SELECT 
                COUNT(*) as count,
                COALESCE(SUM(total_amount), 0) as total_purchases
            FROM transactions 
            WHERE type = 'PURCHASE'
        """, one=True, db_path=self.db_path)

        # Aggregate Expenses
        expenses_row = query_db("""
            SELECT 
                COUNT(*) as count,
                COALESCE(SUM(total_amount), 0) as total_expenses
            FROM transactions 
            WHERE type = 'EXPENSE'
        """, one=True, db_path=self.db_path)

        total_sales = float(sales_row['total_sales'])
        sales_count = int(sales_row['count'])
        total_item_profit = float(sales_row['total_item_profit'])

        total_purchases = float(purchases_row['total_purchases'])
        purchases_count = int(purchases_row['count'])

        total_expenses = float(expenses_row['total_expenses'])
        expenses_count = int(expenses_row['count'])

        # Overall Net Profit: Total Sales Revenue - Total Purchase Cost - Total Expenses
        net_profit = round(total_sales - total_purchases - total_expenses, 2)
        
        # Operating Profit from Sold Goods: Gross Margin on Sold Goods - Operating Expenses
        operating_profit = round(total_item_profit - total_expenses, 2)

        # Profit Margin percentage
        profit_margin = round((net_profit / total_sales * 100), 1) if total_sales > 0 else 0.0

        return {
            "total_sales": round(total_sales, 2),
            "sales_count": sales_count,
            "total_purchases": round(total_purchases, 2),
            "purchases_count": purchases_count,
            "total_expenses": round(total_expenses, 2),
            "expenses_count": expenses_count,
            "total_item_profit": round(total_item_profit, 2),
            "net_profit": net_profit,
            "operating_profit": operating_profit,
            "profit_margin": profit_margin,
            "is_profit": net_profit >= 0,
            "currency": Config.CURRENCY_SYMBOL
        }

    def get_chart_data(self) -> Dict[str, Any]:
        """
        Generate time-series and category breakdowns for Chart.js dashboard visualizers.
        """
        # Daily distribution (last 7 days or recorded dates)
        daily_rows = query_db("""
            SELECT 
                DATE(created_at) as tx_date,
                SUM(CASE WHEN type = 'SALE' THEN total_amount ELSE 0 END) as sales,
                SUM(CASE WHEN type = 'PURCHASE' THEN total_amount ELSE 0 END) as purchases,
                SUM(CASE WHEN type = 'EXPENSE' THEN total_amount ELSE 0 END) as expenses
            FROM transactions
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) ASC
            LIMIT 14
        """, db_path=self.db_path)

        dates = []
        sales_series = []
        purchases_series = []
        expenses_series = []

        for r in daily_rows:
            dates.append(r['tx_date'] or 'Today')
            sales_series.append(float(r['sales']))
            purchases_series.append(float(r['purchases']))
            expenses_series.append(float(r['expenses']))

        # Category Breakdown for Sales
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
        category_values = [float(r['total']) for r in cat_rows]

        return {
            "timeline": {
                "labels": dates if dates else ["Today"],
                "sales": sales_series if sales_series else [0],
                "purchases": purchases_series if purchases_series else [0],
                "expenses": expenses_series if expenses_series else [0]
            },
            "categories": {
                "labels": category_labels if category_labels else ["General"],
                "values": category_values if category_values else [0]
            }
        }
