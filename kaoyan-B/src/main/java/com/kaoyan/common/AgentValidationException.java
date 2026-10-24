package com.kaoyan.common;

/** Fixed internal diagnostics; never derive log messages from remote input. */
public final class AgentValidationException extends IllegalStateException {
    public enum Code {
        SOURCE_HOST_NOT_ALLOWED, PLAN_VALIDATION_FAILED, RESULT_VALIDATION_FAILED,
        CONDITIONS_VALIDATION_FAILED, DOCUMENT_VALIDATION_FAILED, UPSTREAM_FAILED, UNEXPECTED_ERROR
    }

    private final Code code;

    public AgentValidationException(Code code) {
        super(code.name());
        this.code = code;
    }

    public Code getCode() { return code; }
}
