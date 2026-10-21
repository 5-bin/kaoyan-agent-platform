package com.kaoyan.dto.response;

public record AnswerVO(Long questionId, String userAnswer, Integer isCorrect, String answer, String analysis) {}
