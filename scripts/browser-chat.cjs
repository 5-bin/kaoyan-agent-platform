// Real Java/Python/LangChain with a controlled provider; no browser API interception.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const base = process.argv[2];
const screenshotDir = process.argv[3];
assert.equal(new URL(base).hostname, '127.0.0.1');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH });
  const checks = [];
  try {
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      try {
        const page = await context.newPage();
        const username = 'browser_chat_' + width;
        const response = await context.request.post(base + '/api/auth/register', { data: { username, password: 'test-only-chat-password' } });
        assert.equal(response.status(), 200);
        await page.goto(base + '/tasks');
        await page.getByPlaceholder('用户名', { exact: true }).fill(username);
        await page.getByPlaceholder('密码', { exact: true }).fill('test-only-chat-password');
        await page.getByRole('button', { name: /登\s*录/ }).click();
        const input = page.getByRole('textbox', { name: '聊天输入' });
        await input.waitFor();
        const token = await page.evaluate(() => localStorage.getItem('token'));
        const headers = { Authorization: `Bearer ${token}` };
        const consent = await (await context.request.get(base + '/api/privacy/settings', { headers })).json();
        assert.equal((await context.request.put(base + '/api/privacy/settings', { headers, data: { modelAllowed: true, scopes: ['profile', 'document'], provider: consent.data.provider } })).status(), 200);
        await page.reload();
        await input.fill('进程与线程');
        await page.getByRole('button', { name: '发送', exact: true }).click();
        const answers = page.locator('.task-result .markdown').getByText('线程共享地址空间，保留各自的栈。', { exact: true });
        await answers.waitFor();
        assert.ok(new URL(page.url()).searchParams.get('conversationId'));
        const conversationUrl = page.url();
        await input.fill('它们共享哪些资源');
        await page.getByRole('button', { name: '发送', exact: true }).click();
        await answers.nth(1).waitFor();
        await page.reload();
        await answers.nth(1).waitFor();
        checks.push(width + ': continuous_followup_and_refresh');
        await input.fill('创建线程学习笔记');
        await page.getByRole('button', { name: '发送', exact: true }).click();
        await page.getByRole('button', { name: '预览笔记建议' }).click();
        await page.getByRole('dialog').getByRole('button', { name: '确认保存建议' }).click();
        await page.getByText('已保存', { exact: true }).waitFor();
        await input.fill('修改这份文档，补充线程说明');
        await page.getByRole('button', { name: '发送', exact: true }).click();
        await page.getByRole('button', { name: '预览笔记建议' }).nth(1).click();
        await page.getByRole('dialog').getByText('查看修改差异', { exact: false }).click();
        await page.getByRole('dialog').getByRole('button', { name: '确认保存建议' }).click();
        await page.getByText('已保存', { exact: true }).waitFor();
        await page.getByText('已选 v2', { exact: false }).waitFor();
        checks.push(width + ': document_create_update_and_confirm');
        await input.fill('进程与线程，等待停止');
        await page.getByRole('button', { name: '发送', exact: true }).click();
        await page.getByRole('button', { name: '停止生成' }).click();
        await page.getByText('已停止生成', { exact: true }).waitFor();
        await page.getByRole('button', { name: '重试此问题' }).click();
        await page.getByRole('button', { name: '停止生成' }).click();
        await page.getByText('已停止生成', { exact: true }).nth(1).waitFor();
        assert.equal(await page.getByText('已停止生成', { exact: true }).count(), 2);
        checks.push(width + ': cancel_and_retry');
        await page.goto(base + '/notes');
        await page.getByRole('button', { name: '新建笔记', exact: true }).click();
        await page.getByRole('textbox', { name: '笔记标题', exact: true }).fill('手动学习笔记' + width);
        await page.getByRole('textbox', { name: '笔记正文', exact: true }).fill('# 手动复习记录\n保留第一版内容');
        await page.getByRole('button', { name: '创建笔记', exact: true }).click();
        await page.getByText('编辑笔记 · v1', { exact: true }).waitFor();
        const noteUrl = page.url();
        await page.getByRole('textbox', { name: '笔记正文', exact: true }).fill('# 手动复习记录\n增加第二版内容');
        await page.getByRole('button', { name: '保存新版本', exact: true }).click();
        await page.getByText('编辑笔记 · v2', { exact: true }).waitFor();
        await page.goto(noteUrl);
        await page.getByText('编辑笔记 · v2', { exact: true }).waitFor();
        assert.equal(await page.getByRole('textbox', { name: '笔记正文', exact: true }).inputValue(), '# 手动复习记录\n增加第二版内容');
        await page.getByRole('button', { name: '历史版本', exact: true }).click();
        const history = page.getByRole('dialog', { name: '笔记历史版本', exact: true });
        await history.getByRole('button', { name: '查看此版本' }).last().click();
        const historical = page.getByRole('dialog', { name: '历史版本（只读）', exact: true });
        await historical.getByText('保留第一版内容', { exact: true }).waitFor();
        await historical.locator('.el-dialog__headerbtn').click();
        await history.locator('.el-dialog__headerbtn').click();
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        if (screenshotDir) { fs.mkdirSync(screenshotDir, { recursive: true }); await page.screenshot({ path: path.join(screenshotDir, `notes-${width}.png`), fullPage: true }); }
        checks.push(width + ': personal_notes_create_update_history_and_reload');
        await page.goto(conversationUrl);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        if (width === 390) {
          await page.getByRole('button', { name: '会话', exact: true }).click();
          await page.getByRole('dialog', { name: '会话' }).waitFor();
          await page.getByRole('dialog', { name: '会话' }).getByRole('link', { name: '任务历史' }).click();
        } else await page.getByRole('link', { name: '任务历史' }).click();
        await page.getByRole('heading', { name: '任务历史', exact: true }).waitFor();
        checks.push(width + ': layout_and_readonly_history');
      } finally { await context.close(); }
    }
    console.log(JSON.stringify({ scope: 'real Java/Python/LangChain; H2, Redis and provider doubles; desktop and simulated390', checks }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
