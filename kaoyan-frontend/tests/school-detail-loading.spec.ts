import { expect, test } from '@playwright/test'

const user = { id: 1, username: 'school-fixture', role: 'STUDENT', status: 1 }
const response = (name = '四川大学') => ({ code: 0, message: 'ok', data: {
  school: { id: 11, name, province: '四川', level: '985' }, details: []
} })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(u => {
    localStorage.setItem('token', 'test-only-token')
    localStorage.setItem('userInfo', JSON.stringify(u))
  }, user)
  await page.route('**/api/**', route => route.fulfill({ json: { code: 0, message: 'ok', data: {} } }))
})

test('school 11 loads and an empty program list is distinct from failure', async ({ page }) => {
  await page.route('**/api/schools/11', async route => {
    await new Promise(resolve => setTimeout(resolve, 250))
    await route.fulfill({ json: response() })
  })
  await page.goto('/schools/11')
  await expect(page.getByRole('status', { name: '正在加载院校信息' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '四川大学', exact: true })).toBeVisible()
  await expect(page.getByText('该院校暂无已收录的招生专业信息')).toBeVisible()
  await expect(page.locator('.el-loading-mask')).toHaveCount(0)
})

test('failed request releases loading and retry loads real content', async ({ page }) => {
  let attempts = 0
  await page.route('**/api/schools/11', route => ++attempts === 1
    ? route.fulfill({ status: 500, json: { code: 500, message: '合成服务失败' } })
    : route.fulfill({ json: response() }))
  await page.goto('/schools/11')
  await expect(page.getByText('院校信息加载失败', { exact: true })).toBeVisible()
  await expect(page.locator('.el-loading-mask')).toHaveCount(0)
  await page.getByRole('button', { name: '重试加载' }).click()
  await expect(page.getByRole('heading', { name: '四川大学', exact: true })).toBeVisible()
  expect(attempts).toBe(2)
})

test('404 has a useful return action without empty school placeholders', async ({ page }) => {
  await page.route('**/api/schools/11', route => route.fulfill({ status: 404, json: { code: 404, message: '院校不存在' } }))
  await page.goto('/schools/11')
  await expect(page.locator('.el-result__title')).toHaveText('院校不存在')
  await expect(page.getByRole('button', { name: '返回院校库', exact: true })).toBeVisible()
  await expect(page.getByText('层次未登记')).toHaveCount(0)
  await expect(page.locator('.el-loading-mask')).toHaveCount(0)
})

test('route changes cancel old loads and reject their late data', async ({ page }) => {
  let completeOld: (() => void) | undefined
  const oldDone = new Promise<void>(resolve => { completeOld = resolve })
  await page.route('**/api/schools/11', async route => {
    await oldDone
    await route.fulfill({ json: response('旧院校迟到结果') }).catch(() => {})
  })
  await page.route('**/api/schools/12', route => route.fulfill({ json: response('新院校') }))
  await page.goto('/schools/11')
  await expect(page.getByRole('status', { name: '正在加载院校信息' })).toBeVisible()
  await page.evaluate(() => {
    window.history.pushState({}, '', '/schools/12')
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
  await expect(page.getByRole('heading', { name: '新院校', exact: true })).toBeVisible()
  completeOld?.()
  await expect(page.getByText('旧院校迟到结果')).toHaveCount(0)
})

test('stalled detail request times out after 15 seconds and can retry', async ({ page }) => {
  let attempts = 0
  await page.route('**/api/schools/11', route => {
    if (++attempts > 1) return route.fulfill({ json: response() })
    // Leave the first network request pending so the actual Axios/XHR timeout fires.
  })
  await page.goto('/schools/11')
  await expect(page.locator('.el-result__title')).toHaveText('院校信息加载超时，请稍后重试', { timeout: 18000 })
  await expect(page.locator('.el-loading-mask')).toHaveCount(0)
  await page.getByRole('button', { name: '重试加载' }).click()
  await expect(page.getByRole('heading', { name: '四川大学', exact: true })).toBeVisible()
})
