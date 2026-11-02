package com.kaoyan.dto.response;

import com.kaoyan.entity.Question;
import java.util.List;

/** Administrator-only preview or persisted import result. Preview IDs are null. */
public record QuestionImportVO(int count, List<Question> questions) {}
