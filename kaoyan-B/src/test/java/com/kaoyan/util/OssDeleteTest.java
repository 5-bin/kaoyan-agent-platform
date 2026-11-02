package com.kaoyan.util;

import com.aliyun.oss.OSS;
import com.kaoyan.common.ApiException;
import com.kaoyan.config.OssProperties;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class OssDeleteTest {
    private final OSS client = mock(OSS.class);

    private OssUtil util() {
        OssProperties properties = new OssProperties();
        properties.setEndpoint("https://oss-cn-shenzhen.aliyuncs.com");
        properties.setBucketName("example");
        OssUtil util = new OssUtil(properties);
        ReflectionTestUtils.setField(util, "ossClient", client);
        return util;
    }

    @Test
    void uploadBindsEveryModuleToOwner() {
        String key = util().upload(new MockMultipartFile("file", "a.png", "image/png", new byte[]{1}), "common", 7L);
        assertTrue(key.matches("common/7/[0-9]{8}/[a-f0-9]+\\.png"), key);
        verify(client).putObject(eq("example"), eq(key), any(InputStream.class));
    }

    @Test
    void deletesOnlyOwnObjects() {
        OssUtil util = util();
        util.delete("common/1/20261102/abc123.png", 1L, null);
        verify(client).deleteObject("example", "common/1/20261102/abc123.png");

        for (String key : new String[]{
                "avatar/2/20261102/abc123.png",
                "avatar/12/20261102/abc123.png",
                "avatar/20261031/abc123.png",
                "avatar/1/../2/20261102/abc123.png",
                "private/secret.png",
                ""}) {
            ApiException error = assertThrows(ApiException.class, () -> util.delete(key, 1L, null), key);
            assertEquals(404, error.getHttpStatus(), key);
        }
        assertThrows(ApiException.class, () -> util.delete(null, 1L, null));
        verify(client, times(1)).deleteObject(anyString(), anyString());
    }

    @Test
    void refusesCurrentAvatar() {
        OssUtil util = util();
        String key = "avatar/1/20261102/abc123.png";
        ApiException error = assertThrows(ApiException.class, () -> util.delete(key, 1L, util.buildUrl(key)));
        assertEquals(409, error.getHttpStatus());
        verify(client, never()).deleteObject(anyString(), anyString());
    }
}
