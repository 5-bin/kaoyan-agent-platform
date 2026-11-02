package com.kaoyan.dto.response;

/** Safe, row-local catalog diagnostics; invalid values never accompany warnings. */
public record SchoolWarning(String code, Long detailId, String metricType, String message) {}
