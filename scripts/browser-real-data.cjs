// Own isolated browser context + real backend. Never reads the daily profile.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const [base, credentialsFile, output] = process.argv.slice(2);
(async () => {
  const credentials = JSON.parse(fs.readFileSync(credentialsFile, 'utf8'));
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const browser = await chromium.launch({ executablePath, headless: true });
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
  const page = await context.newPage();
  const checks = [];
  try {
    await page.goto(base + '/schools');
    await page.getByPlaceholder('用户名', { exact: true }).fill(credentials.username);
    await page.getByPlaceholder('密码', { exact: true }).fill(credentials.password);
    await page.getByRole('button', { name: /登\s*录/ }).click();
    await page.waitForURL(url => url.pathname === '/schools');
    await page.locator('.school-row').first().waitFor();
    assert.equal(await page.locator('.school-row').count(), 10);
    assert.ok(!(await page.locator('.schools-page').innerText()).includes('测试虚构'));
    checks.push('真实后端登录、10校与无虚构记录');
    await page.locator('.school-row').first().click();
    await page.getByText('2027', { exact: false }).first().waitFor();
    checks.push('院校详情展示2027专业');
    await page.goto(base + '/documents');
    await page.getByText('栈的后进先出与基本操作', { exact: false }).first().waitFor();
    assert.ok(!(await page.locator('main').innerText()).includes('【测试资料】'));
    checks.push('资料页显示真实来源内容');
    await page.screenshot({ path: path.join(output, 'documents-desktop.png'), fullPage: true });
    await page.goto(base + '/practice');
    await page.getByText('数据结构', { exact: false }).first().waitFor();
    checks.push('真实后端练习入口');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(base + '/schools');
    await page.locator('.school-row').first().waitFor();
    assert.equal(await page.locator('.school-row').count(), 10);
    await page.screenshot({ path: path.join(output, 'schools-mobile-width.png'), fullPage: true });
    checks.push('390宽度院校页可读取；非真实手机验收');
    fs.writeFileSync(path.join(output, 'browser.json'), JSON.stringify({ checks }, null, 2), { flag: 'wx', mode: 0o600 });
    console.log(JSON.stringify({ checks: checks.length, passed: true }));
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'browser-failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally { await context.close(); await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
