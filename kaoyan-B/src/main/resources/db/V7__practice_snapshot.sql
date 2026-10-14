-- Apply ONCE after V1 on fresh/existing databases; no data is deleted.
ALTER TABLE practice_record ADD COLUMN question_snapshot JSON NULL
  COMMENT 'Immutable question version captured at grading; legacy rows remain NULL';
