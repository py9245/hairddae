import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveTitle(/헤어때/);
});

test('루트 페이지에 접속 시 시작 버튼이 존재해야 한다', async ({ page }) => {
  await page.goto('/');

  const startButton = page.getByRole('link', { name: '헤어 어때 시작하기' });
  await expect(startButton).toBeVisible();
});

test('루트 페이지에 접속 시 슬라이드가 넘어가야한다.', async ({ page }) => {
  await page.goto('/');

  const firstSlideTitle = page.getByText(/내가 원하는 헤어를/);
  await expect(firstSlideTitle).toBeVisible();

  // 3초 대기
  await page.waitForTimeout(3000);

  const secondSlideTitle = page.getByText(/인기있는 스타일과 함께/);
  await expect(secondSlideTitle).toBeVisible();
});

test('스와이프하여 수동으로 슬라이드를 넘길 수 있다.', async ({ page }) => {
  await page.goto('/');

  const firstSlideTitle = page.getByText(/내가 원하는 헤어를/);
  await expect(firstSlideTitle).toBeVisible();

  // 화면의 중앙쯤(또는 슬라이더 컨테이너)에서 마우스를 누른 채로 왼쪽으로 드래그(스와이프)합니다.
  // 실제 디바이스의 터치(Touch) 모션이나 마우스 드래그를 시뮬레이션합니다.
  
  // 1. 시작 위치로 커서 이동
  await page.mouse.move(400, 300);
  // 2. 터치 시작 (클릭 유지)
  await page.mouse.down();
  // 3. 왼쪽으로 이동 (스와이프 완료 위치). steps를 주어 부드러운 드래그 모션을 만듭니다.
  await page.mouse.move(100, 300, { steps: 10 });
  // 4. 터치 종료 (클릭 해제)
  await page.mouse.up();

  // 스와이프 모션 후 두 번째 슬라이드로 넘어갔는지 확인
  const secondSlideTitle = page.getByText(/인기있는 스타일과 함께/);
  await expect(secondSlideTitle).toBeVisible();
});