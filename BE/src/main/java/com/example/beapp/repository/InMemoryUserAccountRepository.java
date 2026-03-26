package com.example.beapp.repository;

import java.time.LocalDate;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Repository;

import com.example.beapp.model.LoginType;
import com.example.beapp.model.UserAccount;

@Repository
@Profile("test")
public class InMemoryUserAccountRepository implements UserAccountRepository {

    private final Map<String, UserAccount> users = new ConcurrentHashMap<>();

    public InMemoryUserAccountRepository(PasswordEncoder passwordEncoder) {
        save(new UserAccount("TestUser01", passwordEncoder.encode("P@ssw0rd1"), LocalDate.of(2000, 1, 1), "M"));
        save(new UserAccount("GoogleUser01", passwordEncoder.encode("G00gle!1"), LocalDate.of(1999, 5, 20), "F", LoginType.GOOGLE, "seed-google-subject-01"));
    }

    @Override
    public Optional<UserAccount> findByUserId(String userId) {
        return Optional.ofNullable(users.get(userId));
    }

    @Override
    public Optional<UserAccount> findByProviderSubject(String providerSubject) {
        return users.values().stream()
                .filter(userAccount -> providerSubject != null && providerSubject.equals(userAccount.providerSubject()))
                .findFirst();
    }

    @Override
    public boolean existsByUserId(String userId) {
        return users.containsKey(userId);
    }

    @Override
    public UserAccount save(UserAccount userAccount) {
        findByProviderSubject(userAccount.providerSubject())
                .filter(existing -> !existing.userID().equals(userAccount.userID()))
                .ifPresent(existing -> users.remove(existing.userID()));
        users.put(userAccount.userID(), userAccount);
        return userAccount;
    }

    @Override
    public void deleteByUserId(String userId) {
        users.remove(userId);
    }
}
