-- Check if the table exists and its structure
SHOW TABLES LIKE 'transactions';

-- Check the structure of transactions table
DESCRIBE transactions;

-- If meta_data column doesn't exist, add it
-- ALTER TABLE transactions ADD COLUMN meta_data JSON COMMENT 'Дополнительная информация' AFTER ocr_confidence;