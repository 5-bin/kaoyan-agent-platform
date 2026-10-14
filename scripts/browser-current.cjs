// 实际后端页面操作；账号切换后的迟到响应由拦截模拟。
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const base = process.argv[2];

(async () => {
  const executablePath = process.env.CHROME_PATH || process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
  const browser = await chromium.launch({ executablePath, headless: true });
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
  const page = await context.newPage();
  const checks = [];
  async function login(name) {
    await page.getByPlaceholder('用户名', { exact: true }).fill(name);
    await page.getByPlaceholder('密码', { exact: true }).fill('test-password');
    await page.getByRole('button', { name: /登\s*录/ }).click();
    await page.waitForURL('**/tasks');
    await page.locator('.el-pagination').waitFor();
  }
  async function logout() {
    await page.locator('.topbar .user').click();
    await page.getByText('退出登录', { exact: true }).click();
    await page.waitForURL('**/login?redirect=**');
  }
  try {
    await page.goto(base + '/tasks');
    await page.waitForURL('**/login?redirect=**');
    await login('smoke_alpha');
    await page.locator('.el-table__body tbody tr').first().waitFor();
    assert.equal(await page.locator('.el-table__body tbody tr').count(), 20);
    checks.push('任务入口可访问，第一页20条');
    await page.locator('.el-pagination .btn-next').click();
    await page.waitForFunction(() => document.querySelectorAll('.el-table__body tbody tr').length === 5);
    checks.push('真实后端第二页5条');
    await page.getByRole('button', { name: '提交任务', exact: true }).click();
    await page.getByPlaceholder('描述你的问题').fill('页面HTTP联调测试');
    await page.getByRole('button', { name: '提交', exact: true }).click();
    await page.getByRole('dialog').waitFor({ state: 'hidden' });
    await page.getByRole('button', { name: '查看结果与来源' }).first().click();
    await page.getByText('HTTP链路测试的模拟答案', { exact: false }).first().waitFor();
    await page.getByRole('dialog').locator('button.el-dialog__headerbtn').click();
    await page.getByRole('dialog').waitFor({ state: 'hidden' });
    checks.push('页面创建任务并显示Java→Python结果');

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
      await page.waitForURL('**/profile');
      await page.route('**/api/tasks?*', handler);
      await page.getByRole('menuitem', { name: 'Agent 任务' }).click();
      await arrived;
      await logout();
      await login('smoke_beta');
      await page.getByText('还没有任务', { exact: true }).waitFor();
      const payload = status === 401
        ? { code: 401, message: '旧请求的模拟401', data: null }
        : { code: 0, message: 'ok', data: { total: 1, page: 1, size: 20, list: [{
          id: 'late-alpha', userId: 1, taskType: 'KNOWLEDGE_QA', status: 'SUCCESS',
          resultPayload: { answer: 'private-alpha-old-response' }, createdAt: '2026-10-14T00:00:00'
        }] } };
      await held.fulfill({ status, contentType: 'application/json', body: JSON.stringify(payload) });
      await page.waitForTimeout(300);
      assert.match(page.url(), /\/tasks$/);
      assert.equal(await page.locator('.topbar .uname').innerText(), 'smoke_beta');
      assert.equal(await page.getByText('private-alpha-old-response', { exact: false }).count(), 0);
      assert.ok(await page.evaluate(() => localStorage.getItem('token')));
      checks.push(`账号切换后忽略旧${status}响应`);
      await page.unroute('**/api/tasks?*', handler);
      await logout();
      await login('smoke_alpha');
    }
    await logout();
    checks.push('页面退出调用服务端并清理登录态');
    console.log(JSON.stringify({ scope: '桌面Chromium、真实Java/Python；模型与Redis替身；迟到响应使用拦截模拟', checks }));
  } finally {
    await context.close();
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
