import { test, expect, type Page } from '@playwright/test'

async function login(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'practice-fixture')
    localStorage.setItem('userInfo', JSON.stringify({ id: 1, username: 'practice-test', role: 'STUDENT', status: 1 }))
  })
}
test('server result drives feedback and failed submission reveals nothing', async ({ page }) => {
  await login(page)
  let calls = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown
    if (path.endsWith('/answer')) {
      calls++
      if (calls === 1) return route.fulfill({ status: 400, json: { code: 400, message: '选项校验失败', data: null } })
      expect(route.request().postDataJSON()).toEqual({ questionId: 1, answer: 'A' })
      data = { questionId: 1, userAnswer: 'A', isCorrect: 1, answer: 'A', analysis: '服务器保存的解析' }
    } else if (path.endsWith('/questions/1')) {
      data = { id: 1, content: '服务端判分测试题', optionA: '选项甲', optionB: '选项乙' }
    } else data = [{ questionId: 1, orderIndex: 0, isCorrect: null }]
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/practice/session/test-session')
  await page.getByText('选项甲', { exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.getByText('选项校验失败', { exact: true })).toBeVisible()
  await expect(page.locator('.feedback')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '提交答案', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.locator('.feedback')).toContainText('回答正确')
  await expect(page.locator('.feedback')).toContainText('服务器保存的解析')
  expect(calls).toBe(2)
})

test('review distinguishes unanswered and missing history, without marking either choice wrong', async ({ page }, testInfo) => {
  await login(page)
  const records = [{ questionId: 1, orderIndex: 0, isCorrect: null }, { questionId: 2, orderIndex: 1, isCorrect: 0 }]
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    const data = path.endsWith('/review') ? { total: 2, list: [
      { ...records[0], content: '尚未提交的题', optionA: '未答选项', snapshotStatus: 'NOT_ANSWERED' },
      { ...records[1], userAnswer: 'A', snapshotStatus: 'MISSING' }
    ] } : path.endsWith('/questions/1') ? { id: 1, content: '尚未提交的题', optionA: '未答选项' } : records
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/practice/session/partial')
  await expect(page.getByText('尚未提交的题', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '查看已保存作答' }).click()
  const cards = page.locator('.q-card')
  await expect(cards.first()).toContainText('未作答')
  await expect(cards.first()).not.toContainText('答错')
  await expect(cards.nth(1)).toContainText('历史题目快照缺失')
  await expect(page.locator('.opt-mark')).toHaveCount(0)
  await expect(page.locator('.opt-wrong')).toHaveCount(0)
  await expect(page.locator('.sum-item').filter({ hasText: '答错' }).locator('.sum-num')).toHaveText('1')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('review.png'), fullPage: true })
})

test('saved history and overall counts do not change with loaded review pages', async ({ page }) => {
  await login(page)
  const records = Array.from({ length: 12 }, (_, i) => ({ questionId: i + 1, orderIndex: i, isCorrect: i < 11 ? 1 : 0 }))
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const url = new URL(route.request().url())
    if (url.pathname.includes('/questions/')) throw new Error('Historical review must not fetch current questions')
    const first = url.searchParams.get('pageNum') === '1'
    const data = url.pathname.endsWith('/review') ? { total: 12, list: records.slice(first ? 0 : 10, first ? 10 : 12).map(r => ({
      ...r, content: '历史版本题干 ' + r.questionId, optionA: '历史选项A', optionB: '历史选项B',
      userAnswer: 'A', answer: r.isCorrect ? 'A' : 'B', analysis: '历史解析', snapshotStatus: 'AVAILABLE'
    })) } : records
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/practice/session/completed')
  const correct = page.locator('.sum-item').filter({ hasText: '答对' }).locator('.sum-num')
  await expect(correct).toHaveText('11')
  await expect(page.locator('.q-card')).toHaveCount(10)
  await page.getByRole('button', { name: '加载更多' }).click()
  await expect(page.locator('.q-card')).toHaveCount(12)
  await expect(correct).toHaveText('11')
  await expect(page.locator('.q-no').last()).toHaveText('12')
  await expect(page.locator('.q-card').last()).toContainText('历史解析')
})

test('favorites and manual wrong marks do not display unavailable answers', async ({ page }) => {
  await login(page)
  await page.route('http://127.0.0.1:4173/api/**', route => route.fulfill({ json: { code: 0, message: 'ok', data: { total: 3, list: [
    { questionId: 1, content: '未作答标记题', snapshotStatus: 'NOT_ANSWERED' },
    { questionId: 2, snapshotStatus: 'MISSING' },
    { questionId: 3, content: '保存的旧题', answer: 'B', analysis: '保存的旧解析', snapshotStatus: 'PARTIAL' }
  ] } } }))
  for (const path of ['/favorite', '/wrong']) {
    await page.goto(path)
    const items = page.locator('.card.item')
    await expect(items).toHaveCount(3)
    await expect(items.nth(0)).toContainText('尚无有效作答')
    await expect(items.nth(0)).not.toContainText('正确答案')
    await expect(items.nth(1)).toContainText('历史题目快照缺失')
    await expect(items.nth(1)).not.toContainText('正确答案')
    await expect(items.nth(2)).toContainText('保存的旧解析')
    await expect(items.nth(2)).toContainText('历史快照不完整')
  }
})
