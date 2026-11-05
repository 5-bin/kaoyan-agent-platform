package com.kaoyan.dto.response;

import com.kaoyan.entity.User;
import java.time.LocalDateTime;

/** Explicit public registration fields; credentials never enter this DTO. */
public record RegistrationResponse(
    Long id, String username, String role, Integer status, String avatarUrl,
    String targetSchool, String targetMajor, Integer examYear, String degreeType,
    String background, LocalDateTime createdAt, LocalDateTime updatedAt
) {
    public static RegistrationResponse from(User user) {
        return new RegistrationResponse(user.getId(), user.getUsername(), user.getRole(), user.getStatus(),
            user.getAvatarUrl(), user.getTargetSchool(), user.getTargetMajor(), user.getExamYear(),
            user.getDegreeType(), user.getBackground(), user.getCreatedAt(), user.getUpdatedAt());
    }
}
