package com.example.beapp.repository;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Repository;

import com.example.beapp.model.UserAccount;

@Repository
@Profile("test")
public class InMemoryUserAccountRepository implements UserAccountRepository {

    private final Map<String, UserAccount> users = new ConcurrentHashMap<>();

    public InMemoryUserAccountRepository(PasswordEncoder passwordEncoder) {
        save(new UserAccount("TestUser01", passwordEncoder.encode("P@ssw0rd1"), 25, "M"));
    }

    @Override
    public Optional<UserAccount> findByUserId(String userId) {
        return Optional.ofNullable(users.get(userId));
    }

    @Override
    public boolean existsByUserId(String userId) {
        return users.containsKey(userId);
    }

    @Override
    public UserAccount save(UserAccount userAccount) {
        users.put(userAccount.userID(), userAccount);
        return userAccount;
    }

    @Override
    public void deleteByUserId(String userId) {
        users.remove(userId);
    }
}
