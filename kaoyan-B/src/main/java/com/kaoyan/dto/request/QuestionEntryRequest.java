package com.kaoyan.dto.request;

import jakarta.validation.constraints.*;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;

/** Whitelist for entering unpublished single-choice questions; publishing fields are server-owned. */
public record QuestionEntryRequest(
    @NotBlank @Pattern(regexp="数据结构|操作系统|计算机组成原理|计算机网络", message="请选择408科目") String subject,
    @NotBlank(message="知识点不能为空") @Size(max=255) String knowledgePoint,
    @NotBlank @Pattern(regexp="EASY|MEDIUM|HARD", message="难度不合法") String difficulty,
    @NotBlank(message="题干不能为空") @Size(max=10000) String content,
    @NotBlank(message="选项A不能为空") @Size(max=2000) String optionA,
    @NotBlank(message="选项B不能为空") @Size(max=2000) String optionB,
    @NotBlank(message="选项C不能为空") @Size(max=2000) String optionC,
    @NotBlank(message="选项D不能为空") @Size(max=2000) String optionD,
    @NotBlank @Pattern(regexp="[A-Da-d]", message="答案必须为A至D的单个字母") String answer,
    @NotBlank(message="解析不能为空") @Size(max=10000) String analysis,
    @NotBlank @Pattern(regexp="REAL_EXAM|MOCK|ORIGINAL", message="来源类别不合法") String sourceType,
    @NotBlank(message="来源名称不能为空") @Size(max=255) String sourceName,
    @NotBlank(message="来源定位不能为空") @Size(max=1000) String sourceLocator,
    @JsonDeserialize(using=StrictIntegerDeserializer.class) @Min(1900) @Max(2100) Integer sourceYear,
    @Size(max=64) String sourceQuestionNo,
    @NotBlank(message="使用权限说明不能为空") @Size(max=2000) String permissionNote
) {}
