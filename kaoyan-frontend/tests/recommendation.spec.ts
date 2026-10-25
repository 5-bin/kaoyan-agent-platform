import { test, expect } from '@playwright/test'

const user = { id: 1, username: 'browser-test', role: 'STUDENT', status: 1, examYear: 2027, targetMajor: '081200' }
const schoolOptions = { provinces: ['北京', '江苏'], majorNames: ['计算机科学与技术', '计算机技术'] }
function task(outcome = 'COMPLETED') {
  return { id: 'browser-task', taskType: 'SCHOOL_RECOMMEND', userId: 1, status: 'SUCCESS', createdAt: '2026-10-14T12:00:00',
    releaseId: 'rag-v1-1234567890abcdef', resultPayload: { outcome, answer: outcome === 'COMPLETED' ? '满足条件的候选清单' : '当前资料没有符合条件的候选',
      explanationMode: 'rules', releaseId: 'rag-v1-1234567890abcdef', references: outcome === 'COMPLETED' ? [{ id: 'nau', title: '官方目录',
        url: 'https://gs.nau.edu.cn/2026/0920/c4397a161925/page.htm', locator: '计算机学院', version: 'admissions-2027-v1', retrievedAt: '2026-10-14', excerpt: '目录摘要' }] : [],
      candidates: outcome === 'COMPLETED' ? [{ programId: 'nau-2027-081200', school: '南京审计大学', college: '计算机学院', year: 2027,
        major: '计算机科学与技术', majorCode: '081200', degreeType: 'academic', region: '江苏', studyMode: 'full_time', examSubjects: ['101','201','301','408'],
        matchedConditions: ['年份一致'], pendingChecks: ['资格需确认'], sourceIds: ['nau'], explanation: '<img src=x onerror=alert(1)>' }] : [] } }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(u => { localStorage.setItem('token', 'test-token'); localStorage.setItem('userInfo', JSON.stringify(u)) }, user)
})

test('recommendation, safe rendering, sources and saved history', async ({ page }) => {
  let saved: ReturnType<typeof task>[] = []
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const url = new URL(route.request().url())
    let data: unknown = []
    if (url.pathname.endsWith('/schools/options')) data = schoolOptions
    else if (url.pathname.endsWith('/users/me')) data = user
    else if (url.pathname.endsWith('/recommends/generate')) {
      const body = route.request().postDataJSON()
      expect(body.preferences.degreeType).toBe('academic')
      expect(body.profile).toBeUndefined()
      saved = [task()]; data = saved[0]
    } else if (url.pathname.endsWith('/recommends')) data = saved
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/schools')
  await page.getByRole('button', { name: '条件推荐', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: '生成推荐', exact: true }).click()
  await expect(dialog.getByRole('heading', { name: '1. 南京审计大学 · 计算机科学与技术' })).toBeVisible()
  await expect(dialog.getByRole('link', { name: '官方目录' })).toHaveAttribute('href', /^https:\/\/gs.nau.edu.cn/)
  await expect(dialog.locator('.candidate img')).toHaveCount(0)
  await expect(dialog.getByText('<img src=x onerror=alert(1)>', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '关闭', exact: true }).last().click()
  await page.reload()
  await page.getByRole('button', { name: '查看', exact: true }).click()
  await expect(page.getByRole('dialog').getByText('满足条件的候选清单')).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  expect(overflow).toBe(false)
  await page.screenshot({ path: test.info().outputPath('recommendation.png'), fullPage: true, animations: 'disabled' })
})

test('no candidates remains an explicit outcome', async ({ page }) => {
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    const data = path.endsWith('/schools/options') ? schoolOptions : path.endsWith('/users/me') ? user : path.endsWith('/recommends/generate') ? task('UNSUPPORTED') : []
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/schools')
  await page.getByRole('button', { name: '条件推荐', exact: true }).click()
  await page.getByRole('button', { name: '生成推荐', exact: true }).click()
  await expect(page.getByRole('dialog').getByText('资料未覆盖', { exact: true })).toBeVisible()
  await expect(page.locator('.candidate')).toHaveCount(0)
})

test('late unauthorized response cannot log out a newer account', async ({ page }) => {
  let started = false
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/recommends/generate')) {
      started = true
      await gate
      await route.fulfill({ status: 401, json: { code: 401, message: 'old account expired' } })
    } else await route.fulfill({ json: { code: 0, message: 'ok', data: path.endsWith('/schools/options') ? schoolOptions : path.endsWith('/users/me') ? user : [] } })
  })
  await page.goto('/schools')
  await page.getByRole('button', { name: '条件推荐', exact: true }).click()
  await page.getByRole('button', { name: '生成推荐', exact: true }).click()
  await expect.poll(() => started).toBe(true)
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).last().click()
  await page.evaluate(() => {
    const app = (document.querySelector('#app') as any).__vue_app__
    const store = app.config.globalProperties.$pinia._s.get('user')
    store.token = 'new-account-token'
    store.setUserInfo({ id: 2, username: 'new-account', role: 'STUDENT', status: 1 })
    localStorage.setItem('token', 'new-account-token')
  })
  const response = page.waitForResponse(r => r.url().endsWith('/recommends/generate') && r.status() === 401)
  release()
  await response
  await expect(page.locator('.uname')).toHaveText('new-account')
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBe('new-account-token')
  await expect(page.locator('.candidate')).toHaveCount(0)
})
