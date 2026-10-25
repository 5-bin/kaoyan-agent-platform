// Isolated actual Java -> FastAPI -> embedded Qdrant. Explicit vectors, not model-quality evidence.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.argv[2], output = process.argv[3];
assert.equal(new URL(base).hostname, '127.0.0.1');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH });
  const checks = [];
  try {
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      const page = await context.newPage(); page.setDefaultTimeout(20000);
      try {
        const credentials = { username: `semantic_${width}_${Date.now().toString(36)}`, password: 'test-only-semantic-password' };
        assert.equal((await context.request.post(base+'/api/auth/register', { data: credentials })).status(), 200);
        await page.goto(base+'/tasks');
        await page.getByPlaceholder('用户名', { exact: true }).fill(credentials.username);
        await page.getByPlaceholder('密码', { exact: true }).fill(credentials.password);
        await page.getByRole('button', { name: /登\s*录/ }).click();
        await page.waitForURL(url => url.pathname === '/tasks');
        await page.getByRole('textbox', { name: '聊天输入' }).waitFor();
        const api = async (method, endpoint, data) => {
          const token = await page.evaluate(() => localStorage.getItem('token'));
          const response = await context.request.fetch(base+'/api'+endpoint, { method, headers: { Authorization: `Bearer ${token}` }, ...(data === undefined ? {} : { data }) });
          assert.equal(response.status(), 200, endpoint);
          const body = await response.json(); assert.equal(body.code, 0, endpoint); return body.data;
        };
        const send = async query => {
          await page.getByRole('textbox', { name: '聊天输入' }).fill(query);
          await page.getByRole('button', { name: '发送', exact: true }).click();
          const turn = page.locator('.turn').filter({ has: page.locator('.user-message', { hasText: query }) }).last();
          await turn.locator('.task-result').waitFor();
          for (let retry = 0; retry < 5 && (await turn.locator('.assistant-message').last().innerText()).includes('索引正在准备'); retry++) {
            assert.equal(await turn.locator('.action-card').count(), 0);
            const previousAttempts = await turn.locator('.assistant-message').count();
            await turn.getByRole('button', { name: '重试此问题' }).last().click();
            await turn.locator('.assistant-message').nth(previousAttempts).locator('.task-result').waitFor();
          }
          return turn;
        };
        for (const id of [9021, 9022, 9023]) await api('POST', `/marks/wrong/${id}`);
        const defaults = await api('GET', '/privacy/settings'); assert.equal(defaults.modelAllowed, false);
        let turn = await send('将我的错题本中涉及二叉树的题目加入收藏');
        let card = turn.locator('.action-card').last();
        await card.getByRole('button', { name: '确认操作' }).waitFor();
        assert.ok((await card.innerText()).includes('涉及 2 题'));
        assert.ok((await card.innerText()).includes('知识点匹配'));
        assert.ok((await card.innerText()).includes('语义相关'));
        assert.equal((await api('GET', '/marks/favorite?pageNum=1&pageSize=20')).total, 0);
        assert.equal((await turn.innerText()).includes('不得用于检索的解析'), false);
        if (output) { fs.mkdirSync(output, { recursive: true }); await card.scrollIntoViewIfNeeded(); await page.screenshot({ path: path.join(output, `questions-preview-${width}.png`), fullPage: true }); }
        checks.push(`${width}: authorized_wrong_union_labels_and_semantics_preview_hides_answers`);
        await card.getByRole('button', { name: '确认操作' }).click();
        await card.getByText('执行成功', { exact: false }).waitFor();
        const favorites = await api('GET', '/marks/favorite?pageNum=1&pageSize=20');
        assert.deepEqual(favorites.list.map(q => q.questionId).sort(), [9021, 9022]);
        await page.reload();
        await page.locator('.action-card').last().getByText('执行成功', { exact: false }).waitFor();
        assert.equal((await api('GET', '/marks/favorite?pageNum=1&pageSize=20')).total, 2);
        checks.push(`${width}: confirmation_persists_and_refresh_does_not_repeat`);
        turn = await send('在我的收藏夹中查找涉及二叉树的题目');
        assert.ok((await turn.innerText()).includes('语义相关'));
        assert.equal(await turn.locator('.action-card').count(), 0);
        turn = await send('从全题库创建5道关于二叉树的题目练习');
        card = turn.locator('.action-card').last();
        await card.getByRole('button', { name: '确认操作' }).waitFor();
        assert.ok((await card.innerText()).includes('当前可用 2 题'));
        assert.equal((await api('GET', '/practice/sessions/page?pageNum=1&pageSize=20')).total, 0);
        await card.getByRole('button', { name: '确认操作' }).click();
        await card.getByRole('link', { name: '打开练习（2题）', exact: true }).waitFor();
        assert.equal((await api('GET', '/practice/sessions/page?pageNum=1&pageSize=20')).total, 1);
        checks.push(`${width}: published_semantic_practice_uses_actual_count_and_confirmation`);
        turn = await send('在全题库搜索涉及完全不存在的专业主题的题目');
        assert.ok((await turn.innerText()).includes('没有找到符合该主题的题目'));
        assert.equal(await turn.locator('.action-card').count(), 0);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        if (output) { fs.mkdirSync(output, { recursive: true }); await page.screenshot({ path: path.join(output, `questions-${width}.png`), fullPage: true }); }
        checks.push(`${width}: zero_matches_and_no_horizontal_overflow`);
      } catch (error) {
        if (output) { fs.mkdirSync(output, { recursive: true }); await page.screenshot({ path: path.join(output, `questions-failure-${width}.png`), fullPage: true }).catch(() => {}); }
        throw error;
      } finally { await context.close(); }
    }
    console.log(JSON.stringify({ checks }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
