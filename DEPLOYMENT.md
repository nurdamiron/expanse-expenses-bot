# Развертывание Expanse Telegram Bot

## Быстрый старт

### 1. Предварительные требования

- Python 3.10+
- MySQL 8.0+ (AWS RDS)
- Redis 6.0+
- Tesseract OCR

### 2. Клонирование и настройка

```bash
# Клонирование репозитория
git clone https://github.com/yourusername/expanse-telegram-bot.git
cd expanse-telegram-bot

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 3. Настройка переменных окружения

```bash
# Копирование примера конфигурации
cp .env.example .env

# Редактирование .env файла
nano .env  # или используйте любой текстовый редактор
```

Обязательные переменные:
- `BOT_TOKEN` - токен от @BotFather
- `DB_*` - параметры подключения к MySQL

### 4. Инициализация базы данных

```bash
# Запуск скрипта инициализации
python scripts/init_db.py
```

### 5. Тестирование

```bash
# Запуск тестов компонентов
python scripts/test_bot.py
```

### 6. Запуск бота

```bash
# Обычный запуск
python main.py

# Или через Docker Compose
docker-compose up -d
```

## Развертывание на сервере

### Использование systemd (Linux)

1. Создайте файл сервиса:

```bash
sudo nano /etc/systemd/system/expanse-bot.service
```

2. Добавьте конфигурацию:

```ini
[Unit]
Description=Expanse Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/expanse-telegram-bot
Environment="PATH=/home/ubuntu/expanse-telegram-bot/venv/bin"
ExecStart=/home/ubuntu/expanse-telegram-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Запустите сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable expanse-bot
sudo systemctl start expanse-bot
sudo systemctl status expanse-bot
```

### Использование Docker

1. Сборка образа:

```bash
docker build -t expanse-bot .
```

2. Запуск контейнера:

```bash
docker run -d \
  --name expanse-bot \
  --restart unless-stopped \
  --env-file .env \
  expanse-bot
```

### Использование Docker Compose

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down
```

## Настройка Redis (локально)

### Ubuntu/Debian:

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### macOS:

```bash
brew install redis
brew services start redis
```

## Настройка Tesseract OCR

### Ubuntu/Debian:

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-rus tesseract-ocr-kaz
```

### macOS:

```bash
brew install tesseract
brew install tesseract-lang
```

## Мониторинг

### Просмотр логов

```bash
# Systemd
sudo journalctl -u expanse-bot -f

# Docker
docker logs -f expanse-bot

# Docker Compose
docker-compose logs -f bot
```

### Проверка состояния

```bash
# Проверка процесса
ps aux | grep main.py

# Проверка подключения к БД
mysql -h $DB_HOST -u $DB_USERNAME -p$DB_PASSWORD -e "SELECT 1"

# Проверка Redis
redis-cli ping
```

## Обновление

```bash
# Остановка бота
sudo systemctl stop expanse-bot  # или docker-compose down

# Получение обновлений
git pull origin main

# Обновление зависимостей
pip install -r requirements.txt --upgrade

# Применение миграций БД (если есть)
python scripts/migrate_db.py  # если такой скрипт существует

# Запуск бота
sudo systemctl start expanse-bot  # или docker-compose up -d
```

## Резервное копирование

### База данных

```bash
# Создание дампа
mysqldump -h $DB_HOST -u $DB_USERNAME -p$DB_PASSWORD expanse_bot > backup_$(date +%Y%m%d).sql

# Восстановление из дампа
mysql -h $DB_HOST -u $DB_USERNAME -p$DB_PASSWORD expanse_bot < backup_20240101.sql
```

### Автоматическое резервное копирование (cron)

```bash
# Редактирование crontab
crontab -e

# Добавить строку для ежедневного бэкапа в 3:00
0 3 * * * mysqldump -h $DB_HOST -u $DB_USERNAME -p$DB_PASSWORD expanse_bot > /backups/expanse_bot_$(date +\%Y\%m\%d).sql
```

## Устранение неполадок

### Бот не запускается

1. Проверьте токен бота
2. Проверьте подключение к БД
3. Проверьте наличие всех зависимостей
4. Просмотрите логи на наличие ошибок

### Ошибки БД

```bash
# Проверка подключения
mysql -h expanse.cde42ec8m1u7.eu-north-1.rds.amazonaws.com -u admin -p

# Проверка таблиц
USE expanse_bot;
SHOW TABLES;
```

### Проблемы с OCR

1. Убедитесь, что Tesseract установлен
2. Проверьте путь к Tesseract в .env
3. Установите языковые пакеты (rus, kaz)

## Безопасность

1. **Никогда не коммитьте .env файл**
2. Используйте сильные пароли для БД
3. Ограничьте доступ к БД по IP
4. Регулярно обновляйте зависимости
5. Настройте SSL для webhook (в production)