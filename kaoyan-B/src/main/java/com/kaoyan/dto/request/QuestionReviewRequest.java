package com.kaoyan.dto.request;

import jakarta.validation.constraints.*;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;

/** Separate from document review to preserve that module's status vocabulary. */
public record QuestionReviewRequest(
    @NotBlank @Pattern(regexp="APPROVED|REJECTED", message="审核结果只能为通过或驳回") String status,
    @Size(max=2000) String comment,
    @JsonDeserialize(using=StrictIntegerDeserializer.class)
    @NotNull(message="请先读取最新题目版本") @Min(1) Integer version
) {}
