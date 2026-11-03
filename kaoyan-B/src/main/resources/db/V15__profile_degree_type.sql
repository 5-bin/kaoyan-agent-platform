-- Apply ONCE after V14, with backup and explicit database authorization.
-- Additive only: existing profiles keep NULL and school comparison falls back to the catalog or asks.
ALTER TABLE `user`
  ADD COLUMN degree_type VARCHAR(16) NULL COMMENT '报考学位类型：academic学硕／professional专硕' AFTER exam_year,
  ADD CONSTRAINT ck_user_degree_type CHECK (degree_type IS NULL OR degree_type IN ('academic','professional'));
