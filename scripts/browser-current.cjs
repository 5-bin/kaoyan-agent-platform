// 实际后端页面操作；账号切换后的迟到响应由拦截模拟。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.argv[2];
const diagnosticsDir = process.argv[3];

(async () => {
  const executablePath = process.env.CHROME_PATH || process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
  const browser = await chromium.launch({ executablePath, headless: true });
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
  const page = await context.newPage();
  const checks = [];
  // Only synthetic test accounts are used. Never record headers, bodies or full URLs.
  const diagnostics = { browserErrors: [], apiResponses: [], requestFailures: [] };
  page.on('pageerror', error => diagnostics.browserErrors.push({ kind: 'pageerror', name: error.name }));
  page.on('console', message => {
    if (message.type() === 'error') diagnostics.browserErrors.push({ kind: 'console-error' });
  });
  page.on('response', response => {
    const url = new URL(response.url());
    if (url.origin === new URL(base).origin && url.pathname.startsWith('/api/'))
      diagnostics.apiResponses.push({ path: url.pathname, method: response.request().method(), status: response.status() });
  });
  page.on('requestfailed', request => {
    const url = new URL(request.url());
    diagnostics.requestFailures.push({ path: url.pathname, method: request.method() });
  });
  async function login(name) {
    await page.getByPlaceholder('用户名', { exact: true }).fill(name);
    await page.getByPlaceholder('密码', { exact: true }).fill('test-password');
    const [response] = await Promise.all([
      page.waitForResponse(response => {
        const url = new URL(response.url());
        return url.origin === new URL(base).origin && url.pathname === '/api/tasks' && response.request().method() === 'GET';
      }),
      page.waitForURL(url => url.pathname === '/tasks/history'),
      page.getByRole('button', { name: /登\s*录/ }).click()
    ]);
    assert.equal(response.status(), 200);
    await page.getByText(name, { exact: true }).waitFor();
    await page.locator('.el-pagination').waitFor();
  }
  async function logout() {
    await page.locator('.topbar .user').click();
    await page.getByText('退出登录', { exact: true }).click();
    await page.waitForURL(url => url.pathname === '/login' && url.searchParams.has('redirect'));
  }
  try {
    await page.goto(base + '/tasks/history');
    await page.waitForURL(url => url.pathname === '/login' && url.searchParams.has('redirect'));
    await login('smoke_alpha');
    await page.locator('.el-table__body tbody tr').first().waitFor();
    assert.equal(await page.locator('.el-table__body tbody tr').count(), 20);
    checks.push('任务入口可访问，第一页20条');
    await page.locator('.el-pagination .btn-next').click();
    await page.waitForFunction(() => document.querySelectorAll('.el-table__body tbody tr').length === 5);
    checks.push('真实后端第二页5条');
    await page.locator('.el-table__body tbody tr').first().getByRole('button', { name: '查看', exact: true }).click();
    await page.getByText('HTTP链路测试的模拟答案', { exact: false }).first().waitFor();
    checks.push('任务历史显示已保存的Java→Python结果；连续聊天由独立聊天脚本验证');
    await page.keyboard.press('Escape');
    await page.getByRole('dialog', { name: '历史结果', exact: true }).waitFor({ state: 'hidden' });

    for (const status of [200, 401]) {
      let held;
      let signal;
      const arrived = new Promise(resolve => { signal = resolve; });
      let intercept = true;
      const handler = async route => {
        if (intercept && route.request().method() === 'GET') {
          intercept = false; held = route; signal();
        } else await route.continue();
      };
      await page.locator('.topbar .user').click();
      await page.getByText('个人中心', { exact: true }).last().click();
      await page.waitForURL(url => url.pathname === '/profile');
      await page.route(base + '/api/tasks?*', handler);
      await page.goto(base + '/tasks/history');
      await arrived;
      await logout();
      await login('smoke_beta');
      await page.getByText('暂无数据', { exact: true }).waitFor();
      const payload = status === 401
        ? { code: 401, message: '旧请求的模拟401', data: null }
        : { code: 0, message: 'ok', data: { total: 1, page: 1, size: 20, list: [{
          id: 'late-alpha', userId: 1, taskType: 'KNOWLEDGE_QA', status: 'SUCCESS',
          resultPayload: { answer: 'private-alpha-old-response' }, createdAt: '2026-10-14T00:00:00'
        }] } };
      await held.fulfill({ status, contentType: 'application/json', body: JSON.stringify(payload) });
      await page.waitForTimeout(300);
      assert.match(page.url(), /\/tasks\/history$/);
      assert.equal(await page.locator('.topbar .uname').innerText(), 'smoke_beta');
      assert.equal(await page.getByText('private-alpha-old-response', { exact: false }).count(), 0);
      assert.ok(await page.evaluate(() => localStorage.getItem('token')));
      checks.push(`账号切换后忽略旧${status}响应`);
      await page.unroute(base + '/api/tasks?*', handler);
      await logout();
      await login('smoke_alpha');
    }
    await logout();
    checks.push('页面退出调用服务端并清理登录态');
    console.log(JSON.stringify({ scope: '桌面Chromium、真实Java/Python；模型与Redis替身；迟到响应使用拦截模拟', checks }));
  } catch (error) {
    if (diagnosticsDir) {
      fs.mkdirSync(diagnosticsDir, { recursive: true });
      diagnostics.pagePath = new URL(page.url()).pathname;
      fs.writeFileSync(path.join(diagnosticsDir, 'browser.json'), JSON.stringify(diagnostics, null, 2), { flag: 'wx' });
      await page.screenshot({ path: path.join(diagnosticsDir, 'failure.png'), fullPage: true }).catch(() => {});
    }
    throw error;
  } finally {
    await context.close();
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
