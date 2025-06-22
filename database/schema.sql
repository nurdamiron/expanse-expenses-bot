-- База данных для Telegram бота учета расходов
-- MySQL 8.0+ на AWS RDS

-- Создание базы данных
CREATE DATABASE IF NOT EXISTS expanse_bot 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE expanse_bot;

-- Таблица пользователей
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    language_code ENUM('ru', 'kz') DEFAULT 'ru',
    primary_currency ENUM('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY') DEFAULT 'KZT',
    timezone VARCHAR(50) DEFAULT 'Asia/Almaty',
    is_active BOOLEAN DEFAULT true,
    settings JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_telegram_id (telegram_id),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица категорий расходов
CREATE TABLE categories (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id BIGINT NOT NULL,
    name_ru VARCHAR(100) NOT NULL,
    name_kz VARCHAR(100) NOT NULL,
    icon VARCHAR(10) NOT NULL,
    color VARCHAR(7) DEFAULT '#000000',
    is_default BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    order_position INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица транзакций
CREATE TABLE transactions (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id BIGINT NOT NULL,
    category_id CHAR(36),
    amount DECIMAL(12,2) NOT NULL,
    currency ENUM('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY') NOT NULL,
    amount_primary DECIMAL(12,2) NOT NULL COMMENT 'Сумма в основной валюте пользователя',
    exchange_rate DECIMAL(10,4) DEFAULT 1.0000,
    description TEXT,
    merchant VARCHAR(255),
    transaction_date DATETIME NOT NULL,
    receipt_image_url TEXT,
    ocr_confidence DECIMAL(3,2) COMMENT 'Уверенность распознавания 0.00-1.00',
    meta_data JSON COMMENT 'Дополнительная информация',
    is_deleted BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
    INDEX idx_user_date (user_id, transaction_date),
    INDEX idx_category (category_id),
    INDEX idx_transaction_date (transaction_date),
    INDEX idx_is_deleted (is_deleted),
    INDEX idx_user_month (user_id, transaction_date, is_deleted),
    INDEX idx_amount_search (user_id, amount_primary, is_deleted),
    FULLTEXT(description, merchant)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица курсов валют
CREATE TABLE exchange_rates (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    from_currency ENUM('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY') NOT NULL,
    to_currency ENUM('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY') NOT NULL,
    rate DECIMAL(10,4) NOT NULL,
    source VARCHAR(50) NOT NULL COMMENT 'API источник курса',
    is_active BOOLEAN DEFAULT true,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_currency_pair (from_currency, to_currency, fetched_at),
    INDEX idx_currency_pair (from_currency, to_currency),
    INDEX idx_fetched_at (fetched_at),
    INDEX idx_latest_rate (from_currency, to_currency, fetched_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица лимитов пользователей
CREATE TABLE user_limits (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id BIGINT NOT NULL,
    limit_type ENUM('daily', 'weekly', 'monthly') NOT NULL,
    category_id CHAR(36) DEFAULT NULL COMMENT 'NULL = лимит на все категории',
    amount DECIMAL(12,2) NOT NULL,
    currency ENUM('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY') NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    INDEX idx_user_limits (user_id, is_active),
    INDEX idx_date_range (start_date, end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица уведомлений
CREATE TABLE notifications (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id BIGINT NOT NULL,
    type ENUM('limit_exceeded', 'weekly_report', 'monthly_report', 'reminder') NOT NULL,
    status ENUM('pending', 'sent', 'failed') DEFAULT 'pending',
    scheduled_at DATETIME NOT NULL,
    sent_at DATETIME DEFAULT NULL,
    content JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_status_scheduled (status, scheduled_at),
    INDEX idx_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица состояний бота (для FSM)
CREATE TABLE bot_states (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    state VARCHAR(100),
    state_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_state (user_id),
    INDEX idx_state (state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица истории поиска (для аналитики)
CREATE TABLE search_history (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id BIGINT NOT NULL,
    search_type ENUM('text', 'amount', 'category', 'date_range') NOT NULL,
    search_query TEXT,
    results_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица экспортов
CREATE TABLE export_history (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id BIGINT NOT NULL,
    format ENUM('xlsx', 'csv', 'pdf') NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    file_url TEXT,
    file_size INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Представления для аналитики
CREATE VIEW daily_spending AS
SELECT 
    user_id,
    DATE(transaction_date) as date,
    SUM(amount_primary) as total_amount,
    COUNT(*) as transaction_count
FROM transactions
WHERE is_deleted = false
GROUP BY user_id, DATE(transaction_date);

CREATE VIEW category_spending AS
SELECT 
    t.user_id,
    t.category_id,
    c.name_ru,
    c.name_kz,
    c.icon,
    SUM(t.amount_primary) as total_amount,
    COUNT(*) as transaction_count,
    DATE_FORMAT(t.transaction_date, '%Y-%m') as month
FROM transactions t
JOIN categories c ON t.category_id = c.id
WHERE t.is_deleted = false
GROUP BY t.user_id, t.category_id, month;

-- Триггер для автоматического создания стандартных категорий при регистрации пользователя
DELIMITER $$
CREATE TRIGGER after_user_insert
AFTER INSERT ON users
FOR EACH ROW
BEGIN
    INSERT INTO categories (user_id, name_ru, name_kz, icon, is_default, order_position) VALUES
    (NEW.id, 'Еда и рестораны', 'Тамақ және мейрамханалар', '🍔', true, 1),
    (NEW.id, 'Транспорт', 'Көлік', '🚗', true, 2),
    (NEW.id, 'Покупки и одежда', 'Сатып алулар мен киім', '🛒', true, 3),
    (NEW.id, 'Дом и коммунальные', 'Үй және коммуналдық', '🏠', true, 4),
    (NEW.id, 'Здоровье', 'Денсаулық', '💊', true, 5),
    (NEW.id, 'Развлечения', 'Ойын-сауық', '🎬', true, 6),
    (NEW.id, 'Образование', 'Білім беру', '📚', true, 7),
    (NEW.id, 'Прочее', 'Басқа', '💰', true, 8);
END$$
DELIMITER ;