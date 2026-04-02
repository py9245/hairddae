import { test, expect, type Page } from '@playwright/test';

// 테스트용 계정 (tests/login.spec.ts 에서 생성한 계정)
const TEST_USER = { id: 'testusere2e', password: 'Test1234!' };

async function login(page: Page) {
  await page.goto('/auth/login');
  await page.getByRole('textbox', { name: '아이디' }).fill(TEST_USER.id);
  await page.getByRole('textbox', { name: '비밀번호' }).fill(TEST_USER.password);
  await page.getByRole('button', { name: '로그인' }).click();
  await expect(page).toHaveURL(/\/main/);
}

// ──────────────────────────────────────────────
// 1. 인증 가드
// ──────────────────────────────────────────────
test.describe('인증 가드', () => {
  test('비로그인 상태에서 /main 접근 시 로그인 페이지로 리다이렉트 되어야 한다', async ({
    page,
  }) => {
    await page.goto('/main');
    await expect(page).toHaveURL(/\/auth\/login/);
  });
});

// ──────────────────────────────────────────────
// 2. 기본 UI
// ──────────────────────────────────────────────
test.describe('기본 UI', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('헤어때 로고가 보여야 한다', async ({ page }) => {
    await expect(page.getByAltText('헤어때 로고')).toBeVisible();
  });

  test('사용자 이름이 포함된 추천 헤어 타이틀이 보여야 한다', async ({ page }) => {
    const title = page.getByRole('heading', { level: 2 });
    await expect(title).toBeVisible();
    await expect(title).toContainText(TEST_USER.id);
  });

  test('하단 네비게이션 탭 3개(카메라·홈·내 정보)가 모두 보여야 한다', async ({
    page,
  }) => {
    await expect(page.getByRole('link', { name: '카메라' })).toBeVisible();
    await expect(page.getByRole('link', { name: '홈' })).toBeVisible();
    await expect(page.getByRole('link', { name: '내 정보' })).toBeVisible();
  });

  test('홈 탭이 현재 활성화 상태여야 한다', async ({ page }) => {
    const homeLink = page.getByRole('link', { name: '홈' });
    await expect(homeLink).toHaveAttribute('aria-current', 'page');
  });
});

// ──────────────────────────────────────────────
// 3. 맞춤 추천 배너
// ──────────────────────────────────────────────
test.describe('맞춤 추천 배너', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('추천 헤어 배너 영역이 렌더링 되어야 한다', async ({ page }) => {
    // 배너 또는 빈 상태 메시지 중 하나가 반드시 노출
    const banner = page.locator('article').first();
    await expect(banner).toBeVisible();
  });

  test('맞춤 추천 헤어가 없을 때 빈 상태 메시지가 표시되어야 한다', async ({
    page,
  }) => {
    // DB 데이터가 없는 환경에서 확인
    const emptyMessage = page.getByText(/맞춤 추천 헤어가 없습니다/);
    await expect(emptyMessage).toBeVisible();
  });
});

// ──────────────────────────────────────────────
// 4. 카테고리 섹션
// ──────────────────────────────────────────────
test.describe('카테고리 섹션', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('"전체" 카테고리 버튼이 존재해야 한다', async ({ page }) => {
    await expect(page.getByRole('button', { name: '전체' })).toBeVisible();
  });

  test('카테고리 더보기 버튼이 존재해야 한다', async ({ page }) => {
    await expect(page.getByRole('button', { name: '카테고리 더보기' })).toBeVisible();
  });

  test('카테고리 더보기 버튼을 클릭할 수 있어야 한다', async ({ page }) => {
    const btn = page.getByRole('button', { name: '카테고리 더보기' });
    await expect(btn).toBeEnabled();
    await btn.click();
    // 클릭 후 에러 없이 페이지가 유지되어야 함
    await expect(page).toHaveURL(/\/main/);
  });
});

// ──────────────────────────────────────────────
// 5. 정렬 탭 (인기순 / 최신순)
// ──────────────────────────────────────────────
test.describe('정렬 탭', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('인기순·최신순 버튼이 모두 존재해야 한다', async ({ page }) => {
    await expect(page.getByRole('button', { name: '인기순' })).toBeVisible();
    await expect(page.getByRole('button', { name: '최신순' })).toBeVisible();
  });

  test('최신순 클릭 시 최신순 버튼이 활성화 되어야 한다', async ({ page }) => {
    await page.getByRole('button', { name: '최신순' }).click();
    // 활성 버튼은 aria-pressed=true 또는 시각적 구분이 있어야 함
    const latestBtn = page.getByRole('button', { name: '최신순' });
    await expect(latestBtn).toHaveAttribute('aria-pressed', 'true');
  });

  test('인기순 클릭 시 인기순 버튼이 활성화 되어야 한다', async ({ page }) => {
    // 먼저 최신순으로 전환
    await page.getByRole('button', { name: '최신순' }).click();
    // 다시 인기순으로 전환
    await page.getByRole('button', { name: '인기순' }).click();
    const popularBtn = page.getByRole('button', { name: '인기순' });
    await expect(popularBtn).toHaveAttribute('aria-pressed', 'true');
  });
});

// ──────────────────────────────────────────────
// 6. 하단 네비게이션 이동
// ──────────────────────────────────────────────
test.describe('하단 네비게이션', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('홈 탭 클릭 시 /main 페이지를 유지해야 한다', async ({ page }) => {
    await page.getByRole('link', { name: '홈' }).click();
    await expect(page).toHaveURL(/\/main/);
  });

  test('내 정보 탭 클릭 시 /mypage로 이동해야 한다', async ({ page }) => {
    await page.getByRole('link', { name: '내 정보' }).click();
    await expect(page).toHaveURL(/\/mypage/);
  });

  test('카메라 탭 클릭 시 /camera로 이동해야 한다', async ({ page }) => {
    await page.getByRole('link', { name: '카메라' }).click();
    await expect(page).toHaveURL(/\/camera/);
  });
});

// ──────────────────────────────────────────────
// 7. 마이페이지 (내 정보)
// ──────────────────────────────────────────────
test.describe('마이페이지', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.getByRole('link', { name: '내 정보' }).click();
    await expect(page).toHaveURL(/\/mypage/);
  });

  test('사용자 아이디가 표시되어야 한다', async ({ page }) => {
    await expect(page.getByText(TEST_USER.id)).toBeVisible();
  });

  test('로그아웃 버튼이 존재해야 한다', async ({ page }) => {
    await expect(page.getByRole('button', { name: '로그아웃' })).toBeVisible();
  });
});

// ──────────────────────────────────────────────
// 8. 로그아웃
// ──────────────────────────────────────────────
test.describe('로그아웃', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.getByRole('link', { name: '내 정보' }).click();
  });

  test('로그아웃 후 스플래시 페이지로 이동해야 한다', async ({ page }) => {
    await page.getByRole('button', { name: '로그아웃' }).click();
    await expect(page).toHaveURL(/^\//);
    await expect(page.getByRole('link', { name: '헤어 어때 시작하기' })).toBeVisible();
  });

  test('로그아웃 후 /main 접근 시 로그인 페이지로 리다이렉트 되어야 한다', async ({
    page,
  }) => {
    await page.getByRole('button', { name: '로그아웃' }).click();
    await page.goto('/main');
    await expect(page).toHaveURL(/\/auth\/login/);
  });
});
