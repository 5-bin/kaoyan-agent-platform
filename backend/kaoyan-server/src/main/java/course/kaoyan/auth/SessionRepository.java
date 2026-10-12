package course.kaoyan.auth;

import course.kaoyan.pojo.entity.auth.Session;

import org.springframework.data.jpa.repository.JpaRepository;

public interface SessionRepository extends JpaRepository<Session, String> {}

