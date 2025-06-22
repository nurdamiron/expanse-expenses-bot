# Полное руководство по деплою Expanse Bot на сервер

## Требования к серверу

- Ubuntu 20.04+ или Debian 10+
- Минимум 1 GB RAM
- 10 GB свободного места
- Python 3.10+
- Доступ по SSH

## Шаг 1: Подготовка сервера

Подключитесь к серверу по SSH:
```bash
ssh root@your-server-ip
```

### 1.1 Обновление системы
```bash
apt update && apt upgrade -y
```

### 1.2 Установка необходимых пакетов
```bash
apt install -y python3.10 python3.10-venv python3-pip 
apt install -y git nginx redis-server mysql-server
apt install -y tesseract-ocr tesseract-ocr-rus tesseract-ocr-kaz
apt install -y supervisor htop tmux
```

### 1.3 Создание пользователя для бота
```bash
adduser botuser
usermod -aG sudo botuser
su - botuser
```

## Шаг 2: Клонирование и настройка проекта

### 2.1 Клонирование репозитория
```bash
cd ~
git clone https://github.com/nurdamiron/expanse-expenses-bot.git
cd expanse-expenses-bot
```

### 2.2 Создание виртуального окружения
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.3 Настройка переменных окружения
```bash
cp .env.example .env
nano .env
```

Заполните все необходимые переменные:
- `BOT_TOKEN` - токен от @BotFather
- `DB_*` - настройки базы данных
- `REDIS_*` - настройки Redis
- Другие API ключи

## Шаг 3: Настройка базы данных

### 3.1 Настройка MySQL
```bash
sudo mysql_secure_installation
sudo mysql
```

В MySQL консоли:
```sql
CREATE DATABASE expanse_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'botuser'@'localhost' IDENTIFIED BY 'your_strong_password';
GRANT ALL PRIVILEGES ON expanse_bot.* TO 'botuser'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3.2 Импорт схемы
```bash
mysql -u botuser -p expanse_bot < database/schema.sql
```

## Шаг 4: Создание systemd сервиса

### 4.1 Создайте файл сервиса
```bash
sudo nano /etc/systemd/system/expanse-bot.service
```

Вставьте содержимое:
```ini
[Unit]
Description=Expanse Telegram Bot
After=network.target mysql.service redis.service

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/expanse-expenses-bot
Environment="PATH=/home/botuser/expanse-expenses-bot/venv/bin"
ExecStart=/home/botuser/expanse-expenses-bot/venv/bin/python main.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/expanse-bot/bot.log
StandardError=append:/var/log/expanse-bot/error.log

[Install]
WantedBy=multi-user.target
```

### 4.2 Создайте директорию для логов
```bash
sudo mkdir -p /var/log/expanse-bot
sudo chown botuser:botuser /var/log/expanse-bot
```

### 4.3 Активируйте и запустите сервис
```bash
sudo systemctl daemon-reload
sudo systemctl enable expanse-bot
sudo systemctl start expanse-bot
sudo systemctl status expanse-bot
```

## Шаг 5: Настройка автообновлений

### 5.1 Настройка cron для проверки обновлений
```bash
crontab -e
```

Добавьте строку:
```cron
*/5 * * * * /home/botuser/expanse-expenses-bot/deploy/auto_update.sh
```

### 5.2 Сделайте скрипт исполняемым
```bash
chmod +x /home/botuser/expanse-expenses-bot/deploy/auto_update.sh
```

## Шаг 6: Настройка Nginx (опционально, для webhook)

### 6.1 Создайте конфигурацию
```bash
sudo nano /etc/nginx/sites-available/bot-webhook
```

Содержимое:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /webhook {
        proxy_pass http://127.0.0.1:9000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /health {
        proxy_pass http://127.0.0.1:9000;
    }
}
```

### 6.2 Активируйте конфигурацию
```bash
sudo ln -s /etc/nginx/sites-available/bot-webhook /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Шаг 7: Настройка мониторинга

### 7.1 Установка мониторинга процесса
```bash
sudo nano /etc/systemd/system/bot-monitor.service
```

```ini
[Unit]
Description=Bot Monitor
After=expanse-bot.service

[Service]
Type=simple
ExecStart=/bin/bash -c 'while true; do if ! systemctl is-active --quiet expanse-bot; then systemctl restart expanse-bot; echo "Bot restarted at $(date)" >> /var/log/expanse-bot/monitor.log; fi; sleep 60; done'
Restart=always

[Install]
WantedBy=multi-user.target
```

### 7.2 Запустите мониторинг
```bash
sudo systemctl enable bot-monitor
sudo systemctl start bot-monitor
```

## Шаг 8: Настройка бэкапов

### 8.1 Создайте скрипт бэкапа
```bash
nano ~/backup-bot.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/botuser/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
mysqldump -u botuser -p'your_password' expanse_bot | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +7 -delete
```

### 8.2 Добавьте в cron
```bash
crontab -e
```

```cron
0 3 * * * /home/botuser/backup-bot.sh
```

## Шаг 9: Проверка работы

### 9.1 Проверьте статус
```bash
sudo systemctl status expanse-bot
```

### 9.2 Посмотрите логи
```bash
tail -f /var/log/expanse-bot/bot.log
```

### 9.3 Проверьте бота в Telegram
Отправьте команду `/start` вашему боту

## Шаг 10: Настройка GitHub Actions (автодеплой)

### 10.1 Сгенерируйте SSH ключ на сервере
```bash
ssh-keygen -t rsa -b 4096 -C "github-actions"
cat ~/.ssh/id_rsa  # Скопируйте приватный ключ
```

### 10.2 Добавьте публичный ключ в authorized_keys
```bash
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
```

### 10.3 В GitHub репозитории добавьте Secrets:
- Settings → Secrets → New repository secret
- `SERVER_HOST`: IP адрес сервера
- `SERVER_USER`: botuser
- `SERVER_SSH_KEY`: приватный ключ из шага 10.1

Теперь при каждом push в main бот будет автоматически обновляться!

## Полезные команды

```bash
# Остановить бота
sudo systemctl stop expanse-bot

# Перезапустить бота
sudo systemctl restart expanse-bot

# Посмотреть логи
journalctl -u expanse-bot -f

# Обновить вручную
cd ~/expanse-expenses-bot
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart expanse-bot
```

## Troubleshooting

### Бот не запускается
1. Проверьте логи: `journalctl -u expanse-bot -n 100`
2. Проверьте .env файл
3. Проверьте подключение к БД и Redis

### Ошибки с правами
```bash
sudo chown -R botuser:botuser /home/botuser/expanse-expenses-bot
```

### Проблемы с зависимостями
```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```