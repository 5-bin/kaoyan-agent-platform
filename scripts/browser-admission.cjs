// Actual Vue -> Java/H2 -> FastAPI -> local stdio MCP link lookup; no remote pages.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const base = process.argv[2];
const screenshots = process.argv[3];
const sources = require('../config/admission-sources.json');
const school = sources.find(item => item.code === (process.argv[4] || 'nau'));
assert.ok(school, 'a registered admission school is required');
assert.equal(new URL(base).hostname, '127.0.0.1');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH });
  const checks = [];
  fs.mkdirSync(screenshots, { recursive: true });
  try {
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      try {
        const page = await context.newPage();
        const username = `admission_browser_${width}`;
        assert.equal((await context.request.post(base + '/api/auth/register', { data: { username, password: 'test-only-admission-password' } })).status(), 200);
        await page.goto(base + '/tasks');
        await page.getByPlaceholder('用户名', { exact: true }).fill(username);
        await page.getByPlaceholder('密码', { exact: true }).fill('test-only-admission-password');
        await page.getByRole('button', { name: /登\s*录/ }).click();
        const input = page.getByRole('textbox', { name: '聊天输入' });
        await input.fill(`查询${school.name}招生官网链接`);
        await page.getByRole('button', { name: '发送', exact: true }).click();
        const region = page.getByRole('region', { name: '招生官网链接' });
        await region.waitFor();
        const text = await region.textContent();
        assert.ok(text.includes(school.name));
        assert.match(text, /登记年份/);
        assert.ok(text.includes(String(school.year)));
        assert.match(text, /请自行确认招生年份、专业及报考条件/);
        assert.doesNotMatch(text, /未经平台发布审核|官网观察|本次证据|比对平台版本|内容哈希/);
        const links = region.getByRole('link');
        assert.equal(await links.count(), school.entries.length);
        for (let index = 0; index < school.entries.length; index++) {
          const link = links.nth(index);
          assert.equal(await link.getAttribute('href'), school.entries[index]);
          assert.equal(await link.textContent(), school.entries[index]);
          assert.equal(await link.getAttribute('target'), '_blank');
          assert.equal(await link.getAttribute('rel'), 'noopener noreferrer');
        }
        checks.push(`${width}: actual_local_mcp_registered_links`);
        await page.reload();
        await region.waitFor();
        assert.match(await region.textContent(), /登记年份/);
        assert.equal(await region.getByRole('link').count(), school.entries.length);
        checks.push(`${width}: saved_links_restored_after_reload`);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        checks.push(`${width}: no_horizontal_overflow`);
        const token = await page.evaluate(() => localStorage.getItem('token'));
        const headers = { Authorization: `Bearer ${token}` };
        const conversation = new URL(page.url()).searchParams.get('conversationId');
        const history = await (await context.request.get(`${base}/api/conversations/${conversation}/messages`, { headers })).json();
        const task = history.data.list[0].attempts[0].taskId;
        const other = await browser.newContext();
        try {
          await other.request.post(base + '/api/auth/register', { data: { username: username + '_other', password: 'test-only-admission-password' } });
          const login = await (await other.request.post(base + '/api/auth/login', { data: { username: username + '_other', password: 'test-only-admission-password' } })).json();
          const auth = { Authorization: `Bearer ${login.data.accessToken}` };
          assert.equal((await other.request.get(`${base}/api/tasks/${task}`, { headers: auth })).status(), 404);
          assert.equal((await other.request.get(`${base}/api/conversations/${conversation}/messages`, { headers: auth })).status(), 404);
          checks.push(`${width}: cross_account_task_and_chat_404`);
        } finally { await other.close(); }
        await page.screenshot({ path: path.join(screenshots, `admission-${width}.png`), fullPage: true });
      } finally { await context.close(); }
    }
    console.log(JSON.stringify({ checks, screenshots }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
