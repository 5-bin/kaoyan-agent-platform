package com.kaoyan;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * 考研 Agent 平台启动类
 */
@SpringBootApplication
@MapperScan("com.kaoyan.mapper")
@EnableFeignClients(basePackages = "com.kaoyan.feign")
public class KaoyanApplication {

    public static void main(String[] args) {
        SpringApplication.run(KaoyanApplication.class, args);
    }
}
