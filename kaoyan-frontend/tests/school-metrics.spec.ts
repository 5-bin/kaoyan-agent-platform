import { expect, test } from '@playwright/test'

const user = { id: 1, username: 'metrics-test', role: 'STUDENT', status: 1 }
const source = { title: '招生计划原文', url: 'https://example.edu.cn/plan', locator: '计算机学院专业合计，含推免', retrievedAt: '2026-10-30', sourceType: 'OFFICIAL' }
const enrollment = { year: 2027, value: 77, status: 'OFFICIAL', scopeKey: 'same-plan', scopeLabel: '专业合计，各方向共用，勿累加', basis: 'TOTAL_INCLUDING_RECOMMENDED', notice: '暂定计划', sources: [source] }
const cutoffReference = { year: 2026, value: 310, status: 'UNVERIFIED', scopeKey: 'history', scopeLabel: '普通全日制', basis: 'NOT_APPLICABLE', notice: '第三方数据待核实', sources: [{ ...source, sourceType: 'THIRD_PARTY', title: '历史线登记', url: 'https://example.org/cutoff' }] }

test.beforeEach(async ({ page }) => {
  await page.addInitScript(u => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('userInfo', JSON.stringify(u))
  }, user)
})

test('shows historical years, shared totals, provenance and all gap states without inventing values', async ({ page }) => {
  const base = { id: 10, schoolId: 1, majorName: '计算机科学与技术', majorCode: '081200', year: 2027, enrollmentCount: null, scoreLine: null, remark: '原始登记备注' }
  const context = { college: '计算机学院', track: '01计算机系统', studyMode: 'full_time', admissionCategory: 'ordinary', enrollment, cutoffReference }
  const details = [
    { ...base, admissionMetrics: context },
    ...['NOT_PUBLISHED', 'NOT_FOUND', 'SCOPE_MISMATCH', 'CONFLICT'].map((status, index) => ({
      ...base, id: 11 + index, admissionMetrics: { ...context, enrollment: { ...enrollment, value: null, status }, cutoffReference: { ...cutoffReference, value: null, status } }
    })),
    { ...base, id: 20, admissionMetrics: { ...context, track: '02人工智能', cutoffReference: { ...cutoffReference, sources: [{ ...source, title: '不安全链接', url: 'javascript:alert(1)' }] } } }
  ]
  await page.route('**/api/**', route => route.fulfill({ json: { code: 0, message: 'ok', data: { school: { id: 1, name: '测试院校', province: '河北', level: '普通本科' }, details } } }))
  await page.goto('/schools/1')
  await expect(page.getByRole('heading', { name: '测试院校', exact: true })).toBeVisible()
  await expect(page.getByText('2027年 招生计划：77人', { exact: true })).toHaveCount(2)
  await expect(page.getByText('2026年 复试参考线：310分', { exact: true })).toHaveCount(2)
  await expect(page.getByText('招生总计划（含推免）', { exact: true })).toHaveCount(6)
  await expect(page.getByText('第三方·待核实', { exact: true })).toHaveCount(2)
  for (const label of ['未公布', '未找到可靠来源', '范围不匹配', '来源冲突']) {
    await expect(page.getByText(`2027年 招生计划：${label}`, { exact: true })).toHaveCount(1)
  }
  await page.locator('.metric-sources summary').first().click()
  await expect(page.getByRole('link', { name: '招生计划原文', exact: true }).first()).toHaveAttribute('rel', 'noopener noreferrer')
  await expect(page.locator('a[href^="javascript:"]')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath('school-metrics.png'), fullPage: true })
})

test('older school details retain legacy values and do not label old values as historical references', async ({ page }) => {
  await page.route('**/api/**', route => route.fulfill({ json: { code: 0, message: 'ok', data: {
    school: { id: 1, name: '旧版院校', province: '江苏', level: '211' },
    details: [{ id: 1, schoolId: 1, majorName: '计算机技术', year: 2025, enrollmentCount: 40, scoreLine: 300 }]
  } } }))
  await page.goto('/schools/1')
  await expect(page.getByText('2025年原登记：40人', { exact: true })).toHaveCount(1)
  await expect(page.getByText('2025年原登记：300分', { exact: true })).toHaveCount(1)
  await expect(page.locator('.school-metric .metric-value')).toHaveCount(0)
})
