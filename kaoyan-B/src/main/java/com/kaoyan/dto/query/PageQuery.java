package com.kaoyan.dto.query;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 分页查询基类参数
 */
@Schema(description = "分页查询参数")
public record PageQuery(
        @Schema(description = "页码，从 1 开始", example = "1")
        Integer page,

        @Schema(description = "每页条数", example = "10")
        Integer size
) {

    /**
     * 有效页码（默认 1）
     *
     * @return 页码
     */
    public int pageNum() {
        return page == null || page < 1 ? 1 : page;
    }

    /**
     * 有效每页条数（默认 10，上限 100）
     *
     * @return 每页条数
     */
    public int pageSize() {
        if (size == null || size < 1) {
            return 10;
        }
        return Math.min(size, 100);
    }
}
