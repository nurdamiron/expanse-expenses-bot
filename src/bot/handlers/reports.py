import io
import logging
from datetime import datetime, date, timedelta
from typing import List, Tuple
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties
import seaborn as sns
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.database import get_session
from src.database.models import Transaction, Category, User
from src.services.user import UserService
from src.services.transaction import TransactionService
from src.utils.i18n import i18n
from src.utils.text_parser import ExpenseParser

router = Router()
logger = logging.getLogger(__name__)
user_service = UserService()
transaction_service = TransactionService()
expense_parser = ExpenseParser()

# Set style for charts
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


async def get_period_data(
    session: AsyncSession,
    user_id: int,
    start_date: date,
    end_date: date
) -> List[Transaction]:
    """Get transactions for period"""
    try:
        result = await session.execute(
            select(Transaction)
            .options(joinedload(Transaction.category))  # Eager load category
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                    Transaction.is_deleted == False
                )
            )
            .order_by(Transaction.transaction_date)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting period data: {e}")
        # Return empty list on error to prevent crashes
        return []


async def generate_daily_chart(
    transactions: List[Transaction],
    locale: str,
    currency: str
) -> io.BytesIO:
    """Generate daily expenses chart"""
    # Group by date
    daily_data = {}
    for trans in transactions:
        date_key = trans.transaction_date.date()
        if date_key not in daily_data:
            daily_data[date_key] = 0
        daily_data[date_key] += float(trans.amount_primary)
    
    # Prepare data
    dates = sorted(daily_data.keys())
    amounts = [daily_data[d] for d in dates]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Bar chart
    bars = ax.bar(dates, amounts, color='skyblue', edgecolor='navy', alpha=0.7)
    
    # Add value labels on bars
    for bar, amount in zip(bars, amounts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{amount:,.0f}',
                ha='center', va='bottom', fontsize=9)
    
    # Format
    ax.set_xlabel(i18n.get('stats.date', locale), fontsize=12)
    ax.set_ylabel(f"{i18n.get('stats.amount', locale)} ({currency})", fontsize=12)
    ax.set_title(i18n.get('stats.daily_expenses', locale), fontsize=14, fontweight='bold')
    
    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.xticks(rotation=45)
    
    # Grid
    ax.grid(True, alpha=0.3)
    
    # Average line
    if amounts:
        avg = sum(amounts) / len(amounts)
        ax.axhline(y=avg, color='red', linestyle='--', alpha=0.7, 
                   label=f"{i18n.get('stats.average', locale)}: {avg:,.0f} {currency}")
        ax.legend()
    
    plt.tight_layout()
    
    # Save to buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    plt.close()
    
    return buffer


async def generate_category_pie_chart(
    transactions: List[Transaction],
    locale: str,
    currency: str
) -> io.BytesIO:
    """Generate category pie chart"""
    # Group by category
    category_data = {}
    category_names = {}
    
    for trans in transactions:
        if trans.category:
            cat_id = trans.category_id
            if cat_id not in category_data:
                category_data[cat_id] = 0
                category_names[cat_id] = f"{trans.category.icon} {trans.category.get_name(locale)}"
            category_data[cat_id] += float(trans.amount_primary)
    
    # Prepare data
    labels = []
    sizes = []
    colors = []
    
    # Sort by amount
    sorted_cats = sorted(category_data.items(), key=lambda x: x[1], reverse=True)
    
    for cat_id, amount in sorted_cats:
        labels.append(f"{category_names[cat_id]}\n{amount:,.0f} {currency}")
        sizes.append(amount)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Pie chart
    wedges, texts, autotexts = ax.pie(
        sizes, 
        labels=labels, 
        autopct='%1.1f%%',
        startangle=90,
        colors=sns.color_palette("husl", len(sizes))
    )
    
    # Format
    for text in texts:
        text.set_fontsize(10)
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(10)
        autotext.set_weight('bold')
    
    ax.set_title(i18n.get('stats.expenses_by_category', locale), 
                 fontsize=14, fontweight='bold', pad=20)
    
    # Equal aspect ratio
    ax.axis('equal')
    
    plt.tight_layout()
    
    # Save to buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    plt.close()
    
    return buffer


async def generate_trend_chart(
    transactions: List[Transaction],
    locale: str,
    currency: str,
    period_days: int
) -> io.BytesIO:
    """Generate trend chart over time"""
    # Group by date
    daily_data = {}
    for trans in transactions:
        date_key = trans.transaction_date.date()
        if date_key not in daily_data:
            daily_data[date_key] = 0
        daily_data[date_key] += float(trans.amount_primary)
    
    # Fill missing dates with 0
    if daily_data:
        start_date = min(daily_data.keys())
        end_date = max(daily_data.keys())
        current_date = start_date
        while current_date <= end_date:
            if current_date not in daily_data:
                daily_data[current_date] = 0
            current_date += timedelta(days=1)
    
    # Prepare data
    dates = sorted(daily_data.keys())
    amounts = [daily_data[d] for d in dates]
    
    # Calculate cumulative
    cumulative = []
    total = 0
    for amount in amounts:
        total += amount
        cumulative.append(total)
    
    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Daily expenses line chart
    ax1.plot(dates, amounts, marker='o', linewidth=2, markersize=6, color='blue', alpha=0.7)
    ax1.fill_between(dates, amounts, alpha=0.3, color='blue')
    
    # Format ax1
    ax1.set_xlabel(i18n.get('stats.date', locale), fontsize=12)
    ax1.set_ylabel(f"{i18n.get('stats.daily_amount', locale)} ({currency})", fontsize=12)
    ax1.set_title(i18n.get('stats.daily_trend', locale), fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    
    # Cumulative expenses
    ax2.plot(dates, cumulative, linewidth=3, color='green', alpha=0.8)
    ax2.fill_between(dates, cumulative, alpha=0.3, color='green')
    
    # Format ax2
    ax2.set_xlabel(i18n.get('stats.date', locale), fontsize=12)
    ax2.set_ylabel(f"{i18n.get('stats.cumulative_amount', locale)} ({currency})", fontsize=12)
    ax2.set_title(i18n.get('stats.cumulative_trend', locale), fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    
    # Rotate x labels
    for ax in [ax1, ax2]:
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    
    # Save to buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    plt.close()
    
    return buffer


@router.message(F.text.startswith("📊"))
async def report_day(message: Message):
    """Daily report with charts"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        currency = user.primary_currency
        
        # Get today's data
        today = date.today()
        transactions = await get_period_data(session, user.id, today, today)
        
        if not transactions:
            await message.answer(
                i18n.get("stats.no_data", locale),
                parse_mode="HTML"
            )
            return
        
        # Calculate stats
        total = sum(float(t.amount_primary) for t in transactions)
        count = len(transactions)
        
        # Generate text report
        report = f"📊 <b>{i18n.get('stats.today', locale)}</b> ({today.strftime('%d.%m.%Y')})\n\n"
        report += f"💰 {i18n.get('stats.total', locale)}: {expense_parser.format_amount(total, currency)}\n"
        report += f"📝 {i18n.get('stats.transactions', locale)}: {count}\n\n"
        
        # Category breakdown
        category_totals = {}
        for trans in transactions:
            if trans.category:
                cat_name = f"{trans.category.icon} {trans.category.get_name(locale)}"
                if cat_name not in category_totals:
                    category_totals[cat_name] = 0
                category_totals[cat_name] += float(trans.amount_primary)
        
        if category_totals:
            report += f"📂 {i18n.get('stats.by_categories', locale)}:\n"
            for cat, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
                report += f"  {cat}: {expense_parser.format_amount(amount, currency)}\n"
        
        await message.answer(report, parse_mode="HTML")
        
        # Generate and send chart if more than 1 transaction
        if count > 1:
            chart_buffer = await generate_category_pie_chart(transactions, locale, currency)
            await message.answer_photo(
                BufferedInputFile(chart_buffer.getvalue(), filename="daily_report.png"),
                caption=i18n.get("stats.chart_caption", locale)
            )


@router.message(F.text.startswith("📈"))
async def report_week(message: Message):
    """Weekly report with charts"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        currency = user.primary_currency
        
        # Get week's data
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        transactions = await get_period_data(session, user.id, week_start, today)
        
        if not transactions:
            await message.answer(
                i18n.get("stats.no_data", locale),
                parse_mode="HTML"
            )
            return
        
        # Calculate stats
        total = sum(float(t.amount_primary) for t in transactions)
        count = len(transactions)
        avg_daily = total / 7
        
        # Generate text report
        report = f"📈 <b>{i18n.get('stats.week', locale)}</b> "
        report += f"({week_start.strftime('%d.%m')} - {today.strftime('%d.%m.%Y')})\n\n"
        report += f"💰 {i18n.get('stats.total', locale)}: {expense_parser.format_amount(total, currency)}\n"
        report += f"📊 {i18n.get('stats.average_daily', locale)}: {expense_parser.format_amount(avg_daily, currency)}\n"
        report += f"📝 {i18n.get('stats.transactions', locale)}: {count}\n"
        
        await message.answer(report, parse_mode="HTML")
        
        # Generate and send charts
        # Daily chart
        daily_chart = await generate_daily_chart(transactions, locale, currency)
        await message.answer_photo(
            BufferedInputFile(daily_chart.getvalue(), filename="weekly_daily.png"),
            caption=i18n.get("stats.daily_breakdown", locale)
        )
        
        # Category pie chart
        if count > 1:
            pie_chart = await generate_category_pie_chart(transactions, locale, currency)
            await message.answer_photo(
                BufferedInputFile(pie_chart.getvalue(), filename="weekly_categories.png"),
                caption=i18n.get("stats.category_breakdown", locale)
            )


@router.message(F.text.startswith("📉"))
async def report_month(message: Message):
    """Monthly report with charts"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        currency = user.primary_currency
        
        # Get month's data
        today = date.today()
        month_start = date(today.year, today.month, 1)
        transactions = await get_period_data(session, user.id, month_start, today)
        
        if not transactions:
            await message.answer(
                i18n.get("stats.no_data", locale),
                parse_mode="HTML"
            )
            return
        
        # Calculate stats
        total = sum(float(t.amount_primary) for t in transactions)
        count = len(transactions)
        days_in_month = (today - month_start).days + 1
        avg_daily = total / days_in_month
        
        # Generate text report
        report = f"📉 <b>{i18n.get('stats.month', locale)}</b> "
        report += f"({month_start.strftime('%B %Y')})\n\n"
        report += f"💰 {i18n.get('stats.total', locale)}: {expense_parser.format_amount(total, currency)}\n"
        report += f"📊 {i18n.get('stats.average_daily', locale)}: {expense_parser.format_amount(avg_daily, currency)}\n"
        report += f"📝 {i18n.get('stats.transactions', locale)}: {count}\n"
        
        await message.answer(report, parse_mode="HTML")
        
        # Generate and send charts
        # Trend chart
        trend_chart = await generate_trend_chart(transactions, locale, currency, days_in_month)
        await message.answer_photo(
            BufferedInputFile(trend_chart.getvalue(), filename="monthly_trend.png"),
            caption=i18n.get("stats.expense_trend", locale)
        )
        
        # Category pie chart
        if count > 1:
            pie_chart = await generate_category_pie_chart(transactions, locale, currency)
            await message.answer_photo(
                BufferedInputFile(pie_chart.getvalue(), filename="monthly_categories.png"),
                caption=i18n.get("stats.category_breakdown", locale)
            )


@router.message(F.text.startswith("💰"))
async def report_by_category(message: Message):
    """Category analysis report"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        currency = user.primary_currency
        
        # Get last 30 days data
        today = date.today()
        start_date = today - timedelta(days=30)
        
        # Get category statistics
        result = await session.execute(
            select(
                Category.id,
                Category.icon,
                Category.name_ru,
                Category.name_kz,
                func.sum(Transaction.amount_primary).label('total'),
                func.count(Transaction.id).label('count')
            )
            .join(Transaction, Transaction.category_id == Category.id)
            .where(
                and_(
                    Transaction.user_id == user.id,
                    Transaction.transaction_date >= start_date,
                    Transaction.is_deleted == False
                )
            )
            .group_by(Category.id)
            .order_by(func.sum(Transaction.amount_primary).desc())
        )
        
        category_stats = result.all()
        
        if not category_stats:
            await message.answer(
                i18n.get("stats.no_data", locale),
                parse_mode="HTML"
            )
            return
        
        # Generate report
        report = f"💰 <b>{i18n.get('stats.category_analysis', locale)}</b>\n"
        report += f"📅 {i18n.get('stats.last_30_days', locale)}\n\n"
        
        total_all = sum(stat.total for stat in category_stats)
        
        for stat in category_stats:
            cat_name = stat.name_ru if locale == 'ru' else stat.name_kz
            percentage = (stat.total / total_all) * 100 if total_all > 0 else 0
            
            report += f"{stat.icon} <b>{cat_name}</b>\n"
            report += f"  💵 {expense_parser.format_amount(stat.total, currency)}"
            report += f" ({percentage:.1f}%)\n"
            report += f"  📝 {i18n.get('stats.transactions', locale)}: {stat.count}\n"
            report += f"  📊 {i18n.get('stats.average', locale)}: "
            report += f"{expense_parser.format_amount(stat.total / stat.count if stat.count > 0 else 0, currency)}\n\n"
        
        report += f"💰 <b>{i18n.get('stats.total', locale)}: "
        report += f"{expense_parser.format_amount(total_all, currency)}</b>"
        
        await message.answer(report, parse_mode="HTML")
        
        # Get transactions for chart
        transactions = await get_period_data(session, user.id, start_date, today)
        
        if len(transactions) > 1:
            # Generate category comparison chart
            fig, ax = plt.subplots(figsize=(10, 8))
            
            categories = []
            amounts = []
            
            for stat in category_stats:
                cat_name = stat.name_ru if locale == 'ru' else stat.name_kz
                categories.append(f"{stat.icon} {cat_name}")
                amounts.append(float(stat.total))
            
            # Horizontal bar chart
            bars = ax.barh(categories, amounts, color=sns.color_palette("husl", len(categories)))
            
            # Add values on bars
            for i, (bar, amount) in enumerate(zip(bars, amounts)):
                ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2,
                       f' {amount:,.0f} {currency}',
                       ha='left', va='center', fontsize=10)
            
            ax.set_xlabel(f"{i18n.get('stats.amount', locale)} ({currency})", fontsize=12)
            ax.set_title(i18n.get('stats.expenses_by_category', locale), 
                        fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='x')
            
            plt.tight_layout()
            
            # Save to buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            plt.close()
            
            await message.answer_photo(
                BufferedInputFile(buffer.getvalue(), filename="category_analysis.png"),
                caption=i18n.get("stats.category_comparison", locale)
            )