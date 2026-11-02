import { test, expect } from '@playwright/test'

const item = (id: number) => ({ itemId: id, questionId: id, orderIndex: id - 1, subject: '数据结构', knowledgePoint: '树', difficulty: 'EASY',
  content: `诊断题${id}`, optionA: '选择甲', optionB: '选择乙', optionC: '选择丙', optionD: '选择丁', userAnswer: null,
  draftAnswer: null, submitted: false, hintLevelUsed: 0, withdrawn: false, isCorrect: null, answer: null, analysis: null })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-learning-token')
    localStorage.setItem('userInfo', JSON.stringify({ id: 1, username: 'learning-test', role: 'STUDENT', status: 1 }))
  })
})

test('diagnostic draft survives refresh and grading waits for finish', async ({ page }) => {
  const state = { sessionId: 'L-diagnostic-test', kind: 'DIAGNOSTIC', state: 'RUNNING', revision: 0, currentIndex: 0,
    blueprint: { id: 'prototype', missing: [{ subject: '操作系统', difficulty: 'HARD', missing: 1 }] }, items: [item(1), item(2)] }
  let submits = 0
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown = []
    if (path.endsWith('/state')) data = state
    else if (path.endsWith('/progress')) {
      const body = route.request().postDataJSON(); expect(body.revision).toBe(state.revision)
      for (const [key, value] of Object.entries(body.answers)) state.items.find(i => i.itemId === Number(key))!.draftAnswer = value as never
      state.revision++; state.currentIndex = body.currentIndex; data = state
    } else if (path.endsWith('/answer')) {
      const body = route.request().postDataJSON(); expect(body.clientRequestId).toBeTruthy(); expect(body.itemId).toBe(1)
      submits++; state.items[0].submitted = true; state.items[0].userAnswer = body.answer; state.items[0].draftAnswer = null; state.revision++
      data = { submitted: true, isCorrect: null, answer: null }
    } else if (path.endsWith('/finish') || path.endsWith('/result')) {
      state.state = 'FINISHED'; state.items[0].isCorrect = 1 as never; state.items[0].answer = 'B' as never; state.items[0].analysis = '结束后保存的解析' as never
      data = { session: state, answered: 1, correct: 1, unanswered: 1, withdrawn: 0, accuracy: 1, independentAccuracy: 1,
        assisted: 0, diagnosticReferenceScore: null, notice: '局部诊断不输出完整参考分', profilePending: true }
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/practice/session/L-diagnostic-test')
  await page.getByText('B. 选择乙', { exact: true }).click()
  await expect(page.getByRole('status')).toContainText('已保存到服务端')
  await page.reload()
  await expect(page.getByRole('radio', { name: 'B. 选择乙' })).toBeChecked()
  await page.getByRole('button', { name: '提交本题' }).click()
  await expect(page.getByText('已提交：B')).toBeVisible()
  await expect(page.getByText('标准答案：B')).toHaveCount(0)
  await expect(page.getByText('结束后保存的解析')).toHaveCount(0)
  await page.getByRole('button', { name: '结束批次并查看结果' }).click()
  await page.getByRole('button', { name: '确定', exact: true }).click()
  await expect(page.getByText('结束后保存的解析')).toBeVisible()
  await expect(page.getByText('局部诊断不输出完整参考分')).toBeVisible()
  expect(submits).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('draft version conflict requires explicit reload and never displays saved', async ({ page }) => {
  const state = { sessionId: 'L-conflict', kind: 'PRACTICE', state: 'RUNNING', revision: 0, currentIndex: 0, blueprint: { id: 'v1' }, items: [item(1)] }
  await page.route('**/api/**', async route => {
    if (new URL(route.request().url()).pathname.endsWith('/progress')) return route.fulfill({ status: 409, json: { code: 409, message: '草稿版本已变化', data: null } })
    await route.fulfill({ json: { code: 0, message: 'ok', data: state } })
  })
  await page.goto('/practice/session/L-conflict')
  await page.getByText('A. 选择甲', { exact: true }).click()
  await expect(page.getByText('尚未保存', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '提交本题' })).toBeDisabled()
  await page.getByRole('button', { name: '重新读取服务端进度' }).click()
  await expect(page.getByRole('radio', { name: 'A. 选择甲' })).not.toBeChecked()
})
