# 💰 Expanse Expenses Bot

Мощный Telegram-бот для учета личных расходов с поддержкой искусственного интеллекта, OCR распознавания чеков и многоязычным интерфейсом.

## ✨ Основные возможности

### 🤖 AI-Powered Функции
- **🧠 Умное распознавание текста**: Просто напишите "обед 2500" и бот автоматически определит это как расход на еду
- **👁️ OpenAI Vision**: Использует GPT-4 Vision для точного анализа чеков и документов
- **🔤 OCR распознавание**: Tesseract + OpenCV для извлечения текста с изображений
- **🎯 Автоматическая категоризация**: ИИ анализирует контекст и назначает подходящую категорию
- **🔍 Обнаружение дубликатов**: Защита от случайного дублирования транзакций

### 💳 Управление расходами
- **📝 Ручной ввод** с выбором категории и описанием
- **📸 Фотографии чеков** с автоматическим извлечением данных
- **📄 Документы** (PDF, Word, изображения) с OCR обработкой
- **✏️ Редактирование транзакций** после создания
- **🔄 Обработка конкурентных запросов** без ошибок

### 🌍 Мультивалютная поддержка
- **15+ валют**: KZT, RUB, USD, EUR, CNY, KRW, TRY, MYR и другие
- **💱 Автоматическая конвертация** по реальным курсам
- **🔄 Кеширование курсов**: Оптимизированная система для быстрой работы
- **💰 Умное определение валют**: Распознает символы валют в тексте

### 📊 Аналитика и отчеты
- **📈 Детальная аналитика**: По дням, неделям, месяцам
- **🏷️ Категоризированные отчеты**: Разбивка по категориям расходов
- **📤 Экспорт данных**: CSV и Excel форматы
- **📱 Ежедневная сводка**: Показ потраченной суммы за день

### 🏷️ Гибкая система категорий
- **🍽️ Еда и рестораны** - Все расходы на питание
- **🚗 Транспорт** - Такси, автобус, бензин
- **🏠 Дом и коммунальные** - ЖКХ, интернет, мобильная связь
- **🛒 Покупки** - Одежда, техника, товары для дома
- **💊 Здоровье и медицина** - Аптеки, врачи, анализы
- **🎬 Развлечения** - Кино, театр, игры
- **📚 Образование** - Книги, курсы, обучение
- **🕌 Пожертвования** - Садака, мечети, благотворительность
- **⚡ Другое** - Прочие расходы

### 🌐 Многоязычность
- **🇷🇺 Русский язык**: Полная локализация
- **🇰🇿 Казахский язык**: Полная локализация
- **🔄 Динамическое переключение**: Смена языка в настройках

## 🛠️ Технический стек

### Backend
- **Python 3.11+**: Основной язык программирования
- **aiogram 3.x**: Telegram Bot API фреймворк
- **SQLAlchemy 2.x**: ORM для работы с базой данных
- **Alembic**: Миграции базы данных
- **SQLite**: Локальная база данных
- **asyncio**: Асинхронное программирование

### AI & OCR
- **OpenAI GPT-4**: Анализ текста и изображений
- **Tesseract OCR**: Локальное распознавание текста
- **OpenCV**: Обработка изображений
- **PIL/Pillow**: Работа с изображениями

### Cloud Services
- **AWS S3**: Хранение изображений чеков
- **Currency API**: Реальные курсы валют
- **AWS EC2**: Deployment платформа

## 📦 Установка и запуск

### Предварительные требования
- **Python 3.11** или выше
- **Telegram Bot Token** от @BotFather
- **OpenAI API Key** (опционально, для AI функций)
- **Tesseract OCR** (опционально, для локального OCR)

### 1. Клонирование репозитория
```bash
git clone https://github.com/yourusername/expanse-expenses-bot.git
cd expanse-expenses-bot
```

### 2. Установка зависимостей
```bash
# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate.bat  # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 3. Установка Tesseract OCR (опционально)
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng

# macOS (с Homebrew)
brew install tesseract tesseract-lang

# Windows
# Скачайте с https://github.com/UB-Mannheim/tesseract/wiki
```

### 4. Настройка переменных окружения
Создайте файл `.env` в корне проекта:

```env
# ===== TELEGRAM BOT =====
TELEGRAM_BOT_TOKEN=your_bot_token_here

# ===== DATABASE =====
DATABASE_URL=sqlite:///./expanse_bot.db

# ===== OPENAI (OPTIONAL) =====
OPENAI_API_KEY=your_openai_api_key_here
USE_OPENAI_VISION=true

# ===== OCR SETTINGS =====
ENABLE_OCR=true
TESSERACT_PATH=/usr/bin/tesseract
TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# ===== CURRENCY CONVERSION =====
ENABLE_CURRENCY_CONVERSION=true
CURRENCY_API_KEY=your_currency_api_key_here

# ===== AWS S3 (OPTIONAL) =====
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_bucket_name
ENABLE_S3_STORAGE=false

# ===== LOGGING =====
LOG_LEVEL=INFO
LOG_FILE=bot.log

# ===== SECURITY =====
SECRET_KEY=your_secret_key_here
```

### 5. Инициализация базы данных
```bash
# Создание и применение миграций
python -m alembic upgrade head
```

### 6. Запуск бота
```bash
# Запуск в режиме разработки
python -m src.main

# Или с дополнительным логированием
python -m src.main --log-level DEBUG
```

## 🚀 Деплой на AWS EC2

### 1. Подготовка EC2 инстанса
```bash
# Подключение к EC2
ssh -i your-key.pem ubuntu@your-ec2-instance

# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python и зависимостей
sudo apt install python3.11 python3.11-pip python3.11-venv git -y

# Установка Tesseract
sudo apt install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng -y
```

### 2. Развертывание проекта
```bash
# Клонирование
git clone https://github.com/yourusername/expanse-expenses-bot.git
cd expanse-expenses-bot

# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка .env файла
nano .env  # Настройте ваши переменные

# Инициализация базы данных
python -m alembic upgrade head
```

### 3. Настройка systemd сервиса
```bash
sudo nano /etc/systemd/system/expanse-bot.service
```

```ini
[Unit]
Description=Expanse Expenses Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/expanse-expenses-bot
Environment=PATH=/home/ubuntu/expanse-expenses-bot/venv/bin
ExecStart=/home/ubuntu/expanse-expenses-bot/venv/bin/python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Активация сервиса
sudo systemctl daemon-reload
sudo systemctl enable expanse-bot.service
sudo systemctl start expanse-bot.service

# Проверка статуса
sudo systemctl status expanse-bot.service
```

## 📱 Использование бота

### Базовые команды
- **`/start`** - Регистрация и начало работы с ботом
- **`/help`** - Подробная справка по всем функциям
- **`/analytics`** - Просмотр детальной аналитики расходов
- **`/categories`** - Управление категориями расходов
- **`/export`** - Экспорт данных в различных форматах
- **`/settings`** - Настройки языка, валюты, часового пояса

### 💡 Способы добавления расходов

#### 1. 🧠 Умные текстовые сообщения (AI)
Просто отправьте сообщение - ИИ сам все поймет:
```
обед 2500                    → 🍽️ Еда, 2500 KZT
такси 800 рублей            → 🚗 Транспорт, 800 RUB  
кофе в старбакс 1200        → 🍽️ Еда, 1200 KZT
лекарства в аптеке 3000     → 💊 Здоровье, 3000 KZT
садака в мечети 5000        → 🕌 Пожертвования, 5000 KZT
интернет 12000 тенге        → 🏠 Коммунальные, 12000 KZT
```

#### 2. 📸 Фотографии чеков (OCR + AI Vision)
- Сделайте фото любого чека
- Бот автоматически распознает:
  - 💰 Сумму покупки
  - 📅 Дату и время
  - 🏪 Название магазина
  - 🏷️ Категорию (еда, транспорт и т.д.)
  - 💱 Валюту
- Подтвердите или отредактируйте данные одним нажатием

#### 3. 📄 Документы (PDF, Word, изображения)
- Отправьте документ с чеком
- Поддерживает форматы: PDF, DOCX, DOC, JPG, PNG, WebP
- Автоматическое извлечение данных через OCR
- Умная обработка многостраничных документов

#### 4. ✋ Ручной ввод через меню
- Нажмите **"💰 Добавить расход"**
- Введите сумму (например: `2500` или `25.50`)
- Выберите категорию из списка
- Добавьте описание (опционально)
- Выберите дату (по умолчанию - сегодня)

### 📊 Просмотр аналитики

#### Быстрые отчеты
- **📊 Аналитика** → Основное меню аналитики
- **📈 За сегодня** → Расходы за текущий день
- **📅 За неделю** → Расходы за последние 7 дней  
- **📆 За месяц** → Расходы за текущий месяц
- **🗓️ За все время** → Полная история расходов

#### Детальная аналитика
- **🏷️ По категориям** → Разбивка расходов по категориям с процентами
- **💱 По валютам** → Расходы в разных валютах
- **📈 Тренды** → Графики изменения расходов по времени
- **🔍 Поиск** → Поиск транзакций по сумме, описанию, дате

### ⚙️ Настройки

#### Персонализация
- **🌐 Язык интерфейса** → Русский / Қазақша
- **💱 Основная валюта** → KZT, RUB, USD, EUR и др.
- **🕐 Часовой пояс** → Для корректного отображения времени
- **🔔 Уведомления** → Настройка push-уведомлений

#### Управление категориями
- **➕ Создать категорию** → Добавить свою категорию с иконкой
- **✏️ Редактировать** → Изменить название и иконку
- **🗑️ Удалить** → Удалить неиспользуемые категории
- **🔄 Восстановить** → Восстановить стандартные категории

### 📤 Экспорт данных
- **📊 Excel (.xlsx)** → Подробные таблицы с формулами
- **📄 CSV** → Для импорта в другие системы
- **📋 Текстовый отчет** → Для отправки или печати
- **🗓️ За период** → Выбор конкретного диапазона дат
- **🏷️ По категориям** → Фильтрация по выбранным категориям

## 📁 Структура проекта

```
expanse-expenses-bot/
├── 📁 src/                          # Исходный код
│   ├── 📁 bot/                      # Telegram Bot логика
│   │   ├── 📁 handlers/             # Обработчики сообщений
│   │   │   ├── 🐍 __init__.py       # Регистрация роутеров
│   │   │   ├── 🐍 start.py          # Команда /start и регистрация
│   │   │   ├── 🐍 photo.py          # Обработка фотографий чеков
│   │   │   ├── 🐍 document.py       # Обработка документов
│   │   │   ├── 🐍 text_expense.py   # AI парсинг текстовых сообщений
│   │   │   ├── 🐍 manual_input.py   # Ручной ввод расходов
│   │   │   ├── 🐍 analytics.py      # Аналитика и отчеты
│   │   │   ├── 🐍 categories.py     # Управление категориями
│   │   │   ├── 🐍 settings.py       # Настройки пользователя
│   │   │   └── 🐍 export.py         # Экспорт данных
│   │   ├── 📁 keyboards/            # Клавиатуры
│   │   │   ├── 🐍 main.py           # Основные клавиатуры
│   │   │   ├── 🐍 categories.py     # Клавиатуры категорий
│   │   │   ├── 🐍 analytics.py      # Клавиатуры аналитики
│   │   │   └── 🐍 settings.py       # Клавиатуры настроек
│   │   └── 🐍 states.py             # FSM состояния
│   ├── 📁 core/                     # Конфигурация
│   │   ├── 🐍 config.py             # Настройки приложения
│   │   └── 🐍 logging.py            # Настройки логирования
│   ├── 📁 database/                 # База данных
│   │   ├── 🐍 __init__.py           # Подключение к БД
│   │   ├── 🐍 base.py               # Базовые классы
│   │   └── 🐍 models.py             # Модели данных
│   ├── 📁 services/                 # Бизнес-логика
│   │   ├── 🐍 user.py               # Сервис пользователей
│   │   ├── 🐍 transaction.py        # Сервис транзакций
│   │   ├── 🐍 category.py           # Сервис категорий
│   │   ├── 🐍 currency.py           # Сервис валют
│   │   ├── 🐍 ocr.py                # OCR сервис (Tesseract)
│   │   ├── 🐍 ocr_openai.py         # OpenAI Vision сервис
│   │   ├── 🐍 openai_service.py     # OpenAI API интеграция
│   │   ├── 🐍 s3_storage.py         # AWS S3 сервис
│   │   └── 🐍 duplicate_detector.py # Детектор дубликатов
│   ├── 📁 utils/                    # Утилиты
│   │   ├── 🐍 text_parser.py        # Парсинг текста
│   │   ├── 🐍 caption_parser.py     # Парсинг подписей
│   │   ├── 🐍 clarification.py      # Уточнения данных
│   │   └── 🐍 i18n.py               # Интернационализация
│   └── 🐍 main.py                   # Точка входа
├── 📁 locales/                      # Локализация
│   ├── 🌐 ru.yaml                   # Русский язык
│   └── 🌐 kz.yaml                   # Казахский язык
├── 📁 alembic/                      # Миграции БД
│   ├── 🐍 env.py                    # Конфигурация Alembic
│   └── 📁 versions/                 # Файлы миграций
├── 📁 tests/                        # Тесты
│   ├── 📁 unit/                     # Модульные тесты
│   ├── 📁 integration/              # Интеграционные тесты
│   └── 📁 fixtures/                 # Тестовые данные
├── 📄 requirements.txt              # Python зависимости
├── 📄 alembic.ini                   # Конфигурация миграций
├── 📄 .env.example                  # Пример переменных окружения
├── 📄 .gitignore                    # Git игнорируемые файлы
└── 📄 README.md                     # Документация (этот файл)
```

## 🧪 Тестирование

### Запуск тестов
```bash
# Все тесты
pytest

# С покрытием кода
pytest --cov=src --cov-report=html

# Только модульные тесты
pytest tests/unit/

# Только интеграционные тесты
pytest tests/integration/

# Тесты OCR с подробным выводом
pytest tests/test_ocr.py -v -s
```

### Структура тестов
```
tests/
├── unit/                           # Модульные тесты
│   ├── test_text_parser.py         # Тесты парсера текста
│   ├── test_currency_service.py    # Тесты валютного сервиса
│   ├── test_category_service.py    # Тесты сервиса категорий
│   └── test_ocr_service.py         # Тесты OCR сервиса
├── integration/                    # Интеграционные тесты
│   ├── test_bot_handlers.py        # Тесты обработчиков бота
│   ├── test_database.py            # Тесты базы данных
│   └── test_ai_services.py         # Тесты AI сервисов
└── fixtures/                       # Тестовые данные
    ├── sample_receipts/            # Примеры чеков
    ├── test_images/                # Тестовые изображения
    └── test_data.json             # Тестовые данные
```

## 🚨 Troubleshooting

### Частые проблемы и решения

#### 1. 🤖 Бот не отвечает на сообщения
```bash
# Проверка статуса сервиса
sudo systemctl status expanse-bot.service

# Просмотр логов
sudo journalctl -u expanse-bot.service -f

# Перезапуск сервиса
sudo systemctl restart expanse-bot.service

# Проверка токена бота
python3 -c "
import asyncio
from aiogram import Bot
async def check_bot():
    bot = Bot(token='YOUR_TOKEN')
    me = await bot.get_me()
    print(f'Bot @{me.username} is working!')
    await bot.session.close()
asyncio.run(check_bot())
"
```

#### 2. 🔤 OCR не распознает текст
```bash
# Проверка установки Tesseract
tesseract --version

# Проверка языковых пакетов
tesseract --list-langs

# Должно показать: eng rus
# Если нет, установите:
sudo apt install tesseract-ocr-rus tesseract-ocr-eng

# Тест OCR на изображении
tesseract test_image.jpg output -l rus+eng

# Проверка путей в .env
echo $TESSERACT_PATH
echo $TESSDATA_PREFIX
```

#### 3. 🗄️ Ошибки базы данных
```bash
# Проверка состояния миграций
python -m alembic current

# Показать историю миграций
python -m alembic history

# Обновление до последней миграции
python -m alembic upgrade head

# Создание бэкапа БД
cp expanse_bot.db backup_$(date +%Y%m%d_%H%M%S).db

# Восстановление из бэкапа
cp backup_20231225_143022.db expanse_bot.db
```

#### 4. 💱 Проблемы с конвертацией валют
```bash
# Проверка API ключа валют
curl "https://api.exchangerate-api.com/v4/latest/USD"

# Проверка переменных окружения
grep CURRENCY .env

# Очистка кеша валют
python3 -c "
from src.services.currency import currency_service
print('Clearing currency cache...')
currency_service.clear_cache()
print('Cache cleared!')
"
```

#### 5. 🤖 OpenAI API ошибки
```bash
# Проверка API ключа
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Проверка лимитов
python3 -c "
import openai
client = openai.OpenAI(api_key='YOUR_API_KEY')
print(client.models.list())
"

# Отключение OpenAI (использовать только Tesseract)
# В .env файле:
# USE_OPENAI_VISION=false
```

#### 6. ☁️ AWS S3 проблемы
```bash
# Проверка AWS credentials
aws sts get-caller-identity

# Проверка доступа к S3 bucket
aws s3 ls s3://your-bucket-name/

# Тест загрузки файла
aws s3 cp test.txt s3://your-bucket-name/test.txt

# Отключение S3 (локальное хранение)
# В .env файле:
# ENABLE_S3_STORAGE=false
```

### 📊 Мониторинг и логи

#### Системные логи
```bash
# Логи сервиса в реальном времени
sudo journalctl -u expanse-bot.service -f

# Логи за последние 100 строк
sudo journalctl -u expanse-bot.service -n 100

# Логи с определенного времени
sudo journalctl -u expanse-bot.service --since "2023-12-25 10:00:00"

# Логи только с ошибками
sudo journalctl -u expanse-bot.service -p err

# Экспорт логов в файл
sudo journalctl -u expanse-bot.service > bot_logs.txt
```

#### Логи приложения
```bash
# Основной лог файл
tail -f bot.log

# Поиск ошибок
grep -i error bot.log | tail -20

# Поиск по пользователю
grep "user_id: 123456" bot.log

# Статистика по логам
awk '/ERROR/ {count++} END {print "Total errors:", count}' bot.log
```

#### Мониторинг производительности
```bash
# Использование CPU и памяти
top -p $(pgrep -f "expanse-bot")

# Размер базы данных
ls -lh expanse_bot.db*

# Количество активных соединений
netstat -an | grep :8080 | wc -l

# Использование диска
df -h
du -sh /home/ubuntu/expanse-expenses-bot/
```

## 🤝 Разработка и вклад

### Настройка среды разработки
```bash
# Клонирование для разработки
git clone https://github.com/yourusername/expanse-expenses-bot.git
cd expanse-expenses-bot

# Создание ветки для функции
git checkout -b feature/new-awesome-feature

# Установка зависимостей для разработки
pip install -r requirements-dev.txt

# Настройка pre-commit хуков
pre-commit install
```

### Стандарты кода
```bash
# Форматирование кода
black src/ tests/

# Проверка стиля
flake8 src/ tests/

# Проверка типов
mypy src/

# Сортировка импортов
isort src/ tests/

# Линтинг
pylint src/
```

### Структура коммитов
```
feat: добавить новую функцию
fix: исправить ошибку
docs: обновить документацию
style: форматирование кода
refactor: рефакторинг без изменения функциональности
test: добавить или обновить тесты
chore: обновить зависимости или конфигурацию
perf: улучшение производительности
ci: изменения в CI/CD
```

### Процесс внесения изменений
1. **Форкните репозиторий**
2. **Создайте ветку**: `git checkout -b feature/amazing-feature`
3. **Внесите изменения** с соблюдением стандартов кода
4. **Добавьте тесты** для новой функциональности
5. **Обновите документацию** при необходимости
6. **Коммитите изменения**: `git commit -m 'feat: add amazing feature'`
7. **Пушьте в ветку**: `git push origin feature/amazing-feature`
8. **Откройте Pull Request** с подробным описанием

## 📄 Лицензия

Этот проект лицензирован под **MIT License** - см. файл [LICENSE](LICENSE) для деталей.

## 📞 Поддержка и обратная связь

### 🚀 Быстрая помощь
- 🐛 **Issues**: [GitHub Issues](https://github.com/yourusername/expanse-expenses-bot/issues)
- 💬 **Обсуждения**: [GitHub Discussions](https://github.com/yourusername/expanse-expenses-bot/discussions)
- 📖 **Wiki**: [GitHub Wiki](https://github.com/yourusername/expanse-expenses-bot/wiki)

### 👥 Сообщество
- 📧 **Email**: support@expanse-bot.com
- 💬 **Telegram**: [@expanse_bot_support](https://t.me/expanse_bot_support)
- 🌐 **Website**: [expanse-bot.com](https://expanse-bot.com)

### 📈 Roadmap и планы

#### Версия 2.0 (Q1 2024)
- [ ] 🌐 Web-интерфейс для управления расходами
- [ ] 📱 Mobile приложение (iOS/Android)
- [ ] 🏦 Интеграция с банковскими API
- [ ] 🧠 Улучшенное машинное обучение для категоризации
- [ ] 👥 Семейные бюджеты и совместное использование

#### Версия 2.1 (Q2 2024)
- [ ] 💰 Планирование бюджета и цели накоплений
- [ ] 🔔 Уведомления о превышении лимитов
- [ ] 📅 Интеграция с календарем
- [ ] 🎤 Голосовые команды и распознавание речи
- [ ] 📊 Продвинутая аналитика с BI dashboard

#### Версия 2.2 (Q3 2024)
- [ ] 🏢 Интеграция с CRM и ERP системами
- [ ] 🔌 API для сторонних разработчиков
- [ ] 🧩 Система плагинов и расширений
- [ ] 🏛️ Мультитенантность для организаций
- [ ] 🛡️ Enterprise функции безопасности

---

**💰 Expanse Expenses Bot** - Ваш умный помощник для управления финансами! ✨

*Сделайте контроль расходов простым и эффективным с помощью искусственного интеллекта.*