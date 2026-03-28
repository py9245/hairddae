package com.example.beapp.repository;

import java.util.Optional;

import com.example.beapp.model.UserAccount;

public interface UserAccountRepository {
    Optional<UserAccount> findByUserId(String userId);

    Optional<UserAccount> findByProviderSubject(String providerSubject);

    boolean existsByUserId(String userId);

    UserAccount save(UserAccount userAccount);

    void deleteByUserId(String userId);
}
