package com.kaoyan.dto.query;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/** 分页查询：与前端 pageNum/pageSize 对齐，同时兼容旧 page/size 参数。 */
@Data
@Schema(description = "分页查询参数")
public class PageQuery {
    @Schema(description = "页码，从1开始", example = "1")
    private Integer pageNum;
    @Schema(description = "每页条数，最多100", example = "20")
    private Integer pageSize;
    private Integer page;
    private Integer size;

    public int pageNum() {
        Integer value = pageNum != null ? pageNum : page;
        return value == null || value < 1 ? 1 : value;
    }

    public int pageSize() {
        Integer value = pageSize != null ? pageSize : size;
        return value == null || value < 1 ? 10 : Math.min(value, 100);
    }
}
