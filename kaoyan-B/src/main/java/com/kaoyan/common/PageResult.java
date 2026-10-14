package com.kaoyan.common;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
import java.util.List;

/**
 * 分页响应
 */
@Data
@Schema(description = "分页响应")
public class PageResult<T> {

    /** 总条数 */
    @Schema(description = "总条数", example = "100")
    private long total;

    /** 页码，从 1 开始 */
    @Schema(description = "页码", example = "1")
    private long page;

    /** 每页条数 */
    @Schema(description = "每页条数", example = "10")
    private long size;

    /** 数据列表 */
    @Schema(description = "数据列表")
    private List<T> list;

    public static <T> PageResult<T> of(long total, long page, long size, List<T> list) {
        PageResult<T> r = new PageResult<>();
        r.setTotal(total);
        r.setPage(page);
        r.setSize(size);
        r.setList(list);
        return r;
    }
}
