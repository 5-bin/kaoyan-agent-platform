// Actual Java/Python endpoints against an isolated synthetic fixture; no route interception.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.argv[2];
const screenshotDir = process.argv[3];
assert.equal(new URL(base).hostname, '127.0.0.1');
const questionId = 9011, documentId = 9122;

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH });
  const checks = [];
  try {
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      let stage = 'register';
      let page;
      try {
        page = await context.newPage();
        page.setDefaultTimeout(25000);
        const username = `learning_${width}_${Date.now().toString(36)}`;
        const password = 'test-only-learning-password';
        const registered = await context.request.post(base + '/api/auth/register', { data: { username, password } });
        assert.equal(registered.status(), 200, 'synthetic registration HTTP status');
        assert.equal((await registered.json()).code, 0, 'synthetic registration result');
        await page.goto(base + '/wrong');
        await page.getByPlaceholder('用户名', { exact: true }).fill(username);
        await page.getByPlaceholder('密码', { exact: true }).fill(password);
        await page.getByRole('button', { name: /登\s*录/ }).click();
        await page.waitForURL(url => url.pathname === '/wrong');
        await page.getByText(username, { exact: true }).first().waitFor();
        // Token remains inside this isolated context and is never printed or captured.
        const api = async (method, endpoint, data) => {
          const token = await page.evaluate(() => localStorage.getItem('token'));
          assert.ok(token, 'synthetic user must be authenticated');
          const response = await context.request.fetch(base + '/api' + endpoint, {
            method, headers: { Authorization: `Bearer ${token}` }, ...(data === undefined ? {} : { data })
          });
          assert.equal(response.status(), 200, `${method} ${endpoint.split('?')[0]} status`);
          const envelope = await response.json();
          assert.equal(envelope.code, 0, `${method} ${endpoint.split('?')[0]} result`);
          return envelope.data;
        };
        const sessions = () => api('GET', '/practice/sessions/page?pageNum=1&pageSize=50');
        const openAssistant = async () => {
          const launch = page.getByRole('button', { name: '考研助手', exact: true });
          if (await launch.isVisible()) await launch.click();
          await page.getByRole('textbox', { name: '聊天输入' }).waitFor();
          assert.equal(await page.locator('.assistant').count(), 1, 'one chat instance');
        };
        const closeAssistant = async () => {
          const close = page.locator('.assistant .chat-heading').getByRole('button', { name: '关闭', exact: true });
          if (await close.isVisible()) await close.click();
        };
        const send = async query => {
          await page.getByRole('textbox', { name: '聊天输入' }).fill(query);
          await page.getByRole('button', { name: '发送', exact: true }).click();
        };
        const defaults = await api('GET', '/privacy/settings');
        assert.equal(defaults.modelAllowed, false);
        assert.deepEqual(defaults.scopes, []);
        assert.equal(defaults.retentionDays, 30);
        checks.push(`${width}: privacy_defaults_off`);

        stage = 'create_wrong_attempt';
        const initial = await api('POST', '/practice/sessions', { source: 'NORMAL', subject: '操作系统', questionIds: [questionId], count: 1 });
        const graded = await api('POST', `/practice/sessions/${initial.sessionId}/answer`, { questionId, answer: 'A' });
        assert.equal(graded.isCorrect, 0);
        assert.equal(graded.answer, 'B');
        assert.equal((await sessions()).total, 1);
        await page.reload();
        await page.locator('.item-head .el-checkbox').first().click();
        await openAssistant();
        await page.getByText('外部模型未授权 · 使用本地规则', { exact: true }).waitFor();
        if (width === 390) assert.equal(Math.round((await page.locator('.assistant').boundingBox()).width), 390);
        else assert.equal(Math.round((await page.locator('.assistant').boundingBox()).width), 440);

        stage = 'direct_favorite';
        await send('帮我收藏这道题');
        const favoriteCard = page.locator('.action-card').filter({ hasText: '收藏题目' }).first();
        await favoriteCard.getByText('执行成功', { exact: false }).waitFor();
        assert.equal(await favoriteCard.getByRole('button', { name: '确认操作' }).count(), 0);
        const favoriteRows = await api('GET', '/marks/favorite?pageNum=1&pageSize=20');
        assert.ok(favoriteRows.list.some(item => item.questionId === questionId));
        checks.push(`${width}: local_single_favorite_persisted`);

        stage = 'confirmed_practice';
        await send('从我的错题安排5道练习');
        const practiceCard = page.locator('.action-card').filter({ hasText: '创建练习' }).last();
        await practiceCard.getByRole('button', { name: '确认操作', exact: true }).waitFor();
        stage = 'practice_preview_count';
        assert.equal((await sessions()).total, 1, 'preview must not create a session');
        await practiceCard.getByRole('button', { name: '确认操作', exact: true }).click();
        stage = 'practice_execute_result';
        await practiceCard.getByText('执行成功', { exact: false }).waitFor();
        await practiceCard.getByRole('link', { name: '打开练习（1题）', exact: true }).waitFor();
        const afterConfirmation = await sessions();
        assert.equal(afterConfirmation.total, 2);
        const created = afterConfirmation.list.filter(item => item.sessionId !== initial.sessionId);
        assert.equal(created.length, 1);
        assert.equal(created[0].total, 1, 'show actual count when fewer than five published questions exist');
        if (screenshotDir) {
          fs.mkdirSync(screenshotDir, { recursive: true });
          await page.screenshot({ path: path.join(screenshotDir, `learning-actions-${width}.png`), fullPage: true });
        }
        await page.reload();
        stage = 'practice_reload';
        await openAssistant();
        await page.locator('.action-card').filter({ hasText: '创建练习' }).last().getByText('执行成功', { exact: false }).waitFor();
        assert.equal((await sessions()).total, 2, 'refresh must not create a duplicate session');
        checks.push(`${width}: pending_then_confirm_one_session_refresh_idempotent`);

        stage = 'statistics_and_published_document';
        await closeAssistant();
        await page.getByRole('menuitem', { name: '学习统计', exact: true }).click();
        await page.waitForFunction(() => document.querySelector('.stats .num')?.textContent.trim() === '1');
        const stats = await api('GET', '/stats/learning');
        assert.equal(stats.questionCount, 1);
        assert.equal(stats.correctCount, 0);
        assert.equal(stats.uniqueQuestions, 1);
        assert.equal(stats.accuracy, 0);
        await openAssistant();
        await send('分析我的学习统计');
        const statsTurn = page.locator('.turn').filter({ has: page.locator('.user-message', { hasText: '分析我的学习统计' }) });
        await statsTurn.locator('.task-result .markdown').getByText('记录事实：', { exact: false }).waitFor();
        assert.ok((await statsTurn.locator('.task-result .markdown').innerText()).includes('有效作答1次'));
        assert.ok((await statsTurn.locator('.task-result .markdown').innerText()).includes('样本不足5次'));
        await closeAssistant();
        checks.push(`${width}: assistant_uses_actual_statistics_and_marks_small_sample`);
        await page.goto(base + `/documents?documentId=${documentId}`);
        const documents = await api('GET', '/documents');
        const published = documents.find(item => item.id === documentId);
        assert.ok(published && published.content, 'published fixture document exists');
        const documentDialog = page.getByRole('dialog', { name: published.title, exact: true });
        await documentDialog.waitFor();
        assert.ok((await documentDialog.locator('.markdown').innerText()).length > 0);
        assert.ok((await documentDialog.locator('.markdown').innerText()).includes(published.content.replace(/^#+\s*/gm, '').trim().split('\n').at(-1)));
        await documentDialog.locator('.el-dialog__headerbtn').click();
        checks.push(`${width}: real_statistics_and_document_body`);

        stage = 'privacy_grant_revoke';
        await openAssistant();
        await page.locator('.action-card').filter({ hasText: '创建练习' }).last().getByText('执行成功', { exact: false }).waitFor();
        await send('分析当前资料');
        const documentTurn = page.locator('.turn').filter({ has: page.locator('.user-message', { hasText: '分析当前资料' }) });
        await documentTurn.locator('.task-result .markdown').getByText('合成学习资料正文', { exact: false }).waitFor();
        assert.ok((await documentTurn.locator('.task-result .markdown').innerText()).includes('同一进程的线程共享地址空间'));
        checks.push(`${width}: assistant_reads_selected_published_document_body`);
        await page.getByRole('button', { name: '隐私', exact: true }).click();
        const privacyDialog = page.getByRole('dialog', { name: '考研助手隐私设置', exact: true });
        await privacyDialog.waitFor();
        assert.equal(await privacyDialog.getByRole('switch').isChecked(), false);
        await privacyDialog.locator('.el-switch').click();
        await privacyDialog.locator('.el-checkbox').filter({ hasText: '学习统计' }).click();
        await privacyDialog.getByRole('button', { name: '保存隐私设置', exact: true }).click();
        await privacyDialog.waitFor({ state: 'hidden' });
        const granted = await api('GET', '/privacy/settings');
        assert.equal(granted.modelAllowed, true);
        assert.deepEqual(granted.scopes, ['stats']);
        await page.getByRole('button', { name: '隐私', exact: true }).click();
        await privacyDialog.waitFor();
        await privacyDialog.locator('.el-switch').click();
        await privacyDialog.getByRole('button', { name: '保存隐私设置', exact: true }).click();
        await privacyDialog.waitFor({ state: 'hidden' });
        const revoked = await api('GET', '/privacy/settings');
        assert.equal(revoked.modelAllowed, false);
        assert.deepEqual(revoked.scopes, []);
        assert.ok(revoked.version > granted.version);
        checks.push(`${width}: privacy_ui_grant_stats_and_revoke`);

        stage = 'clear_current_conversation';
        await page.getByRole('button', { name: '隐私', exact: true }).click();
        await privacyDialog.getByRole('button', { name: '清除当前会话', exact: true }).click();
        const deleteDialog = page.getByRole('dialog', { name: '删除对话', exact: true });
        await deleteDialog.getByRole('button', { name: '删除', exact: true }).click();
        await deleteDialog.waitFor({ state: 'hidden' });
        await privacyDialog.waitFor({ state: 'hidden' });
        assert.equal((await api('GET', '/conversations?pageNum=1&pageSize=20')).total, 0);
        assert.equal((await sessions()).total, 2);
        assert.ok((await api('GET', '/marks/favorite?pageNum=1&pageSize=20')).list.some(item => item.questionId === questionId));
        assert.equal((await api('GET', '/stats/learning')).questionCount, 1);
        assert.equal(await page.locator('.assistant-message').count(), 0);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        if (screenshotDir) {
          fs.mkdirSync(screenshotDir, { recursive: true });
          await page.screenshot({ path: path.join(screenshotDir, `learning-${width}-${Date.now()}.png`), fullPage: true });
        }
        checks.push(`${width}: clear_chat_preserves_attempts_favorites_and_sessions`);
      } catch (error) {
        if (screenshotDir && page) {
          fs.mkdirSync(screenshotDir, { recursive: true });
          await page.screenshot({ path: path.join(screenshotDir, `failure-${width}-${stage}.png`), fullPage: true }).catch(() => {});
          // Synthetic fixtures only. Never record request headers or browser storage.
          const cards = await page.locator('.action-card').allTextContents().catch(() => []);
          fs.writeFileSync(path.join(screenshotDir, `failure-${width}-${stage}.json`), JSON.stringify({ stage, errorType: error.name, cards }, null, 2));
        }
        throw new Error(`learning browser check failed at ${width}:${stage}`);
      } finally {
        if (screenshotDir) fs.writeFileSync(path.join(screenshotDir, `cleanup-${width}.json`), JSON.stringify({ stage, phase: 'closing_context' }));
        await context.close();
        if (screenshotDir) fs.writeFileSync(path.join(screenshotDir, `cleanup-${width}.json`), JSON.stringify({ stage, phase: 'context_closed' }));
      }
    }
    console.log(JSON.stringify({ checks }));
  } finally {
    if (screenshotDir) fs.writeFileSync(path.join(screenshotDir, 'browser-cleanup.json'), JSON.stringify({ phase: 'closing_browser' }));
    await browser.close();
    if (screenshotDir) fs.writeFileSync(path.join(screenshotDir, 'browser-cleanup.json'), JSON.stringify({ phase: 'browser_closed' }));
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
