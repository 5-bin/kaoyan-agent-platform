package com.kaoyan.util;

import com.aliyun.oss.OSS;
import com.aliyun.oss.model.OSSObject;

import java.io.ByteArrayInputStream;
import com.kaoyan.config.OssProperties;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;


import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class OssAvatarTest {
    @Test
    void restrictsNewBindingsToOwner() {
        OssProperties properties = new OssProperties();
        properties.setEndpoint("https://oss-cn-shenzhen.aliyuncs.com");
        properties.setBucketName("example");
        OssUtil util = new OssUtil(properties);
        OSS client = mock(OSS.class);
        ReflectionTestUtils.setField(util, "ossClient", client);
        String old = util.buildUrl("avatar/20261031/abc123.png");
        OSSObject object = mock(OSSObject.class);
        when(object.getObjectContent()).thenReturn(new ByteArrayInputStream(new byte[]{1, 2, 3}));
        when(client.getObject("example", "avatar/20261031/abc123.png")).thenReturn(object);
        assertArrayEquals(new byte[]{1, 2, 3}, util.readAvatar(old));
        assertTrue(util.isAllowedAvatar(old, 1L, old));
        assertTrue(util.isAllowedAvatar(util.buildUrl("avatar/1/20261031/abc123.png"), 1L, old));
        assertFalse(util.isAllowedAvatar(util.buildUrl("avatar/2/20261031/abc123.png"), 1L, old));
        assertFalse(util.isAllowedAvatar(util.buildUrl("private/secret.png"), 1L, old));
        assertThrows(com.kaoyan.common.ApiException.class, () -> util.readAvatar(util.buildUrl("private/secret.png")));
        verify(client, times(1)).getObject(anyString(), anyString());
    }
}
