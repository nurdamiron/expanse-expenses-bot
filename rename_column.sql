-- Rename metadata column to meta_data in transactions table
ALTER TABLE transactions 
CHANGE COLUMN metadata meta_data JSON 
COMMENT 'Дополнительная информация';