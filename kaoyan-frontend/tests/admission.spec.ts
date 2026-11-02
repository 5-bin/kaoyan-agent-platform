import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

const sources = JSON.parse(readFileSync(new URL('../../config/admission-sources.json', import.meta.url), 'utf-8')) as {
  code: string; name: string; year: number; entries: string[]
}[]

const nau = sources.find(source => source.code === 'nau')!
const links = { schoolCode: nau.code, schoolName: nau.name, registeredYear: nau.year, entryUrls: nau.entries }
const legacyCheck = {
  query: { schoolCode: 'nau', year: 2027, majorCode: '081200' },
  baselineReleaseId: 'rag-v1-0000000000000000', checkedAt: '2026-10-29T01:00:00Z', status: 'DIFFERENCES',
  entryUrls: ['https://evil.invalid/old-admission'], limitations: ['OLD_LIMITATION'],
  evidence: [{ id: 'A1', title: 'OLD_EVIDENCE', url: 'https://evil.invalid/old-admission', locator: 'OLD_LOCATOR', excerpt: 'OLD_EXCERPT', publishedAt: null,
    retrievedAt: '2026-10-29T01:00:00Z', contentHash: 'a'.repeat(64), permissionNote: 'OLD_PERMISSION', reviewStatus: 'UNREVIEWED' }],
  comparisons: [{ field: 'examSubjects', oldValue: 'OLD_OLD', newValue: 'OLD_NEW', status: 'CHANGED', baselineId: 'OLD_BASELINE', evidenceId: 'A1' }],
}

async function show(page: import('@playwright/test').Page, result: unknown) {
  const user = { id: 1, username: 'admission-fixture', role: 'STUDENT', status: 1 }
  const conversation = { id: 'admission-conversation', title: '招生链接', conditions: {} }
  await page.addInitScript(u => {
    localStorage.setItem('token', 'test-only-token')
    localStorage.setItem('userInfo', JSON.stringify(u))
  }, user)
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/privacy/settings')) data = { modelAllowed: false, scopes: [], version: 1 }
    else if (path.endsWith('/learning/status')) data = { enabled: false }
    else if (path === '/api/conversations') data = { list: [conversation], total: 1 }
    else if (path.endsWith('/messages')) {
      data = { conversation, list: [{ id: 'm1', sequenceNo: 1, content: '查官网南京审计大学',
        attempts: [{ taskId: 't1', status: 'SUCCESS', version: 1, result }] }], total: 1 }
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/tasks')
}

for (const code of ['pku', 'cumtb', 'zju']) {
  test(`expanded registry displays ${code} links after history reload`, async ({ page }) => {
    const source = sources.find(source => source.code === code)!
    await show(page, {
      outcome: 'COMPLETED', answer: '已展示登记招生官网链接。', references: [], resolvedTaskType: 'CHAT',
      explanationMode: 'rules', releaseId: 'rag-v1-0000000000000000', conditions: {},
      admissionLinks: { schoolCode: code, schoolName: source.name, registeredYear: source.year, entryUrls: source.entries },
    })
    const region = page.getByRole('region', { name: '招生官网链接' })
    await expect(region).toContainText(source.name)
    await expect(region.getByRole('link')).toHaveCount(source.entries.length)
    await expect(region.getByRole('link').first()).toHaveAttribute('href', source.entries[0])
    await expect(region).toContainText('如进入学校主页，请从研究生招生栏目继续查阅。')
    await page.reload()
    await expect(region).toContainText(source.name)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

for (const state of ['new', 'legacy', 'unknown']) {
  test(`admission ${state} shows only trusted registered links`, async ({ page }) => {
    const result = state === 'new'
      ? { outcome: 'COMPLETED', answer: 'OLD_ANSWER', references: [], resolvedTaskType: 'CHAT',
          explanationMode: 'rules', releaseId: nau.entries[0], conditions: {}, admissionLinks: links }
      : state === 'legacy'
        ? { outcome: 'UNSUPPORTED', answer: 'OLD_ADMISSION_ANSWER', notice: 'OLD_NOTICE', followUp: ['OLD_FOLLOWUP'], references: [], resolvedTaskType: 'CHAT',
            explanationMode: 'rules', releaseId: 'rag-v1-0000000000000000', conditions: {}, admissionCheck: legacyCheck }
        : { outcome: 'UNSUPPORTED', answer: 'OLD_UNKNOWN_ANSWER', notice: 'OLD_NOTICE', followUp: ['OLD_FOLLOWUP'], references: [], resolvedTaskType: 'CHAT',
            explanationMode: 'rules', releaseId: 'rag-v1-0000000000000000', conditions: {},
            admissionCheck: { ...legacyCheck, query: { schoolCode: 'unknown' } } }
    await show(page, result)
    const region = page.getByRole('region', { name: '招生官网链接' })
    if (state === 'unknown') {
      await expect(region).toHaveCount(0)
      await expect(page.getByText('该院校未在登记清单中，无法展示招生官网链接')).toBeVisible()
    } else {
      await expect(region).toBeVisible()
      await expect(region).toContainText(nau.name)
      await expect(region).toContainText('登记年份')
      await expect(region).toContainText(String(nau.year))
      await expect(region).toContainText('登记年份不代表当前内容年份或最新招生年度')
      await expect(region).toContainText('请自行确认招生年份、专业及报考条件')
      const anchors = region.getByRole('link')
      await expect(anchors).toHaveCount(nau.entries.length)
      for (let index = 0; index < nau.entries.length; index++) {
        const anchor = anchors.nth(index)
        await expect(anchor).toHaveAttribute('href', nau.entries[index])
        await expect(anchor).toHaveText(nau.entries[index])
        await expect(anchor).toHaveAttribute('target', '_blank')
        await expect(anchor).toHaveAttribute('rel', 'noopener noreferrer')
      }
    }
    for (const old of ['OLD_ANSWER', 'OLD_ADMISSION_ANSWER', 'OLD_UNKNOWN_ANSWER', 'OLD_NOTICE', 'OLD_FOLLOWUP', 'OLD_LIMITATION',
      'OLD_EVIDENCE', 'OLD_LOCATOR', 'OLD_EXCERPT', 'OLD_BASELINE', '未经平台发布审核', '官网观察', '本次证据', '比对平台版本']) {
      await expect(page.getByText(old, { exact: false })).toHaveCount(0)
    }
    await page.reload()
    if (state === 'unknown') await expect(page.getByText('该院校未在登记清单中，无法展示招生官网链接')).toBeVisible()
    else {
      await expect(page.getByRole('region', { name: '招生官网链接' })).toContainText('登记年份')
      await expect(page.getByRole('region', { name: '招生官网链接' }).getByRole('link')).toHaveCount(nau.entries.length)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

test('new forged entries are hidden instead of rendered as links', async ({ page }) => {
  await show(page, {
    outcome: 'COMPLETED', answer: '已展示登记招生官网链接。', references: [], resolvedTaskType: 'CHAT', explanationMode: 'rules',
    releaseId: 'rag-v1-0000000000000000', conditions: {},
    admissionLinks: { ...links, entryUrls: ['https://evil.invalid/forged'] },
  })
  await expect(page.getByText('招生官网链接未通过登记校验，已隐藏。')).toBeVisible()
  await expect(page.getByRole('region', { name: '招生官网链接' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'https://evil.invalid/forged' })).toHaveCount(0)
})

test('catalog information precedes confirmation links and survives reload', async ({ page }) => {
  await show(page, {
    outcome: 'COMPLETED', answer: '已找到库内专业信息，以下展示已有资料。', references: [], resolvedTaskType: 'CHAT',
    explanationMode: 'rules', releaseId: 'school-catalog-v1', conditions: {}, admissionLinks: links,
    schoolCatalog: {
      school: { id: 11, name: nau.name, province: '江苏', level: '普通本科' }, targetYear: 2027,
      availableYears: [2027, 2026], total: 1, warnings: [], details: [{
        id: 1, schoolId: 11, majorName: '计算机科学与技术', majorCode: '081200', year: 2027, remark: '采集待核实',
        admissionMetrics: { college: '计算机学院', track: '系统方向', studyMode: 'full_time', admissionCategory: 'ordinary',
          enrollment: { year: 2027, value: 77, status: 'OFFICIAL', basis: 'TOTAL_INCLUDING_RECOMMENDED', scopeLabel: '专业合计，各方向共用', sources: [] },
          cutoffReference: { year: 2026, value: 310, status: 'UNVERIFIED', basis: 'NOT_APPLICABLE', scopeLabel: '普通全日制', sources: [] } }
      }]
    }
  })
  for (const reload of [false, true]) {
    if (reload) await page.reload()
    await expect(page.getByText('已找到库内专业信息，以下展示已有资料。')).toBeVisible()
    const catalog = page.getByRole('region', { name: '库内院校信息' })
    await expect(catalog).toContainText('2027年 招生计划：77人')
    await expect(catalog).toContainText('2026年 复试参考线：310分')
    await expect(catalog).toContainText('第三方·待核实')
    await expect(catalog).toContainText('采集待核实')
    await expect(catalog.getByRole('link', { name: '查看完整院校详情' })).toHaveAttribute('href', '/schools/11')
    expect(await page.evaluate(() => Boolean(document.querySelector('.school-catalog')!
      .compareDocumentPosition(document.querySelector('.admission-links')!) & Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true)
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: test.info().outputPath('catalog-before-links.png'), fullPage: true })
})

test('registered links do not hide a missing catalog record', async ({ page }) => {
  await show(page, {
    outcome: 'UNSUPPORTED', answer: '院校库尚未收录该院校的信息。', references: [], resolvedTaskType: 'CHAT',
    explanationMode: 'rules', releaseId: 'school-catalog-v1', admissionLinks: links,
    schoolCatalog: { school: null, targetYear: null, availableYears: [], details: [], total: 0, warnings: [] }
  })
  await expect(page.getByText('院校库尚未收录该院校的信息。')).toBeVisible()
  await expect(page.getByRole('region', { name: '库内院校信息' })).toHaveCount(0)
  await expect(page.getByRole('region', { name: '招生官网链接' })).toBeVisible()
})

test('registered scope URLs are clickable while arbitrary Markdown URLs stay blocked', async ({ page }) => {
  await show(page, {
    outcome: 'COMPLETED', answer: `登记院校来源：\n[${nau.name}](${nau.entries[0]})\n[不可信网址](https://evil.invalid/forged)`,
    references: [], resolvedTaskType: 'CHAT', explanationMode: 'rules', releaseId: 'rag-v1-0000000000000000',
  })
  await expect(page.getByRole('link', { name: nau.name, exact: true })).toHaveAttribute('href', nau.entries[0])
  await expect(page.getByRole('link', { name: '不可信网址' })).toHaveCount(0)
})

test('legacy compound results retain candidates while hiding the old verification answer', async ({ page }) => {
  await show(page, {
    outcome: 'COMPLETED', answer: 'OLD_ADMISSION_ANSWER', admissionCheck: legacyCheck,
    references: [], resolvedTaskType: 'SCHOOL_RECOMMEND', explanationMode: 'rules', releaseId: 'rag-v1-0000000000000000',
    candidates: [{ programId: 'fixture', school: nau.name, major: '计算机科学与技术', college: '计算机学院',
      year: 2027, degreeType: 'academic', region: '江苏', examSubjects: ['101', '201', '301', '408'],
      matchedConditions: [], pendingChecks: [], explanation: '保留原规则候选说明' }],
  })
  await expect(page.getByText('保留原规则候选说明')).toBeVisible()
  await expect(page.getByRole('region', { name: '招生官网链接' })).toBeVisible()
  await expect(page.getByText('OLD_ADMISSION_ANSWER')).toHaveCount(0)
})

test('malformed new link results cannot crash history rendering', async ({ page }) => {
  await show(page, {
    outcome: 'COMPLETED', answer: '原正文', references: [], resolvedTaskType: 'CHAT', explanationMode: 'rules',
    releaseId: 'rag-v1-0000000000000000', admissionLinks: { ...links, entryUrls: null },
  })
  await expect(page.getByText('招生官网链接未通过登记校验，已隐藏。')).toBeVisible()
  await expect(page.getByRole('region', { name: '招生官网链接' })).toHaveCount(0)
})
