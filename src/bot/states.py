from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """States for user registration flow"""
    choosing_language = State()
    viewing_tutorial = State()


class ExpenseStates(StatesGroup):
    """States for expense creation flow"""
    waiting_for_amount = State()
    waiting_for_description = State()
    waiting_for_category = State()
    waiting_for_date = State()
    editing_transaction = State()
    confirming_save = State()


class ReceiptStates(StatesGroup):
    """States for receipt processing flow"""
    processing_image = State()
    confirming_data = State()
    editing_amount = State()
    editing_merchant = State()
    selecting_category = State()
    selecting_currency = State()
    confirming_duplicate = State()
    choosing_category = State()
    clarifying_amount = State()
    clarifying_category = State()
    asking_description = State()


class CategoryStates(StatesGroup):
    """States for category management"""
    viewing_categories = State()
    creating_category = State()
    entering_name_ru = State()
    entering_name_kz = State()
    selecting_icon = State()
    editing_category = State()
    confirming_delete = State()


class SearchStates(StatesGroup):
    """States for search functionality"""
    entering_query = State()
    viewing_results = State()
    filtering_results = State()


class ExportStates(StatesGroup):
    """States for data export"""
    selecting_period = State()
    selecting_format = State()
    selecting_categories = State()
    generating_export = State()


class SettingsStates(StatesGroup):
    """States for user settings"""
    main_menu = State()
    changing_language = State()
    changing_currency = State()
    changing_timezone = State()
    managing_notifications = State()
    managing_limits = State()
    confirming_clear_data = State()


class LimitStates(StatesGroup):
    """States for limit management"""
    viewing_limits = State()
    creating_limit = State()
    selecting_type = State()
    selecting_category = State()
    entering_amount = State()
    selecting_period = State()
    confirming_save = State()