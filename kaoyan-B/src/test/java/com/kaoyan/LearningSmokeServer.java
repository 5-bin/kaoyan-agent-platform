package com.kaoyan;

import com.kaoyan.learning.*;
import org.springframework.boot.*;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import java.util.*;

/** Only isolated H2 fixtures. No production data and no external model. */
public class LearningSmokeServer {
 public static void main(String[] args) {new SpringApplication(KaoyanApplication.class,FrameworkSmokeServer.SmokeConfig.class,Fixtures.class).run(args);}
 @TestConfiguration(proxyBeanMethods=false)
 static class Fixtures {
  @Bean ApplicationRunner learningFixtures(JdbcTemplate db,PasswordEncoder passwords,LearningProfiles profiles) {
   return args -> {
    try(var c=db.getDataSource().getConnection()) {
     String url=c.getMetaData().getURL();boolean allowed=url.startsWith("jdbc:h2:mem:learning-loop-smoke");
     if(url.startsWith("jdbc:h2:file:")) {
      var parent=java.nio.file.Path.of(url.substring("jdbc:h2:file:".length()).split(";")[0]).getParent().toRealPath();
      allowed=parent.startsWith(java.nio.file.Path.of(System.getProperty("java.io.tmpdir")).toRealPath())&&parent.getFileName().toString().startsWith("kaoyan-learning-loop-");
     }
     if(!allowed)throw new IllegalStateException("Learning fixtures require isolated H2");
    }
    if(db.queryForObject("SELECT COUNT(*) FROM `user`",Integer.class)>0)return;
    for(String name:List.of("learning_student_1","learning_student_2"))db.update("INSERT INTO `user`(username,password_hash,role,status,target_major,exam_year) VALUES(?,?,'STUDENT',1,'081200',2027)",name,passwords.encode("test-only-learning-password"));
    var cells=new ArrayList<LearningContracts.Cell>();
    for(String subject:List.of("数据结构","计算机组成原理","操作系统","计算机网络")) {
     for(String difficulty:List.of("EASY","MEDIUM","HARD")) {
      int count="HARD".equals(difficulty)?1:2;
      for(int i=0;i<count;i++)db.update("INSERT INTO question(subject,knowledge_point,content,option_a,option_b,option_c,option_d,answer,analysis,difficulty,question_type,version,active,stable_order,review_status) VALUES(?,?,?,'选择甲','选择乙','选择丙','选择丁','B','隔离测试解析',?,'SINGLE_CHOICE',1,1,0,'APPROVED')",subject,subject+"基础",subject+"隔离测试题"+difficulty+i,difficulty);
      cells.add(new LearningContracts.Cell(subject,subject+"基础",LearningProfileEngine.pointId(subject,subject+"基础"),difficulty,count,count/20.0));
     }
    }
    long reviewer=db.queryForObject("SELECT id FROM `user` WHERE username='learning_student_1'",Long.class);
    // Reviewed synthetic blueprint only in this test process; never imports into the daily database.
    profiles.publish(new LearningContracts.Blueprint("isolated-fixture-v1",1,cells),reviewer);
   };
  }
 }
}
