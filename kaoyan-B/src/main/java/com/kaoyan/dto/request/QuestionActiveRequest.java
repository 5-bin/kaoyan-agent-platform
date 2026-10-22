package com.kaoyan.dto.request;

import jakarta.validation.constraints.*;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;

/** Activation does not grant permission to edit published content or audit fields. */
public record QuestionActiveRequest(
    @JsonDeserialize(using=StrictIntegerDeserializer.class)
    @NotNull @Min(0) @Max(1) Integer active,
    @JsonDeserialize(using=StrictIntegerDeserializer.class)
    @NotNull(message="请先读取最新题目版本") @Min(1) Integer version
) {}
