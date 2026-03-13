package com.example.beapp.persistence.repository;

import java.util.Optional;

import org.springframework.context.annotation.Profile;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Repository;

import com.example.beapp.model.UserAccount;
import com.example.beapp.persistence.entity.UserEntity;
import com.example.beapp.repository.UserAccountRepository;

@Repository
@Primary
@Profile("!test")
public class JpaUserAccountRepositoryAdapter implements UserAccountRepository {

    private final UserJpaRepository userJpaRepository;

    public JpaUserAccountRepositoryAdapter(UserJpaRepository userJpaRepository) {
        this.userJpaRepository = userJpaRepository;
    }

    @Override
    public Optional<UserAccount> findByUserId(String userId) {
        return userJpaRepository.findByUserId(userId).map(this::toModel);
    }

    @Override
    public boolean existsByUserId(String userId) {
        return userJpaRepository.existsByUserId(userId);
    }

    @Override
    public UserAccount save(UserAccount userAccount) {
        UserEntity entity = userJpaRepository.findByUserId(userAccount.userID())
                .map(existing -> existing.update(
                        userAccount.encodedPassword(),
                        toShort(userAccount.age()),
                        userAccount.gender()))
                .orElseGet(() -> new UserEntity(
                        userAccount.userID(),
                        userAccount.encodedPassword(),
                        toShort(userAccount.age()),
                        userAccount.gender()));

        UserEntity saved = userJpaRepository.save(entity);
        return toModel(saved);
    }

    @Override
    public void deleteByUserId(String userId) {
        userJpaRepository.findByUserId(userId).ifPresent(userJpaRepository::delete);
    }

    private UserAccount toModel(UserEntity entity) {
        return new UserAccount(
                entity.getUserId(),
                entity.getPasswordHash(),
                entity.getAge() == null ? null : entity.getAge().intValue(),
                entity.getGender());
    }

    private Short toShort(Integer value) {
        return value == null ? null : value.shortValue();
    }
}
