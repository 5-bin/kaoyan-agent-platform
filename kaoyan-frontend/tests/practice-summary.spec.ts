import { test, expect } from '@playwright/test'

test('missing historical snapshots show the server error and release the summary button', async ({ page }) => {
  let summaryRequests = 0
  const message = '该批次包含缺少题目版本快照的历史作答，暂不支持生成总结'
  await page.addInitScript(() => {
    localStorage.setItem('token', 'summary-test-token')
    localStorage.setItem('userInfo', JSON.stringify({ id: 1, username: 'summary-test', role: 'STUDENT', status: 1 }))
  })
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/ai-summary')) {
      summaryRequests++
      await route.fulfill({ status: 409, json: { code: 409, message, data: null } })
      return
    }
    const data = path.endsWith('/questions/1')
      ? { id: 1, content: '测试题干', optionA: '测试选项A', optionB: '测试选项B', answer: 'A' }
      : path.endsWith('/answer') ? null : [{ questionId: 1, orderIndex: 0, isCorrect: null }]
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/practice/session/legacy-session')
  await page.getByText('测试选项A', { exact: true }).click()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await page.getByRole('button', { name: '完成，查看结果', exact: true }).click()
  const summary = page.getByRole('button', { name: '生成 AI 总结', exact: true })
  await summary.click()
  await expect(page.getByText(message, { exact: true })).toBeVisible()
  await expect(summary).toBeEnabled()
  await expect(summary).not.toHaveClass(/is-loading/)
  expect(summaryRequests).toBe(1)
})
