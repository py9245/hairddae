import { expect, test, type Page } from '@playwright/test';

const mockHairList = {
  hairList: [
    {
      hairID: 1,
      image: 'https://example.com/classic-bob.png',
      hairName: 'Classic Bob',
      datasetCode: 'classic-bob',
    },
    {
      hairID: 2,
      image: 'https://example.com/wolf-cut.png',
      hairName: 'Wolf Cut',
      datasetCode: 'wolf-cut',
    },
  ],
};

async function installBrowserMocks(page: Page) {
  await page.addInitScript(() => {
    const mockPlay = async () => undefined;
    const mockPause = () => undefined;

    Object.defineProperty(HTMLMediaElement.prototype, 'play', {
      configurable: true,
      value: mockPlay,
    });

    Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
      configurable: true,
      value: mockPause,
    });

    Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', {
      configurable: true,
      get() {
        return 720;
      },
    });

    Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', {
      configurable: true,
      get() {
        return 1280;
      },
    });

    Object.defineProperty(HTMLCanvasElement.prototype, 'captureStream', {
      configurable: true,
      value() {
        return new MediaStream();
      },
    });

    Object.defineProperty(HTMLCanvasElement.prototype, 'toBlob', {
      configurable: true,
      value(callback: BlobCallback) {
        callback(new Blob(['camera-capture'], { type: 'image/png' }));
      },
    });

    Object.defineProperty(CanvasRenderingContext2D.prototype, 'drawImage', {
      configurable: true,
      value() {
        return undefined;
      },
    });

    if (!navigator.mediaDevices) {
      Object.defineProperty(navigator, 'mediaDevices', {
        configurable: true,
        value: {},
      });
    }

    Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {
      configurable: true,
      value: async () => new MediaStream(),
    });

    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: () => 'blob:camera-test',
    });

    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: () => undefined,
    });

    Object.defineProperty(HTMLAnchorElement.prototype, 'click', {
      configurable: true,
      value() {
        ;(window as Window & { __cameraLastDownload?: string }).__cameraLastDownload =
          this.download;
      },
    });
  });
}

async function mockAuthenticatedCameraRoutes(page: Page) {
  await page.route('**/api/me/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 200,
        message: 'ok',
        userID: 'camera-e2e',
        birthDate: null,
        gender: null,
      }),
    });
  });

  await page.route('**/api/accounts/refreshToken/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 200,
        message: 'ok',
      }),
    });
  });

  await page.route('**/api/hairs/cameralist/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockHairList),
    });
  });

  await page.route('**/api/home/hairapplybootstrap', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 200,
        message: 'ok',
        success: true,
        apply_session_id: 'session-1',
        rtc: {
          enabled: false,
          offer_url: 'https://rtc.example.com/offer',
          connect_ticket: 'ticket-1',
          expires_at: '2030-01-01T00:00:00.000Z',
          ice_servers: [],
        },
      }),
    });
  });

  await page.route('**/api/home/hairapplyresume', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 200,
        message: 'ok',
        success: true,
        apply_session_id: 'session-1',
        rtc: {
          enabled: false,
          offer_url: 'https://rtc.example.com/offer',
          connect_ticket: 'ticket-1',
          expires_at: '2030-01-01T00:00:00.000Z',
          ice_servers: [],
        },
      }),
    });
  });
}

async function mockUnauthenticatedRoutes(page: Page) {
  await page.route('**/api/me/', async (route) => {
    await route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'unauthorized' }),
    });
  });

  await page.route('**/api/accounts/refreshToken/', async (route) => {
    await route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'unauthorized' }),
    });
  });
}

async function openAuthenticatedCamera(page: Page, path = '/camera') {
  await installBrowserMocks(page);
  await mockAuthenticatedCameraRoutes(page);
  await page.goto(path, { waitUntil: 'domcontentloaded' });
}

test.describe('카메라 페이지', () => {
  test('비인증 사용자는 로그인 페이지로 리다이렉트된다', async ({
    page,
  }) => {
    await mockUnauthenticatedRoutes(page);

    await page.goto('/camera');

    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test('진입 후 카메라 화면과 헤어 선택 UI가 렌더링된다', async ({
    page,
  }) => {
    await openAuthenticatedCamera(page);

    await expect(page).toHaveURL(/\/camera$/);
    await expect(page.locator('video').first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'None' })).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Classic Bob' }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Wolf Cut' })).toBeVisible();
  });

  test('applyLatest 쿼리로 진입하면 첫 헤어가 자동 선택되고 쿼리가 제거된다', async ({
    page,
  }) => {
    await openAuthenticatedCamera(page, '/camera?applyLatest=true');

    await expect(page).toHaveURL(/\/camera$/);
    await expect(page.getByTestId('apply-style-modal')).toBeVisible();
  });

  test('설정 모달이 열리고 미러 토글을 변경할 수 있다', async ({
    page,
  }) => {
    await openAuthenticatedCamera(page);

    await page.getByTestId('camera-settings-button').click();

    const settingsModal = page.getByTestId('camera-settings-modal');
    const mirrorSwitch = page.getByRole('switch');

    await expect(settingsModal).toBeVisible();
    await expect(mirrorSwitch).toHaveAttribute('aria-checked', 'true');

    await mirrorSwitch.click();

    await expect(mirrorSwitch).toHaveAttribute('aria-checked', 'false');
  });

  test('선택된 헤어를 다시 누르면 프레임이 고정되고 다운로드 버튼이 나타난다', async ({
    page,
  }) => {
    await openAuthenticatedCamera(page);

    await page.getByRole('button', { name: 'None' }).click();

    const downloadButton = page.getByTestId('camera-download-button');
    await expect(downloadButton).toBeVisible();

    await downloadButton.click();

    await expect(downloadButton).toBeHidden();

    const downloadName = await page.evaluate(() => {
      return (
        (window as Window & { __cameraLastDownload?: string })
          .__cameraLastDownload ?? null
      );
    });

    expect(downloadName).toMatch(/^None-.*\.png$/);
  });
});
