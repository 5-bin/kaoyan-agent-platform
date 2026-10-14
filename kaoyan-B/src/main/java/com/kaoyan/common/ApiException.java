package com.kaoyan.common;

import lombok.Getter;

/**
 * 业务异常
 */
@Getter
public class ApiException extends RuntimeException {

    /** HTTP 状态码 */
    private final int httpStatus;

    /** 业务错误码 */
    private final int code;

    public ApiException(int httpStatus, int code, String message) {
        super(message);
        this.httpStatus = httpStatus;
        this.code = code;
    }

    public ApiException(int httpStatus, String message) {
        this(httpStatus, httpStatus, message);
    }
}
