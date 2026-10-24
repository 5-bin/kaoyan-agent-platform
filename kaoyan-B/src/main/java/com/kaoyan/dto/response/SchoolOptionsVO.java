package com.kaoyan.dto.response;

import java.util.List;

/** 院校库已有的筛选选项，不代表资料已经核验。 */
public record SchoolOptionsVO(List<String> provinces, List<String> majorNames) {}
