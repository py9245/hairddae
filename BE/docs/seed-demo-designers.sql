-- 발표용 디자이너 데모 계정 10명 생성 SQL
-- 실행 위치 예시:
--   psql -U beapp -d beapp -f docs/seed-demo-designers.sql
--
-- 공통 로그인 정보
--   user_id:
--     godam_eunsu, godam_minji, godam_jiho
--     sillim_sujin, sillim_hyerin, sillim_donghyun
--     isu_yuna, isu_minseo, isu_haneul, isu_hyewon
--   password: P@ssw0rd1
--
-- 주의
-- - 이 스크립트는 godam_*, sillim_*, isu_* 계정에 대해서만 재실행 가능하도록 작성되었다.
-- - 기존 legacy demo 계정(designer_demo_01 ~ designer_demo_10)이 있으면 먼저 새 user_id로 이름만 변경한다.
-- - 기존 demo 계정의 specialties / applications / users 정보는 같은 user_id에 한해 갱신된다.

BEGIN;

ALTER TABLE designer_applications
    DROP CONSTRAINT IF EXISTS fk_designer_applications_user_id;

ALTER TABLE designer_specialties
    DROP CONSTRAINT IF EXISTS fk_designer_specialties_user;

WITH legacy_user_mapping AS (
    SELECT *
    FROM (
        VALUES
            ('designer_demo_01', 'godam_eunsu'),
            ('designer_demo_02', 'godam_minji'),
            ('designer_demo_03', 'godam_jiho'),
            ('designer_demo_04', 'sillim_sujin'),
            ('designer_demo_05', 'sillim_hyerin'),
            ('designer_demo_06', 'sillim_donghyun'),
            ('designer_demo_07', 'isu_yuna'),
            ('designer_demo_08', 'isu_minseo'),
            ('designer_demo_09', 'isu_haneul'),
            ('designer_demo_10', 'isu_hyewon')
    ) AS t(old_user_id, new_user_id)
)
UPDATE users u
SET user_id = m.new_user_id,
    updated_at = CURRENT_TIMESTAMP
FROM legacy_user_mapping m
WHERE u.user_id = m.old_user_id
  AND NOT EXISTS (
      SELECT 1
      FROM users existing_user
      WHERE existing_user.user_id = m.new_user_id
  );

WITH legacy_user_mapping AS (
    SELECT *
    FROM (
        VALUES
            ('designer_demo_01', 'godam_eunsu'),
            ('designer_demo_02', 'godam_minji'),
            ('designer_demo_03', 'godam_jiho'),
            ('designer_demo_04', 'sillim_sujin'),
            ('designer_demo_05', 'sillim_hyerin'),
            ('designer_demo_06', 'sillim_donghyun'),
            ('designer_demo_07', 'isu_yuna'),
            ('designer_demo_08', 'isu_minseo'),
            ('designer_demo_09', 'isu_haneul'),
            ('designer_demo_10', 'isu_hyewon')
    ) AS t(old_user_id, new_user_id)
)
UPDATE designer_applications da
SET user_id = m.new_user_id,
    updated_at = CURRENT_TIMESTAMP
FROM legacy_user_mapping m
WHERE da.user_id = m.old_user_id
  AND EXISTS (
      SELECT 1
      FROM users u
      WHERE u.user_id = m.new_user_id
  );

WITH legacy_user_mapping AS (
    SELECT *
    FROM (
        VALUES
            ('designer_demo_01', 'godam_eunsu'),
            ('designer_demo_02', 'godam_minji'),
            ('designer_demo_03', 'godam_jiho'),
            ('designer_demo_04', 'sillim_sujin'),
            ('designer_demo_05', 'sillim_hyerin'),
            ('designer_demo_06', 'sillim_donghyun'),
            ('designer_demo_07', 'isu_yuna'),
            ('designer_demo_08', 'isu_minseo'),
            ('designer_demo_09', 'isu_haneul'),
            ('designer_demo_10', 'isu_hyewon')
    ) AS t(old_user_id, new_user_id)
)
UPDATE designer_specialties ds
SET user_id = m.new_user_id,
    updated_at = CURRENT_TIMESTAMP
FROM legacy_user_mapping m
WHERE ds.user_id = m.old_user_id
  AND EXISTS (
      SELECT 1
      FROM users u
      WHERE u.user_id = m.new_user_id
  );

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_designer_applications_user_id'
    ) THEN
        ALTER TABLE designer_applications
            ADD CONSTRAINT fk_designer_applications_user_id
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_designer_specialties_user'
    ) THEN
        ALTER TABLE designer_specialties
            ADD CONSTRAINT fk_designer_specialties_user
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE;
    END IF;
END $$;

WITH demo_users AS (
    SELECT *
    FROM (
        VALUES
            ('godam_eunsu', '$2b$12$G..rAHCCsp.h/5Waom.ekuHqmkcS.yLqgnCBMOMSZzKaYmdBDuooy', 'M', DATE '1994-02-14', 'CERT-DEMO-001', DATE '2021-03-15', '서울특별시 강남구 테헤란로 212 멀티캠퍼스', 37.5012748::double precision, 127.0396250::double precision),
            ('godam_minji', '$2b$12$G..rAHCCsp.h/5Waom.ekuHqmkcS.yLqgnCBMOMSZzKaYmdBDuooy', 'F', DATE '1993-07-11', 'CERT-DEMO-002', DATE '2020-05-22', '서울특별시 강남구 테헤란로 521 파르나스타워', 37.5093629::double precision, 127.0602114::double precision),
            ('godam_jiho', '$2b$12$G..rAHCCsp.h/5Waom.ekuHqmkcS.yLqgnCBMOMSZzKaYmdBDuooy', 'M', DATE '1991-11-02', 'CERT-DEMO-003', DATE '2019-09-10', '서울특별시 서초구 서초대로 77', 37.4930000::double precision, 127.0170000::double precision),
            ('sillim_sujin', '$2b$12$G..rAHCCsp.h/5Waom.ekuHqmkcS.yLqgnCBMOMSZzKaYmdBDuooy', 'F', DATE '1995-03-28', 'CERT-DEMO-004', DATE '2022-01-18', '서울특별시 송파구 올림픽로 300', 37.5133000::double precision, 127.1028000::double precision),
            ('sillim_hyerin', '$2b$12$G..rAHCCsp.h/5Waom.ekuHqmkcS.yLqgnCBMOMSZzKaYmdBDuooy', 'F', DATE '1990-08-19', 'CERT-DEMO-005', DATE '2018-06-01', '서울특별시 강남구 봉은사로 524', 37.5121000::double precision, 127.0585000::double precision),
            ('sillim_donghyun', '$2b$12$G..rAHCCsp.h/5Waom.ekuHqmkcS.yLqgnCBMOMSZzKaYmdBDuooy', 'M', DATE '1989-12-05', 'CERT-DEMO-006', DATE '2017-04-12', '서울특별시 강남구 도산대로 442', 37.5231000::double precision, 127.0437000::double precision),
            ('isu_yuna', '$2b$12$G..rAHCCsp.h/5Waom.ekuHqmkcS.yLqgnCBMOMSZzKaYmdBDuooy', 'F', DATE '1996-01-30', 'CERT-DEMO-007', DATE '2023-02-08', '서울특별시 마포구 양화로 45', 37.5508000::double precision, 126.9142000::double precision),
            ('isu_minseo', '$2b$12$G..rAHCCsp.h/5Waom.ekuHqmkcS.yLqgnCBMOMSZzKaYmdBDuooy', 'F', DATE '1992-10-17', 'CERT-DEMO-008', DATE '2020-10-20', '서울특별시 성동구 아차산로 83', 37.5478000::double precision, 127.0566000::double precision),
            ('isu_haneul', '$2b$12$G..rAHCCsp.h/5Waom.ekuHqmkcS.yLqgnCBMOMSZzKaYmdBDuooy', 'M', DATE '1993-04-09', 'CERT-DEMO-009', DATE '2021-12-03', '서울특별시 노원구 노원로 431 노원역지구대', 37.6543210::double precision, 127.0612340::double precision),
            ('isu_hyewon', '$2b$12$G..rAHCCsp.h/5Waom.ekuHqmkcS.yLqgnCBMOMSZzKaYmdBDuooy', 'F', DATE '1997-06-21', 'CERT-DEMO-010', DATE '2024-01-10', '서울특별시 강동구 천호대로 1005', 37.5382000::double precision, 127.1231000::double precision)
    ) AS t(user_id, password_hash, gender, birth_date, certificate_number, acquisition_date, salon_address, salon_latitude, salon_longitude)
)
INSERT INTO users (
    user_id,
    password_hash,
    gender,
    birth_date,
    login_type,
    provider_subject,
    grade,
    created_at,
    updated_at
)
SELECT
    user_id,
    password_hash,
    gender,
    birth_date,
    0,
    NULL,
    2,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM demo_users
ON CONFLICT (user_id) DO UPDATE
SET password_hash = EXCLUDED.password_hash,
    gender = EXCLUDED.gender,
    birth_date = EXCLUDED.birth_date,
    login_type = EXCLUDED.login_type,
    provider_subject = EXCLUDED.provider_subject,
    grade = EXCLUDED.grade,
    updated_at = CURRENT_TIMESTAMP;

WITH demo_users AS (
    SELECT *
    FROM (
        VALUES
            ('godam_eunsu', 'CERT-DEMO-001', DATE '2021-03-15', '서울특별시 강남구 테헤란로 212 멀티캠퍼스', 37.5012748::double precision, 127.0396250::double precision),
            ('godam_minji', 'CERT-DEMO-002', DATE '2020-05-22', '서울특별시 강남구 테헤란로 521 파르나스타워', 37.5093629::double precision, 127.0602114::double precision),
            ('godam_jiho', 'CERT-DEMO-003', DATE '2019-09-10', '서울특별시 서초구 서초대로 77', 37.4930000::double precision, 127.0170000::double precision),
            ('sillim_sujin', 'CERT-DEMO-004', DATE '2022-01-18', '서울특별시 송파구 올림픽로 300', 37.5133000::double precision, 127.1028000::double precision),
            ('sillim_hyerin', 'CERT-DEMO-005', DATE '2018-06-01', '서울특별시 강남구 봉은사로 524', 37.5121000::double precision, 127.0585000::double precision),
            ('sillim_donghyun', 'CERT-DEMO-006', DATE '2017-04-12', '서울특별시 강남구 도산대로 442', 37.5231000::double precision, 127.0437000::double precision),
            ('isu_yuna', 'CERT-DEMO-007', DATE '2023-02-08', '서울특별시 마포구 양화로 45', 37.5508000::double precision, 126.9142000::double precision),
            ('isu_minseo', 'CERT-DEMO-008', DATE '2020-10-20', '서울특별시 성동구 아차산로 83', 37.5478000::double precision, 127.0566000::double precision),
            ('isu_haneul', 'CERT-DEMO-009', DATE '2021-12-03', '서울특별시 노원구 노원로 431 노원역지구대', 37.6543210::double precision, 127.0612340::double precision),
            ('isu_hyewon', 'CERT-DEMO-010', DATE '2024-01-10', '서울특별시 강동구 천호대로 1005', 37.5382000::double precision, 127.1231000::double precision)
    ) AS t(user_id, certificate_number, acquisition_date, salon_address, salon_latitude, salon_longitude)
)
INSERT INTO designer_applications (
    user_id,
    certificate_number,
    salon_address,
    acquisition_date,
    salon_latitude,
    salon_longitude,
    created_at,
    updated_at
)
SELECT
    user_id,
    certificate_number,
    salon_address,
    acquisition_date,
    salon_latitude,
    salon_longitude,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM demo_users
ON CONFLICT (user_id) DO UPDATE
SET certificate_number = EXCLUDED.certificate_number,
    salon_address = EXCLUDED.salon_address,
    acquisition_date = EXCLUDED.acquisition_date,
    salon_latitude = EXCLUDED.salon_latitude,
    salon_longitude = EXCLUDED.salon_longitude,
    updated_at = CURRENT_TIMESTAMP;

DELETE FROM designer_specialties
WHERE user_id IN (
    'godam_eunsu',
    'godam_minji',
    'godam_jiho',
    'sillim_sujin',
    'sillim_hyerin',
    'sillim_donghyun',
    'isu_yuna',
    'isu_minseo',
    'isu_haneul',
    'isu_hyewon'
);

INSERT INTO designer_specialties (
    user_id,
    category_id,
    created_at,
    updated_at
)
VALUES
    ('godam_eunsu', '댄디컷', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('godam_eunsu', '가르마', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('godam_minji', '가르마', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('godam_minji', '긴머리', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('godam_jiho', '댄디컷', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('godam_jiho', '리젠트컷', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('sillim_sujin', '긴머리', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('sillim_sujin', '묶은머리', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('sillim_hyerin', '히피펌', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('sillim_hyerin', '긴머리', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('sillim_donghyun', '버즈컷', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('sillim_donghyun', '리젠트컷', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('isu_yuna', '단발펌', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('isu_yuna', '히피펌', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('isu_minseo', '묶은머리', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('isu_minseo', '긴머리', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('isu_haneul', '가르마', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('isu_haneul', '단발펌', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('isu_hyewon', '댄디컷', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('isu_hyewon', '버즈컷', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

COMMIT;

-- 확인용 조회
-- SELECT user_id, grade FROM users WHERE user_id LIKE 'godam_%' OR user_id LIKE 'sillim_%' OR user_id LIKE 'isu_%' ORDER BY user_id;
-- SELECT user_id, salon_address, salon_latitude, salon_longitude FROM designer_applications WHERE user_id LIKE 'godam_%' OR user_id LIKE 'sillim_%' OR user_id LIKE 'isu_%' ORDER BY user_id;
-- SELECT user_id, category_id FROM designer_specialties WHERE user_id LIKE 'godam_%' OR user_id LIKE 'sillim_%' OR user_id LIKE 'isu_%' ORDER BY user_id, category_id;
