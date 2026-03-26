import { test as setup, expect } from '@playwright/test';
import path from 'path';

export const authFile = path.join(__dirname, '../playwright/.auth/user.json');

setup('로그인 세션 저장', async ({ page }) => {
  await page.goto('/auth/login');
  await page.getByRole('textbox', { name: '아이디' }).fill('testusere2e');
  await page.getByRole('textbox', { name: '비밀번호' }).fill('Test1234!');
  await page.getByRole('button', { name: '로그인' }).click();
  await expect(page).toHaveURL(/\/main/);

  await page.context().storageState({ path: authFile });
});
