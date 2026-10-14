package com.kaoyan.common;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 统一响应
 */
@Data
@Schema(description = "统一响应")
public class Result<T> {

    /** 状态码，0 表示成功 */
    @Schema(description = "状态码，0 表示成功", example = "0")
    private int code;

    /** 提示信息 */
    @Schema(description = "提示信息", example = "ok")
    private String message;

    /** 响应数据 */
    @Schema(description = "响应数据")
    private T data;

    public static <T> Result<T> ok() {
        return ok(null);
    }

    public static <T> Result<T> ok(T data) {
        Result<T> r = new Result<>();
        r.setCode(0);
        r.setMessage("ok");
        r.setData(data);
        return r;
    }

    public static <T> Result<T> fail(int code, String message) {
        Result<T> r = new Result<>();
        r.setCode(code);
        r.setMessage(message);
        return r;
    }
}
