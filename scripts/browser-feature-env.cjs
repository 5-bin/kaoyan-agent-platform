// Real isolated Java/MySQL services; no API interception and no daily browser profile.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const { chromium } = createRequire(path.join(root, 'kaoyan-frontend/package.json'))('playwright');
const base = 'http://127.0.0.1:15173';
const privateRoot = path.join(root, '.cache/feature-env-2027');
const creds = JSON.parse(fs.readFileSync(path.join(privateRoot, 'credentials.json'), 'utf8'));
const questions = JSON.parse(fs.readFileSync(path.join(root, 'scripts/fixtures/feature-2027-questions.json'), 'utf8'));
const out = path.join(privateRoot, 'browser-' + new Date().toISOString().replace(/[:.]/g, '-'));
process.umask(0o077); fs.mkdirSync(out, { recursive: true });
(async () => {
  const checks = [], errors = [];
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH });
  async function login(context, who, route) {
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.name + ': ' + error.message.slice(0, 180)));
    await page.goto(base + route);
    await page.getByPlaceholder('用户名', { exact: true }).fill(creds[who].username);
    await page.getByPlaceholder('密码', { exact: true }).fill(creds[who].password);
    await page.getByRole('button', { name: /登\s*录/ }).click();
    await page.waitForURL(url => !url.pathname.includes('login'));
    return page;
  }
  async function capture(page, name) {
    await page.screenshot({ path: path.join(out, name + '.png'), fullPage: true });
  }
  try {
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      try {
        const page = await login(context, 'demo', '/schools');
        await page.locator('.school-row').nth(9).waitFor();
        assert.equal(await page.locator('.school-row').count(), 10);
        await page.getByPlaceholder('省份', { exact: true }).fill('浙江');
        await page.getByRole('button', { name: '搜索院校库' }).click();
        await page.getByText('浙江科技大学', { exact: true }).waitFor();
        await page.waitForFunction(() => document.querySelectorAll('.school-row').length === 1);
        await capture(page, width + '-schools');
        await page.locator('.school-row').first().click();
        await page.getByRole('heading', { name: '浙江科技大学' }).waitFor();
        await page.getByText('085404', { exact: true }).waitFor();
        const major = page.getByText('计算机技术', { exact: true });
        await major.waitFor();
        const box = await major.boundingBox();
        assert.ok(box && box.width >= 80 && box.height < 80, 'School major must remain readable at this width');
        assert.ok(await page.getByText('未收录', { exact: true }).count() >= 2);
        await page.getByText(/2027官方来源核验摘要/).waitFor();
        await capture(page, width + '-school-detail');
        checks.push(width + ': 10 schools, real filtering, sourced detail and null indicators');
        for (const [route, heading, loaded] of [
          ['/practice', '开始刷题', '查看详情'],
          ['/wrong', '错题本', '移出错题'],
          ['/favorite', '我的收藏', '取消收藏'],
          ['/stat', '学习统计', '有效作答次数']
        ]) {
          await page.goto(base + route);
          await page.getByRole('heading', { name: heading, exact: true }).waitFor();
          if (route === '/practice') {
            await page.getByRole('button', { name: loaded }).first().waitFor();
            assert.equal(await page.getByRole('button', { name: loaded }).count(), 8);
          } else if (route === '/favorite') {
            await page.getByRole('button', { name: loaded }).nth(5).waitFor();
            assert.equal(await page.getByRole('button', { name: loaded }).count(), 6);
          } else if (route === '/wrong') {
            await page.getByRole('button', { name: loaded }).first().waitFor();
            await page.getByText('正确答案：', { exact: true }).first().waitFor();
          } else {
            await page.waitForFunction(() => Array.from(document.querySelectorAll('.stat .num')).map(x => x.textContent.trim()).join(',') === '30,20,67%');
          }
          await capture(page, width + route.replaceAll('/', '-'));
        }
        checks.push(width + ': eight practice sessions, wrong answers, six favorites and 30/20/67% statistics');
        await page.goto(base + '/practice');
        await page.getByRole('button', { name: '查看详情' }).first().click();
        await page.waitForFunction(() => document.querySelector('.card.summary') || Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('查看已保存作答') && !b.disabled));
        if (!await page.locator('.card.summary').count()) await page.getByRole('button', { name: '查看已保存作答' }).click();
        await page.locator('.saved-answer').first().waitFor();
        await capture(page, width + '-history');
        await page.reload();
        await page.waitForFunction(() => document.querySelector('.card.summary') || document.querySelector('.q-title'));
        checks.push(width + ': saved answer review and refresh');
        await page.goto(base + '/admin/questions');
        await page.waitForURL(url => url.pathname === '/');
        checks.push(width + ': student admin navigation denied');
      } finally { await context.close(); }
      const adminContext = await browser.newContext({ viewport: { width, height: 900 } });
      try {
        const page = await login(adminContext, 'admin', '/admin/questions');
        await page.getByRole('heading', { name: '题目录入与审核' }).waitFor();
        await page.getByRole('heading', { name: '待审核题目（4）' }).waitFor();
        await page.getByRole('button', { name: '查看并审核' }).first().click();
        await page.getByRole('region', { name: '题目详情' }).waitFor();
        await page.getByText('标准答案：', { exact: true }).waitFor();
        await capture(page, width + '-admin-review');
        checks.push(width + ': pending queue, full question, source and review actions');
        await page.goto(base + '/practice');
        await page.getByRole('button', { name: '开始刷题', exact: true }).click();
        await page.locator('.q-title').waitFor();
        const stem = await page.locator('.q-title').textContent();
        const q = questions.find(q => q.content === stem.trim()); assert.ok(q);
        assert.equal(await page.locator('.feedback').count(), 0);
        assert.equal(await page.getByText('正确答案：', { exact: false }).count(), 0);
        const options = page.locator('.q-card .opt');
        await options.nth('ABCD'.indexOf(q.answer)).click();
        await page.getByRole('button', { name: '提交答案', exact: true }).click();
        await page.getByText('回答正确', { exact: false }).waitFor();
        await capture(page, width + '-submitted-answer');
        checks.push(width + ': real new session, hidden answer, UI selection, Java grading and saved feedback (admin verification account)');
      } finally { await adminContext.close(); }
    }
    const empty = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    try {
      const page = await login(empty, 'empty', '/favorite');
      await page.getByText('还没有收藏题目', { exact: true }).waitFor();
      await page.goto(base + '/wrong');
      await page.getByText('暂时没有错题', { exact: true }).waitFor();
      await capture(page, 'empty-student');
      checks.push('empty student has separate empty lists');
    } finally { await empty.close(); }
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify({ passed: checks.length, checks, pageErrors: errors,
      apiInterception: false, providerCalls: 0, realMySQL: true, simulatedWidths: [1280, 390], realMobileDevice: false,
      note: 'Browser grading adds one answer per width to the administrator verification account; demo student remains 30/20/2.' }, null, 2));
    console.log(JSON.stringify({ passed: checks.length, report: path.join(out, 'report.json') }));
  } catch (error) {
    fs.writeFileSync(path.join(out, 'failure.json'), JSON.stringify({ name: error.name, message: error.message, checks, pageErrors: errors }, null, 2));
    console.error(error.name + ': ' + error.message.slice(0, 250));
    console.error('Diagnostics: ' + out); process.exitCode = 1;
  } finally { await browser.close(); }
})();
