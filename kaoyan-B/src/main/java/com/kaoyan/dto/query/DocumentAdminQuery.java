package com.kaoyan.dto.query;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 后台资料分页查询
 */
@Data
@EqualsAndHashCode(callSuper = true)
@Schema(description = "后台资料分页查询")
public class DocumentAdminQuery extends PageQuery {
    @Schema(description = "资料状态", example = "PENDING_REVIEW")
    private String status;

    public String status() { return status; }
}
