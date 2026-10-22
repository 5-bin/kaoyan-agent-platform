-- Apply ONCE after checking V7/V8, BEFORE starting the question-entry application.
-- Additive only: legacy questions, review states and practice snapshots are preserved.
-- NULL means the source has not yet been documented; do not fabricate provenance.
ALTER TABLE question ADD COLUMN source_type VARCHAR(20) NULL
  COMMENT 'REAL_EXAM / MOCK / ORIGINAL; NULL for undocumented legacy sources';
ALTER TABLE question ADD COLUMN source_name VARCHAR(255) NULL
  COMMENT 'Paper, publication or original author record';
ALTER TABLE question ADD COLUMN source_locator VARCHAR(1000) NULL
  COMMENT 'Traceable URL, page, section or author record location';
ALTER TABLE question ADD COLUMN source_year INT NULL
  COMMENT 'Exam or source year when known';
ALTER TABLE question ADD COLUMN source_question_no VARCHAR(64) NULL
  COMMENT 'Original question number when applicable';
ALTER TABLE question ADD COLUMN permission_note VARCHAR(2000) NULL
  COMMENT 'Permission or original authorship evidence';
