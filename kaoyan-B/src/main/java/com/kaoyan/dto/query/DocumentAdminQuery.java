package com.kaoyan.dto.query;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 后台资料分页查询
 */
@Schema(description = "后台资料分页查询")
public record DocumentAdminQuery(
        @Schema(description = "资料状态", example = "PENDING_REVIEW")
        String status,

        @Schema(description = "页码，从 1 开始", example = "1")
        Integer page,

        @Schema(description = "每页条数", example = "10")
        Integer size
) {

    /**
     * 有效页码
     *
     * @return 页码
     */
    public int pageNum() {
        return page == null || page < 1 ? 1 : page;
    }

    /**
     * 有效每页条数
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
