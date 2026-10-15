-- Apply ONCE before starting this application version; existing tasks and usage are retained.
ALTER TABLE task ADD COLUMN deleted_at DATETIME NULL
  COMMENT 'Hidden recommendation history; still counted toward task quotas';
