package course.kaoyan.auth;

import course.kaoyan.pojo.entity.auth.Account;

import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AccountRepository extends JpaRepository<Account, String> {
    Optional<Account> findByUsername(String username);
}

