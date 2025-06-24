import io
import logging
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional
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
from src.database.models import Transaction, Category, User, CompanyTransaction, CompanyCategory
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
    end_date: date,
    company_id: Optional[str] = None
) -> List[Transaction]:
    """Get transactions for period"""
    try:
        # Convert dates to datetime to include full day range
        from datetime import datetime, time
        start_datetime = datetime.combine(start_date, time.min)  # 00:00:00
        end_datetime = datetime.combine(end_date, time.max)      # 23:59:59.999999
        
        query = select(Transaction).options(joinedload(Transaction.category))
        
        if company_id:
            # Company transactions
            logger.info(f"[GET_PERIOD_DATA] Company mode: {company_id}, dates: {start_date} to {end_date}")
            query = query.join(
                CompanyTransaction,
                CompanyTransaction.transaction_id == Transaction.id
            ).where(
                and_(
                    CompanyTransaction.company_id == company_id,
                    CompanyTransaction.status == 'approved',
                    Transaction.transaction_date >= start_datetime,
                    Transaction.transaction_date <= end_datetime,
                    Transaction.is_deleted == False
                )
            )
        else:
            # Personal transactions only
            logger.info(f"[GET_PERIOD_DATA] Personal mode for user {user_id}, dates: {start_date} to {end_date}")
            query = query.where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.company_id == None,
                    Transaction.transaction_date >= start_datetime,
                    Transaction.transaction_date <= end_datetime,
                    Transaction.is_deleted == False
                )
            )
        
        query = query.order_by(Transaction.transaction_date)
        result = await session.execute(query)
        transactions = result.scalars().all()
        
        logger.info(f"[GET_PERIOD_DATA] Found {len(transactions)} transactions")
        for t in transactions[:3]:  # Log first 3 transactions
            logger.info(f"[GET_PERIOD_DATA] Transaction: {t.amount} {t.currency} on {t.transaction_date} company_id={t.company_id}")
        
        return transactions
    except Exception as e:
        logger.error(f"Error getting period data: {e}")
        # Return empty list on error to prevent crashes
        return []


async def generate_daily_chart(
    transactions: List[Transaction],
    locale: str,
    currency: str,
    title_key: str = 'stats.daily_expenses',
    company_name: Optional[str] = None
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
    if company_name:
        ax.set_title(f"{company_name} - {i18n.get(title_key, locale)}", fontsize=14, fontweight='bold')
    else:
        ax.set_title(i18n.get(title_key, locale), fontsize=14, fontweight='bold')
    
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


async def generate_monthly_trend_chart(
    transactions: List[Transaction],
    locale: str,
    currency: str,
    company_name: Optional[str] = None
) -> io.BytesIO:
    """Generate monthly trend chart for all-time view"""
    # Group by month
    monthly_data = {}
    for trans in transactions:
        month_key = trans.transaction_date.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = 0
        monthly_data[month_key] += float(trans.amount_primary)
    
    # Prepare data
    months = sorted(monthly_data.keys())
    amounts = [monthly_data[m] for m in months]
    
    # Convert month strings to dates for better formatting
    month_dates = []
    month_labels = []
    for m in months:
        try:
            month_date = datetime.strptime(m, '%Y-%m')
            month_dates.append(month_date)
            month_labels.append(month_date.strftime('%m/%y'))
        except:
            month_dates.append(m)
            month_labels.append(m)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Line chart with area fill
    line = ax.plot(range(len(months)), amounts, marker='o', linewidth=3, markersize=8, color='blue', alpha=0.8)
    ax.fill_between(range(len(months)), amounts, alpha=0.3, color='blue')
    
    # Add value labels on points
    for i, amount in enumerate(amounts):
        ax.text(i, amount, f'{amount:,.0f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # Format
    ax.set_xlabel("Месяц", fontsize=12)
    ax.set_ylabel(f"Сумма ({currency})", fontsize=12)
    if company_name:
        ax.set_title(f"{company_name} - Тренд расходов по месяцам", fontsize=14, fontweight='bold')
    else:
        ax.set_title("Тренд расходов по месяцам", fontsize=14, fontweight='bold')
    
    # Format x-axis
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(month_labels, rotation=45)
    
    # Grid
    ax.grid(True, alpha=0.3)
    
    # Average line
    if amounts:
        avg = sum(amounts) / len(amounts)
        ax.axhline(y=avg, color='red', linestyle='--', alpha=0.7, 
                   label=f"Среднее: {avg:,.0f} {currency}")
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
    currency: str,
    company_name: Optional[str] = None
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
    
    if company_name:
        ax.set_title(f"{company_name} - {i18n.get('stats.expenses_by_category', locale)}", 
                     fontsize=14, fontweight='bold', pad=20)
    else:
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
    period_days: int,
    company_name: Optional[str] = None
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
    if company_name:
        ax1.set_title(f"{company_name} - {i18n.get('stats.daily_trend', locale)}", fontsize=14, fontweight='bold')
    else:
        ax1.set_title(i18n.get('stats.daily_trend', locale), fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    
    # Cumulative expenses
    ax2.plot(dates, cumulative, linewidth=3, color='green', alpha=0.8)
    ax2.fill_between(dates, cumulative, alpha=0.3, color='green')
    
    # Format ax2
    ax2.set_xlabel(i18n.get('stats.date', locale), fontsize=12)
    ax2.set_ylabel(f"{i18n.get('stats.cumulative_amount', locale)} ({currency})", fontsize=12)
    if company_name:
        ax2.set_title(f"{company_name} - {i18n.get('stats.cumulative_trend', locale)}", fontsize=14, fontweight='bold')
    else:
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


async def report_day(message: Message):
    """Daily report with charts"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден. Пожалуйста, выполните /start")
            return
        
        locale = user.language_code
        currency = user.primary_currency
        
        # Check if in company mode
        company_name = None
        if user.active_company_id and user.active_company:
            company_name = user.active_company.name
            currency = user.active_company.primary_currency
        
        # Get today's data
        today = date.today()
        transactions = await get_period_data(session, user.id, today, today, user.active_company_id)
        
        # Debug info
        logger.info(f"[ANALYTICS] User {user.id}, active_company_id: {user.active_company_id}")
        logger.info(f"[ANALYTICS] Found {len(transactions)} transactions for {today}")
        
        if not transactions:
            # Check if there are any transactions at all for this user
            all_transactions = await get_period_data(session, user.id, date(2020, 1, 1), date(2030, 12, 31), user.active_company_id)
            debug_msg = f"📊 Нет данных за сегодня ({today.strftime('%d.%m.%Y')})\n\n"
            
            if all_transactions:
                debug_msg += f"💡 У вас есть {len(all_transactions)} транзакций за весь период.\n"
                debug_msg += "Попробуйте выбрать другой период: неделю или месяц."
            else:
                debug_msg += "💡 У вас пока нет ни одной транзакции.\n"
                if user.active_company_id:
                    debug_msg += "🏢 Вы в корпоративном режиме - добавьте расходы компании."
                else:
                    debug_msg += "👤 Вы в личном режиме - добавьте личные расходы."
            
            await message.answer(debug_msg, parse_mode="HTML")
            return
        
        # Calculate stats
        total = sum(float(t.amount_primary) for t in transactions)
        count = len(transactions)
        
        # Generate text report
        if company_name:
            report = f"📊 <b>{company_name}</b>\n"
            report += f"<b>{i18n.get('stats.today', locale)}</b> ({today.strftime('%d.%m.%Y')})\n\n"
        else:
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
            chart_buffer = await generate_category_pie_chart(transactions, locale, currency, company_name)
            await message.answer_photo(
                BufferedInputFile(chart_buffer.getvalue(), filename="daily_report.png"),
                caption=i18n.get("stats.chart_caption", locale)
            )


async def report_week(message: Message):
    """Weekly report with charts"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден. Пожалуйста, выполните /start")
            return
        
        locale = user.language_code
        currency = user.primary_currency
        
        # Check if in company mode
        company_name = None
        if user.active_company_id and user.active_company:
            company_name = user.active_company.name
            currency = user.active_company.primary_currency
        
        # Get week's data (last 7 days)
        today = date.today()
        week_start = today - timedelta(days=6)  # Last 7 days including today
        transactions = await get_period_data(session, user.id, week_start, today, user.active_company_id)
        
        if not transactions:
            await message.answer(
                i18n.get("stats.no_data", locale),
                parse_mode="HTML"
            )
            return
        
        # Calculate stats
        total = sum(float(t.amount_primary) for t in transactions)
        count = len(transactions)
        days_count = 7
        avg_daily = total / days_count
        
        # Generate text report
        if company_name:
            report = f"📈 <b>{company_name}</b>\n"
            report += f"<b>{i18n.get('stats.week', locale)} ({i18n.get('stats.last_7_days', locale)})</b>\n"
        else:
            report = f"📈 <b>{i18n.get('stats.week', locale)} ({i18n.get('stats.last_7_days', locale)})</b>\n"
        report += f"({week_start.strftime('%d.%m')} - {today.strftime('%d.%m.%Y')})\n\n"
        report += f"💰 {i18n.get('stats.total', locale)}: {expense_parser.format_amount(total, currency)}\n"
        report += f"📊 {i18n.get('stats.average_daily', locale)}: {expense_parser.format_amount(avg_daily, currency)}\n"
        report += f"📝 {i18n.get('stats.transactions', locale)}: {count}\n"
        
        await message.answer(report, parse_mode="HTML")
        
        # Generate and send charts
        # Daily chart for week
        daily_chart = await generate_daily_chart(
            transactions, locale, currency, 
            title_key='stats.weekly_expenses',
            company_name=company_name
        )
        await message.answer_photo(
            BufferedInputFile(daily_chart.getvalue(), filename="weekly_daily.png"),
            caption=i18n.get("stats.daily_breakdown", locale)
        )
        
        # Category pie chart - show even for 1 transaction
        if count >= 1:
            pie_chart = await generate_category_pie_chart(transactions, locale, currency, company_name)
            await message.answer_photo(
                BufferedInputFile(pie_chart.getvalue(), filename="weekly_categories.png"),
                caption=i18n.get("stats.category_breakdown", locale)
            )


async def report_month(message: Message):
    """Monthly report with charts"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден. Пожалуйста, выполните /start")
            return
        
        locale = user.language_code
        currency = user.primary_currency
        
        # Check if in company mode
        company_name = None
        if user.active_company_id and user.active_company:
            company_name = user.active_company.name
            currency = user.active_company.primary_currency
        
        # Get month's data (last 30 days)
        today = date.today()
        month_start = today - timedelta(days=29)  # Last 30 days including today
        transactions = await get_period_data(session, user.id, month_start, today, user.active_company_id)
        
        if not transactions:
            await message.answer(
                i18n.get("stats.no_data", locale),
                parse_mode="HTML"
            )
            return
        
        # Calculate stats
        total = sum(float(t.amount_primary) for t in transactions)
        count = len(transactions)
        days_count = 30
        avg_daily = total / days_count
        
        # Generate text report
        if company_name:
            report = f"📉 <b>{company_name}</b>\n"
            report += f"<b>{i18n.get('stats.month', locale)} ({i18n.get('stats.last_30_days_period', locale)})</b>\n"
        else:
            report = f"📉 <b>{i18n.get('stats.month', locale)} ({i18n.get('stats.last_30_days_period', locale)})</b>\n"
        report += f"({month_start.strftime('%d.%m')} - {today.strftime('%d.%m.%Y')})\n\n"
        report += f"💰 {i18n.get('stats.total', locale)}: {expense_parser.format_amount(total, currency)}\n"
        report += f"📊 {i18n.get('stats.average_daily', locale)}: {expense_parser.format_amount(avg_daily, currency)}\n"
        report += f"📝 {i18n.get('stats.transactions', locale)}: {count}\n"
        
        await message.answer(report, parse_mode="HTML")
        
        # Generate and send charts
        # Trend chart
        trend_chart = await generate_trend_chart(transactions, locale, currency, days_count, company_name)
        await message.answer_photo(
            BufferedInputFile(trend_chart.getvalue(), filename="monthly_trend.png"),
            caption=i18n.get("stats.expense_trend", locale)
        )
        
        # Category pie chart - show even for 1 transaction
        if count >= 1:
            pie_chart = await generate_category_pie_chart(transactions, locale, currency, company_name)
            await message.answer_photo(
                BufferedInputFile(pie_chart.getvalue(), filename="monthly_categories.png"),
                caption=i18n.get("stats.category_breakdown", locale)
            )


async def report_by_category(message: Message):
    """Category analysis report"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден. Пожалуйста, выполните /start")
            return
        
        locale = user.language_code
        currency = user.primary_currency
        
        # Check if in company mode
        company_name = None
        if user.active_company_id and user.active_company:
            company_name = user.active_company.name
            currency = user.active_company.primary_currency
        
        # Get last 30 days data
        today = date.today()
        start_date = today - timedelta(days=30)
        
        # Get category statistics based on mode
        if user.active_company_id:
            # Company mode - use company categories
            result = await session.execute(
                select(
                    CompanyCategory.id,
                    CompanyCategory.icon,
                    CompanyCategory.name_ru,
                    CompanyCategory.name_kz,
                    func.sum(Transaction.amount_primary).label('total'),
                    func.count(Transaction.id).label('count')
                )
                .join(Transaction, Transaction.category_id == CompanyCategory.id)
                .join(CompanyTransaction, CompanyTransaction.transaction_id == Transaction.id)
                .where(
                    and_(
                        CompanyTransaction.company_id == user.active_company_id,
                        CompanyTransaction.status == 'approved',
                        Transaction.transaction_date >= start_date,
                        Transaction.is_deleted == False
                    )
                )
                .group_by(CompanyCategory.id)
                .order_by(func.sum(Transaction.amount_primary).desc())
            )
        else:
            # Personal mode - use personal categories
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
                        Transaction.company_id == None,
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
        if company_name:
            report = f"💰 <b>{company_name}</b>\n"
            report += f"<b>{i18n.get('stats.category_analysis', locale)}</b>\n"
        else:
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
        transactions = await get_period_data(session, user.id, start_date, today, user.active_company_id)
        
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
            if company_name:
                ax.set_title(f"{company_name} - {i18n.get('stats.expenses_by_category', locale)}", 
                            fontsize=14, fontweight='bold')
            else:
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


async def report_all_time(message: Message):
    """All time report with comprehensive analytics"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден. Пожалуйста, выполните /start")
            return
        
        locale = user.language_code
        currency = user.primary_currency
        
        # Check if in company mode
        company_name = None
        if user.active_company_id and user.active_company:
            company_name = user.active_company.name
            currency = user.active_company.primary_currency
        
        # Get all-time data (from 2020 to 2030 to cover all possible dates)
        start_date = date(2020, 1, 1)
        end_date = date(2030, 12, 31)
        transactions = await get_period_data(session, user.id, start_date, end_date, user.active_company_id)
        
        if not transactions:
            no_data_msg = f"📋 <b>За все время</b>\n\n"
            no_data_msg += "💡 У вас пока нет ни одной транзакции.\n"
            if user.active_company_id:
                no_data_msg += "🏢 Вы в корпоративном режиме - добавьте расходы компании."
            else:
                no_data_msg += "👤 Вы в личном режиме - добавьте личные расходы."
            
            await message.answer(no_data_msg, parse_mode="HTML")
            return
        
        # Calculate comprehensive stats
        total = sum(float(t.amount_primary) for t in transactions)
        count = len(transactions)
        
        # Get date range
        first_date = min(t.transaction_date.date() for t in transactions)
        last_date = max(t.transaction_date.date() for t in transactions)
        days_range = (last_date - first_date).days + 1
        avg_daily = total / days_range if days_range > 0 else 0
        
        # Get monthly stats
        monthly_totals = {}
        for trans in transactions:
            month_key = trans.transaction_date.strftime('%Y-%m')
            if month_key not in monthly_totals:
                monthly_totals[month_key] = 0
            monthly_totals[month_key] += float(trans.amount_primary)
        
        # Generate text report
        if company_name:
            report = f"📋 <b>{company_name}</b>\n"
            report += f"<b>За все время</b>\n"
        else:
            report = f"📋 <b>За все время</b>\n"
        
        report += f"📅 {first_date.strftime('%d.%m.%Y')} - {last_date.strftime('%d.%m.%Y')}\n\n"
        report += f"💰 <b>Общая сумма</b>: {expense_parser.format_amount(total, currency)}\n"
        report += f"📝 <b>Транзакций</b>: {count}\n"
        report += f"📊 <b>Среднее в день</b>: {expense_parser.format_amount(avg_daily, currency)}\n"
        report += f"📈 <b>Активных месяцев</b>: {len(monthly_totals)}\n\n"
        
        # Top spending months
        if monthly_totals:
            top_months = sorted(monthly_totals.items(), key=lambda x: x[1], reverse=True)[:3]
            report += f"<b>Топ месяцы по расходам:</b>\n"
            for month, amount in top_months:
                try:
                    month_date = datetime.strptime(month, '%Y-%m')
                    month_name = month_date.strftime('%B %Y')
                    report += f"  {month_name}: {expense_parser.format_amount(amount, currency)}\n"
                except:
                    report += f"  {month}: {expense_parser.format_amount(amount, currency)}\n"
            report += "\n"
        
        # Category breakdown (top 5)
        category_totals = {}
        for trans in transactions:
            if trans.category:
                cat_name = f"{trans.category.icon} {trans.category.get_name(locale)}"
                if cat_name not in category_totals:
                    category_totals[cat_name] = 0
                category_totals[cat_name] += float(trans.amount_primary)
        
        if category_totals:
            top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]
            report += f"<b>Топ категории:</b>\n"
            for cat, amount in top_categories:
                percentage = (amount / total) * 100 if total > 0 else 0
                report += f"  {cat}: {expense_parser.format_amount(amount, currency)} ({percentage:.1f}%)\n"
        
        await message.answer(report, parse_mode="HTML")
        
        # Generate and send comprehensive charts
        # 1. Monthly trend chart
        if len(monthly_totals) > 1:
            monthly_trend_chart = await generate_monthly_trend_chart(
                transactions, locale, currency, company_name
            )
            await message.answer_photo(
                BufferedInputFile(monthly_trend_chart.getvalue(), filename="monthly_trend.png"),
                caption="📈 Тренд расходов по месяцам"
            )
        
        # 2. Category pie chart
        if len(category_totals) > 1:
            pie_chart = await generate_category_pie_chart(transactions, locale, currency, company_name)
            await message.answer_photo(
                BufferedInputFile(pie_chart.getvalue(), filename="all_time_categories.png"),
                caption="🥧 Распределение по категориям за все время"
            )