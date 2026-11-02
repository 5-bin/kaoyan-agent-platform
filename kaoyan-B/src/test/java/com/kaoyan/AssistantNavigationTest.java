package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.entity.User;
import com.kaoyan.mapper.UserMapper;
import com.kaoyan.service.AssistantNavigation;
import org.junit.jupiter.api.Test;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class AssistantNavigationTest {
    final UserMapper users=mock(UserMapper.class);
    final AssistantNavigation navigation=new AssistantNavigation(new ObjectMapper(),users);

    @Test void registryMatchesSharedSourceAndCoversEverySidebarDestination() throws Exception {
        try(var input=getClass().getResourceAsStream("/assistant-navigation.json")) {
            assertArrayEquals(Files.readAllBytes(Path.of("../config/assistant-navigation.json")),input.readAllBytes());
        }
        var result=Map.<String,Object>of("answer","首页 刷题 Agent 助手 个人笔记 错题本 我的收藏 学习统计 院校库 备考资料 管理后台 题目录入与审核");
        assertEquals(9,navigation.targets(result,false).size());
        assertEquals(11,navigation.targets(result,true).size());
    }

    @Test void upstreamNavigationCannotInjectUrlsOrAdminTargetsAndRoleChangesAreApplied() {
        var result=new LinkedHashMap<String,Object>();
        result.put("answer","去错题本与管理后台；javascript:alert(1) https://evil.invalid");
        result.put("navigation",List.of(Map.of("target","HOME","url","https://evil.invalid")));
        var user=new User();user.setRole("STUDENT");when(users.selectById(1L)).thenReturn(user);
        navigation.decorate(1L,result);
        assertEquals(List.of(Map.of("target","WRONG")),result.get("navigation"));
        user.setRole("ADMIN");navigation.decorate(1L,result);
        assertEquals(List.of(Map.of("target","WRONG"),Map.of("target","ADMIN_DOCUMENTS")),result.get("navigation"));
        user.setRole("STUDENT");navigation.decorate(1L,result);
        assertEquals(List.of(Map.of("target","WRONG")),result.get("navigation"));
    }

    @Test void trustedResourcesAndActionsAddRelevantDestinationsWithoutDuplicates() {
        var result=Map.<String,Object>of("answer","刷题", "documentProposal",Map.of("title","笔记"),
            "candidates",List.of(Map.of("school","合成学校")),
            "evidence",List.of(Map.of("resource",Map.of("type","stats")),Map.of("resource",Map.of("type","question"))),
            "actions",List.of(Map.of("type","PRACTICE_CREATE")));
        assertEquals(List.of("PRACTICE","NOTES","STATS","SCHOOLS"),navigation.targets(result,false).stream().map(item->item.get("target")).toList());
    }
}
