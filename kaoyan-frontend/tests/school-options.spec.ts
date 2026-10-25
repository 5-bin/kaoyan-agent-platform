import { expect, test } from '@playwright/test'

const user = { id: 1, username: 'school-test', role: 'STUDENT', status: 1 }
const options = { provinces: ['北京', '江苏'], majorNames: ['计算机技术', '计算机科学与技术', '软件工程'] }
const schools = [
  { id: 1, name: '测试甲校', province: '北京', level: '985' },
  { id: 2, name: '测试乙校', province: '江苏', level: '211' }
]

test.beforeEach(async ({ page }) => {
  await page.addInitScript(u => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('userInfo', JSON.stringify(u))
  }, user)
})

test('select, filter options, combine conditions and clear without shrinking options', async ({ page }) => {
  const queries: URLSearchParams[] = []
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const url = new URL(route.request().url())
    let data: unknown = []
    if (url.pathname === '/api/schools/options') data = options
    else if (url.pathname === '/api/schools') {
      queries.push(url.searchParams)
      data = url.searchParams.get('province') === '江苏' ? [schools[1]] : schools
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/schools')
  await expect(page.locator('.school-row')).toHaveCount(2)
  const province = page.getByRole('combobox', { name: '省份', exact: true })
  const major = page.getByRole('combobox', { name: '专业名', exact: true })
  await province.fill('江')
  await expect(page.getByRole('option', { name: '北京', exact: true })).not.toBeVisible()
  await page.getByRole('option', { name: '江苏', exact: true }).click()
  await major.fill('软件')
  await page.getByRole('option', { name: '软件工程', exact: true }).click()
  const level = page.locator('.search-bar .el-select').nth(1)
  await level.click()
  await page.getByRole('option', { name: '211', exact: true }).click()
  expect(queries).toHaveLength(1)
  await page.getByRole('button', { name: '搜索院校库', exact: true }).click()
  await expect(page.locator('.school-row')).toHaveCount(1)
  expect(Object.fromEntries(queries.at(-1)!)).toEqual({ province: '江苏', level: '211', majorName: '软件工程' })
  await province.click()
  await expect(page.getByRole('option', { name: '北京', exact: true })).toBeVisible()
  await province.press('Escape')
  // Clearing all three filters restores an unrestricted query.
  for (const select of [page.locator('.search-bar .el-select').first(), level, page.locator('.search-bar .el-select').nth(2)]) {
    await select.hover()
    await select.locator('.el-select__clear').click({ force: true })
  }
  await page.getByRole('button', { name: '搜索院校库', exact: true }).click()
  await expect(page.locator('.school-row')).toHaveCount(2)
  for (const key of ['province', 'level', 'majorName']) expect(queries.at(-1)!.get(key) || '').toBe('')
  await major.fill('不存在的专业')
  await expect(page.getByText('无匹配数据', { exact: true })).toBeVisible()
  await expect(page.getByRole('option', { name: '不存在的专业', exact: true })).toHaveCount(0)
  await major.press('Escape')
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath('school-options.png'), fullPage: true })
})

test('option loading failure can be retried independently of school results', async ({ page }) => {
  let attempts = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/schools/options' && ++attempts === 1) {
      await route.fulfill({ status: 503, json: { code: 503, message: '测试选项加载失败' } })
      return
    }
    const data = path === '/api/schools/options' ? options : path === '/api/schools' ? schools : []
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/schools')
  await expect(page.getByText('筛选选项加载失败', { exact: false })).toBeVisible()
  await expect(page.locator('.school-row')).toHaveCount(2)
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.getByText('筛选选项加载失败', { exact: false })).toHaveCount(0)
  await page.getByRole('combobox', { name: '省份', exact: true }).click()
  await expect(page.getByRole('option', { name: '江苏', exact: true })).toBeVisible()
  expect(attempts).toBe(2)
})

test('empty catalog has explicit empty options', async ({ page }) => {
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const data = new URL(route.request().url()).pathname === '/api/schools/options'
      ? { provinces: [], majorNames: [] } : []
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/schools')
  for (const name of ['省份', '专业名']) {
    const select = page.getByRole('combobox', { name, exact: true })
    await select.click()
    await expect(page.locator('.el-select-dropdown:visible').getByText('暂无选项', { exact: true })).toBeVisible()
    await select.press('Escape')
  }
  await expect(page.getByText('没有匹配的院校', { exact: true })).toBeVisible()
})

test('options show loading until the request completes', async ({ page }) => {
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/schools/options') await gate
    await route.fulfill({ json: { code: 0, message: 'ok', data: path === '/api/schools/options' ? options : [] } })
  })
  try {
    await page.goto('/schools')
    await page.getByRole('combobox', { name: '省份', exact: true }).click()
    await expect(page.locator('.el-select-dropdown:visible').getByText('加载中', { exact: true })).toBeVisible()
  } finally { release() }
  await expect(page.getByRole('option', { name: '北京', exact: true })).toBeVisible()
})
