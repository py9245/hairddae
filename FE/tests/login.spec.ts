import { test, expect } from '@playwright/test';

test.describe('로그인 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/auth/login');
    // 로그인 상태라면 로그아웃 후 재접속
    if (page.url().includes('/main') || page.url().includes('/mypage')) {
      await page.goto('/auth/login');
    }
  });

  test('로그인 페이지에 아이디·비밀번호 입력 필드와 로그인 버튼이 존재해야 한다', async ({
    page,
  }) => {
    await expect(page.getByRole('textbox', { name: '아이디' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: '비밀번호' })).toBeVisible();
    await expect(page.getByRole('button', { name: '로그인' })).toBeVisible();
  });

  test('아이디·비밀번호가 비어있으면 로그인 버튼이 비활성화 되어야 한다', async ({
    page,
  }) => {
    await expect(page.getByRole('button', { name: '로그인' })).toBeDisabled();
  });

  test('아이디만 입력하면 로그인 버튼이 비활성화 되어야 한다', async ({ page }) => {
    await page.getByRole('textbox', { name: '아이디' }).fill('testusere2e');
    await expect(page.getByRole('button', { name: '로그인' })).toBeDisabled();
  });

  test('비밀번호만 입력하면 로그인 버튼이 비활성화 되어야 한다', async ({ page }) => {
    await page.getByRole('textbox', { name: '비밀번호' }).fill('Test1234!');
    await expect(page.getByRole('button', { name: '로그인' })).toBeDisabled();
  });

  test('아이디·비밀번호를 모두 입력하면 로그인 버튼이 활성화 되어야 한다', async ({
    page,
  }) => {
    await page.getByRole('textbox', { name: '아이디' }).fill('testusere2e');
    await page.getByRole('textbox', { name: '비밀번호' }).fill('Test1234!');
    await expect(page.getByRole('button', { name: '로그인' })).toBeEnabled();
  });

  test('잘못된 비밀번호 입력 시 에러 메시지가 표시되어야 한다', async ({ page }) => {
    await page.getByRole('textbox', { name: '아이디' }).fill('testusere2e');
    await page.getByRole('textbox', { name: '비밀번호' }).fill('WrongPass1!');

    await page.getByRole('button', { name: '로그인' }).click();

    // 에러 메시지가 표시될 때까지 대기
    const errorMessage = page.locator('p.text-red-500');
    await expect(errorMessage).toBeVisible();
    await expect(errorMessage).not.toBeEmpty();
  });

  test('존재하지 않는 아이디로 로그인 시 에러 메시지가 표시되어야 한다', async ({
    page,
  }) => {
    await page.getByRole('textbox', { name: '아이디' }).fill('nonexistuser99');
    await page.getByRole('textbox', { name: '비밀번호' }).fill('WrongPass1!');

    await page.getByRole('button', { name: '로그인' }).click();

    const errorMessage = page.locator('p.text-red-500');
    await expect(errorMessage).toBeVisible();
    await expect(errorMessage).not.toBeEmpty();
  });

  test('올바른 아이디·비밀번호로 로그인 시 메인 페이지로 이동해야 한다', async ({
    page,
  }) => {
    await page.getByRole('textbox', { name: '아이디' }).fill('testusere2e');
    await page.getByRole('textbox', { name: '비밀번호' }).fill('Test1234!');

    await page.getByRole('button', { name: '로그인' }).click();

    await expect(page).toHaveURL(/\/main/);
  });

  test('회원가입 링크를 클릭하면 회원가입 페이지로 이동해야 한다', async ({ page }) => {
    await page.getByRole('link', { name: '회원가입' }).click();
    await expect(page).toHaveURL(/\/auth\/signup/);
  });

  test('비밀번호 표시/숨기기 버튼이 동작해야 한다', async ({ page }) => {
    const passwordInput = page.getByRole('textbox', { name: '비밀번호' });
    const toggleButton = page.getByRole('button', { name: '비밀번호 보기' });

    await passwordInput.fill('Test1234!');

    // 초기 상태: 비밀번호 숨김
    await expect(passwordInput).toHaveAttribute('type', 'password');

    // 토글 클릭 → 비밀번호 보임
    await toggleButton.click();
    await expect(passwordInput).toHaveAttribute('type', 'text');

    // 다시 클릭 → 비밀번호 숨김
    await page.getByRole('button', { name: '비밀번호 숨기기' }).click();
    await expect(passwordInput).toHaveAttribute('type', 'password');
  });
});
