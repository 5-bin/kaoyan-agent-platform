package com.kaoyan.util;

import com.aliyun.oss.ClientException;
import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSException;
import com.aliyun.oss.model.OSSObject;
import com.kaoyan.common.ApiException;
import com.kaoyan.config.OssProperties;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.util.ReflectionTestUtils;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class OssNamespaceTest {
    private final OSS client = mock(OSS.class);
    private OssProperties properties(String namespace) {
        var props = new OssProperties();
        props.setEndpoint("https://oss-cn-shenzhen.aliyuncs.com");props.setBucketName("example");
        props.setKeyPrefix(namespace);return props;
    }
    private OssUtil util(String namespace) {
        var util = new OssUtil(properties(namespace));
        ReflectionTestUtils.setField(util,"ossClient",client);return util;
    }
    @Test void namespaceIsOptionalNormalizedAndValidated() {
        assertEquals("",properties("").normalizedKeyPrefix());
        assertEquals("prod/",properties("prod").normalizedKeyPrefix());
        assertEquals("prod/app/",properties("prod/app/").normalizedKeyPrefix());
        for(String invalid:new String[]{"/","/prod","../prod","prod/../local","prod//app","prod//","https://x","prod\\x"," prod ","prod/?x","x".repeat(129)}) {
            var props=properties(invalid);
            assertThrows(IllegalStateException.class,props::normalizedKeyPrefix,invalid);
            assertThrows(IllegalStateException.class,()->new OssUtil(props).init(),invalid);
        }
    }
    @Test void uploadAndUrlUseExactlyOneNamespace() {
        var util=util("prod/");
        String key=util.upload(new MockMultipartFile("file","a.png","image/png",new byte[]{1}),"avatar",7L);
        assertTrue(key.matches("prod/avatar/7/[0-9]{8}/[a-f0-9]+\\.png"));
        assertEquals("https://example.oss-cn-shenzhen.aliyuncs.com/"+key,util.buildUrl(key));
        verify(client).putObject(eq("example"),eq(key),any(InputStream.class));
        assertThrows(ApiException.class,()->util.upload(new MockMultipartFile("file","a.png","image/png",new byte[]{1}),"avatar"));
    }
    @Test void bindingsAndDeletesRejectOtherNamespaceAndOwnerWithoutOssCalls() {
        var util=util("prod/");
        String own="prod/avatar/7/20261103/abc123.png";
        assertTrue(util.isAllowedAvatar(util.buildUrl(own),7L,null));
        for(String key:new String[]{"avatar/7/20261103/abc123.png","dev/avatar/7/20261103/abc123.png","prod/avatar/8/20261103/abc123.png","prod/avatar/7/../8/20261103/abc123.png","prod/avatar/20261103/abc123.png"}) {
            String url=util.buildUrl(key);
            assertFalse(util.isAllowedAvatar(url,7L,url));
            assertEquals(404,assertThrows(ApiException.class,()->util.delete(key,7L,null)).getHttpStatus());
        }
        assertEquals(409,assertThrows(ApiException.class,()->util.delete(own,7L,util.buildUrl(own))).getHttpStatus());
        verifyNoInteractions(client);
        util.delete(own,7L,null);verify(client).deleteObject("example",own);
    }
    @Test void avatarReadsAreNamespaceScoped() {
        var util=util("prod/");String key="prod/avatar/7/20261103/abc123.png";
        var object=mock(OSSObject.class);
        when(object.getObjectContent()).thenReturn(new ByteArrayInputStream(new byte[]{1,2,3}));
        when(client.getObject("example",key)).thenReturn(object);
        assertArrayEquals(new byte[]{1,2,3},util.readAvatar(util.buildUrl(key)));
        for(String invalid:new String[]{"avatar/7/20261103/abc123.png","prod/avatar/20261103/abc123.png","dev/avatar/7/20261103/abc123.png"})
            assertEquals(404,assertThrows(ApiException.class,()->util.readAvatar(util.buildUrl(invalid))).getHttpStatus());
        verify(client,times(1)).getObject(anyString(),anyString());
    }
    @Test void existingFileValidationStillPrecedesOss() {
        var util=util("prod/");
        for(var file:new MockMultipartFile[]{new MockMultipartFile("file","a.png","image/png",new byte[0]),new MockMultipartFile("file","a.exe","image/png",new byte[]{1}),new MockMultipartFile("file","a.png","image/png",new byte[5*1024*1024+1])})
            assertEquals(400,assertThrows(ApiException.class,()->util.upload(file,"avatar",7L)).getHttpStatus());
        verifyNoInteractions(client);
    }
    @Test void failuresDoNotExposeProviderMessageOrCredentials() {
        var util=util("prod/");
        when(client.putObject(anyString(),anyString(),any(InputStream.class))).thenThrow(new OSSException("synthetic-secret-value"));
        assertEquals("上传失败",assertThrows(ApiException.class,()->util.upload(new MockMultipartFile("file","a.png","image/png",new byte[]{1}),"avatar",7L)).getMessage());
        when(client.getObject(anyString(),anyString())).thenThrow(new ClientException("synthetic-secret-value"));
        assertEquals("头像读取失败",assertThrows(ApiException.class,()->util.readAvatar(util.buildUrl("prod/avatar/7/20261103/abc123.png"))).getMessage());
        doThrow(new OSSException("synthetic-secret-value")).when(client).deleteObject(anyString(),anyString());
        assertEquals("删除失败",assertThrows(ApiException.class,()->util.delete("prod/avatar/7/20261103/abc123.png",7L,null)).getMessage());
        var props=properties("prod/");props.setAccessKeyId("synthetic-id");props.setAccessKeySecret("synthetic-secret-value");
        assertFalse(props.toString().contains("synthetic-id"));assertFalse(props.toString().contains("synthetic-secret-value"));
    }
}
