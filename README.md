# Expanse Telegram Bot

Telegram бот для учета личных расходов с распознаванием чеков и поддержкой мультивалютности.

## Основные возможности

- 📸 Распознавание чеков с фотографий (OCR)
- 💰 Учет расходов по категориям
- 📊 Детальная статистика и аналитика
- 💱 Автоматическая конвертация валют
- 🌐 Поддержка русского и казахского языков
- 📤 Экспорт данных в Excel, CSV, PDF
- 🎯 Установка лимитов трат
- 🔔 Умные уведомления

## Технологии

- **Python 3.10+**
- **aiogram 3.x** - Telegram Bot API
- **SQLAlchemy** - ORM
- **MySQL** - База данных (AWS RDS)
- **Redis** - Кеширование
- **Tesseract + EasyOCR** - Распознавание текста
- **Docker** - Контейнеризация

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/yourusername/expanse-telegram-bot.git
cd expanse-telegram-bot
```

### 2. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните необходимые значения:

```bash
cp .env.example .env
```

Основные переменные:
- `BOT_TOKEN` - токен вашего бота от @BotFather
- `DB_*` - параметры подключения к MySQL
- `REDIS_*` - параметры Redis
- API ключи для курсов валют

### 5. Инициализация базы данных

```bash
mysql -h expanse.cde42ec8m1u7.eu-north-1.rds.amazonaws.com -u admin -p < database/schema.sql
```

### 6. Запуск бота

```bash
python main.py
```

## Hot Reload (Автообновление)

Бот поддерживает автоматическую перезагрузку кода без остановки работы!

### Включение Hot Reload

1. В файле `.env` установите:
```bash
ENABLE_HOT_RELOAD=true
APP_ENV=development
```

2. Запустите бот с поддержкой hot reload:
```bash
python main_hot_reload.py
```

Теперь при изменении файлов в папках `src/bot/handlers` и `src/bot/keyboards` изменения применятся автоматически без перезапуска бота!

### Динамическое обновление контента

Вы можете изменять тексты и клавиатуры без изменения кода:

1. Отредактируйте файл `dynamic_config.json`
2. Или разместите конфиг на внешнем сервере и укажите URL:
```bash
DYNAMIC_CONFIG_URL=https://your-server.com/bot-config.json
```

Бот будет проверять обновления каждые 60 секунд.

## Использование Docker

### Сборка образа

```bash
docker build -t expanse-bot .
```

### Запуск контейнера

```bash
docker run -d --name expanse-bot --env-file .env expanse-bot
```

## Структура проекта

```
expanse-telegram-bot/
├── src/
│   ├── bot/           # Хендлеры и клавиатуры
│   ├── core/          # Конфигурация
│   ├── database/      # Модели и работа с БД
│   ├── services/      # Бизнес-логика
│   └── utils/         # Утилиты
├── locales/           # Файлы локализации
├── database/          # SQL скрипты
├── tests/             # Тесты
└── main.py           # Точка входа
```

## Команды бота

- `/start` - Начать работу с ботом
- `/help` - Помощь и инструкции
- `/stats` - Статистика расходов
- `/categories` - Управление категориями
- `/export` - Экспорт данных
- `/settings` - Настройки
- `/last` - Последние траты
- `/today` - Траты за сегодня
- `/rates` - Курсы валют
- `/convert` - Конвертер валют

## Примеры использования

### Ручной ввод расхода
```
500 кофе
1200 продукты в магните
50 автобус
```

### Загрузка чека
Просто отправьте фото чека, и бот автоматически распознает:
- Сумму покупки
- Дату операции
- Название магазина

### Конвертация валют
```
/convert 100 USD to KZT
```

## Разработка

### Запуск тестов

```bash
pytest
```

### Форматирование кода

```bash
black src/
flake8 src/
```

### Проверка типов

```bash
mypy src/
```

## Лицензия

MIT

## Поддержка

Если у вас есть вопросы или предложения, создайте issue в репозитории.