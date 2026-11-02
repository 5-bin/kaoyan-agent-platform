import { test, expect, type Page } from '@playwright/test'
import example from '../src/assets/question-import-example.json' with { type: 'json' }

async function login(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'import-test-token')
    localStorage.setItem('userInfo', JSON.stringify({ id: 1, username: 'import-test', role: 'ADMIN', status: 1 }))
  })
}
const rows = example.questions.map((q, index) => ({ ...q, id: 300 + index, version: 1, active: 1, reviewStatus: 'PENDING_REVIEW' }))
async function open(page: Page) {
  await page.goto('/admin/questions')
  await page.getByRole('button', { name: '批量导入', exact: true }).click()
}
const emptyPage = { total: 0, page: 1, size: 10, list: [] }

test('download, upload, preview and explicitly import examples into the pending queue', async ({ page }, info) => {
  await login(page)
  let writes = 0, previews = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown = writes ? { ...emptyPage, total: 8, list: rows } : emptyPage
    if (path.endsWith('/import/preview')) {
      previews++; expect(route.request().postDataJSON()).toEqual(example)
      data = { count: 8, questions: example.questions }
    } else if (path.endsWith('/import')) {
      writes++; expect(previews).toBe(1); expect(route.request().postDataJSON()).toEqual(example)
      await new Promise(resolve => setTimeout(resolve, 150))
      data = { count: 8, questions: rows }
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await open(page)
  const downloadEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: '下载自编题 JSON 示例' }).click()
  expect((await downloadEvent).suggestedFilename()).toBe('question-import-example.json')
  await page.getByLabel('选择 JSON 文件（最大 2 MiB）').setInputFiles({ name: 'examples.json', mimeType: 'application/json', buffer: Buffer.from('\uFEFF' + JSON.stringify(example)) })
  await expect(page.getByLabel('题目 JSON（也可直接粘贴）')).toHaveValue(JSON.stringify(example))
  await expect(page.getByRole('button', { name: '确认整批送审' })).toBeDisabled()
  await page.getByRole('button', { name: '校验并预览' }).click()
  await expect(page.getByText('预览 8 道题 · 尚未写入题库')).toBeVisible()
  expect(writes).toBe(0)
  await page.locator('details').first().locator('summary').click()
  await expect(page.locator('details').first()).toContainText('标准答案：C')
  await expect(page.locator('details').first()).toContainText('最后一次出栈返回8')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('question-import-preview.png'), fullPage: true })
  await page.getByRole('button', { name: '确认整批送审' }).click()
  await expect(page.getByRole('button', { name: '关闭批量导入' })).toBeDisabled()
  await expect(page.getByRole('status').filter({ hasText: '已导入 8 道题' })).toBeVisible()
  await expect(page.getByRole('button', { name: '确认整批送审' })).toBeDisabled()
  await page.getByRole('button', { name: '关闭批量导入' }).click()
  await expect(page.locator('.queue')).toContainText(example.questions[0].content)
  expect(writes).toBe(1)
})

test('invalid JSON, invalid count and a bad row preserve input without importing', async ({ page }) => {
  await login(page)
  let previews = 0, writes = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/import')) writes++
    if (path.endsWith('/import/preview')) {
      previews++
      return route.fulfill({ status: 400, json: { code: 400, message: '第2题：真题必须填写年份和原题号', data: null } })
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data: emptyPage } })
  })
  await open(page)
  const input = page.getByLabel('题目 JSON（也可直接粘贴）')
  await input.fill('{broken')
  await page.getByRole('button', { name: '校验并预览' }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'JSON 格式不正确' })).toBeVisible()
  await input.fill('{"questions":[]}')
  await page.getByRole('button', { name: '校验并预览' }).click()
  await expect(page.getByRole('alert').filter({ hasText: '每批1至50道题' })).toBeVisible()
  expect(previews).toBe(0)
  const invalid = JSON.stringify({ questions: [example.questions[0], { ...example.questions[1], sourceType: 'REAL_EXAM' }] })
  await input.fill(invalid)
  await page.getByRole('button', { name: '校验并预览' }).click()
  await expect(page.getByRole('region', { name: '批量导入题目' }).getByRole('alert')).toContainText('第2题')
  await expect(input).toHaveValue(invalid)
  await expect(page.getByRole('button', { name: '确认整批送审' })).toBeDisabled()
  expect(writes).toBe(0)
})

test('changing JSON invalidates the preview and preview content renders as text', async ({ page }) => {
  await login(page)
  let previews = 0, writes = 0
  const source = '<img src=x onerror=alert(1)>'
  const data = { questions: [{ ...example.questions[0], sourceLocator: source }] }
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/import')) writes++
    if (path.endsWith('/import/preview')) previews++
    await route.fulfill({ json: { code: 0, message: 'ok', data: path.endsWith('/preview') ? { count: 1, questions: data.questions } : emptyPage } })
  })
  await open(page)
  const input = page.getByLabel('题目 JSON（也可直接粘贴）')
  await input.fill(JSON.stringify(data))
  await page.getByRole('button', { name: '校验并预览' }).click()
  await page.locator('details summary').click()
  await expect(page.locator('details')).toContainText(source)
  await expect(page.locator('.batch-import img')).toHaveCount(0)
  await input.fill(JSON.stringify(example))
  await expect(page.locator('[aria-label="导入预览"]')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '确认整批送审' })).toBeDisabled()
  expect(previews).toBe(1); expect(writes).toBe(0)
})

test('an import conflict preserves the file and requires another preview before retry', async ({ page }) => {
  await login(page)
  let writes = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/import')) {
      writes++
      return route.fulfill({ status: 409, json: { code: 409, message: '第1题已存在，题目ID为300', data: null } })
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data: path.endsWith('/preview') ? { count: 8, questions: example.questions } : emptyPage } })
  })
  await open(page)
  const text = JSON.stringify(example)
  await page.getByLabel('题目 JSON（也可直接粘贴）').fill(text)
  await page.getByRole('button', { name: '校验并预览' }).click()
  await page.getByRole('button', { name: '确认整批送审' }).click()
  await expect(page.getByRole('alert').filter({ hasText: '导入未确认' })).toContainText('第1题已存在')
  await expect(page.getByLabel('题目 JSON（也可直接粘贴）')).toHaveValue(text)
  await expect(page.getByRole('button', { name: '确认整批送审' })).toBeDisabled()
  expect(writes).toBe(1)
})
