import { test, expect, type Page } from '@playwright/test'

async function login(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'tutor-fixture')
    localStorage.setItem('userInfo', JSON.stringify({ id: 1, username: 'tutor-test', role: 'STUDENT', status: 1 }))
  })
}
function task(id: string, input: Record<string, unknown>, mode = 'ai') {
  return { id, taskType: 'WRONG_QUESTION_TUTOR', status: 'SUCCESS', createdAt: '2026-10-25',
    tutoring: { messages: [], ...input }, resultPayload: { outcome: 'COMPLETED', resolvedTaskType: 'WRONG_QUESTION_TUTOR',
      explanationMode: mode, answer: id === 'turn-1' ? '解释线程区别 <img src=x onerror=alert(1)>' : '通过例子说明本题。',
      recordId: 71, standardAnswer: 'B', userAnswer: 'A', questionVersion: 2, releaseId: 'rag-v1-1234567890abcdef', references: [],
      notice: mode === 'rules' ? '未启用 AI，当前仅展示原题解析，尚未生成个性化解释或追问回答。' : 'AI 辅助解释可能有误。' } }
}
const wrong = { questionId: 3, recordId: 71, isCorrect: 0, content: '线程错题', answer: 'B', analysis: '原解析', snapshotStatus: 'AVAILABLE' }

test('wrong answer enables explicit explanation and chained followups, persisted history can continue', async ({ page }, testInfo) => {
  await login(page)
  const saved: ReturnType<typeof task>[] = []
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown
    if (path.endsWith('/tasks') && route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      expect(body.taskType).toBe('WRONG_QUESTION_TUTOR')
      expect(body.input.recordId).toBe(71)
      expect(body.input).not.toHaveProperty('messages')
      expect(body.input).not.toHaveProperty('attempt')
      if (saved.length) expect(body.input.parentTaskId).toBe(saved.at(-1)?.id)
      else expect(body.input).not.toHaveProperty('parentTaskId')
      const prior = saved.at(-1)
      const messages = prior ? [...((prior.tutoring.messages as unknown[]) || []),
        { role: 'user', content: prior.tutoring.query }, { role: 'assistant', content: prior.resultPayload.answer }].slice(-6) : []
      data = task('turn-' + (saved.length + 1), { ...body.input, messages })
      saved.push(data as ReturnType<typeof task>)
    } else if (path.endsWith('/tasks')) data = { total: saved.length, list: [...saved].reverse() }
    else if (path.endsWith('/answer')) data = { questionId: 3, recordId: 71, userAnswer: 'A', isCorrect: 0, answer: 'B', analysis: '原解析' }
    else if (path.endsWith('/questions/3')) data = { id: 3, content: '线程错题', optionA: '选项甲', optionB: '选项乙' }
    else data = [{ id: 71, questionId: 3, orderIndex: 0, isCorrect: null }]
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/practice/session/tutor')
  await expect(page.getByRole('button', { name: 'AI 解释与追问' })).toHaveCount(0)
  await page.getByText('选项甲', { exact: true }).click()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.locator('.feedback')).toContainText('回答错误，正确答案：B')
  expect(saved).toHaveLength(0)
  await page.getByRole('button', { name: 'AI 解释与追问' }).click()
  await page.getByRole('button', { name: '生成解释' }).click()
  await expect(page.locator('.task-result')).toContainText('AI解释')
  await expect(page.locator('.task-result')).toContainText('标准答案 B')
  await expect(page.locator('.tutor img')).toHaveCount(0)
  await page.getByRole('textbox', { name: '错题追问' }).fill('能举个例子吗？')
  await page.getByRole('button', { name: '发送追问' }).click()
  await expect(page.locator('.task-result')).toContainText('通过例子说明本题')
  expect(saved).toHaveLength(2)
  await page.goto('/tasks/history')
  await page.reload()
  await page.getByRole('button', { name: '查看', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('能举个例子吗？')
  await expect(dialog).toContainText('解释线程区别')
  await dialog.getByRole('textbox', { name: '错题追问' }).fill('再解释一下')
  await dialog.getByRole('button', { name: '发送追问' }).click()
  await expect(dialog.locator('.task-result')).toContainText('通过例子说明本题')
  await expect(dialog.getByRole('textbox', { name: '错题追问' })).toHaveValue('')
  expect(saved).toHaveLength(3)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('tutor-followup.png'), fullPage: true })
})

test('wrongbook exposes only saved wrong attempts and honestly labels disabled model and failure', async ({ page }) => {
  await login(page)
  let calls = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    if (route.request().method() === 'POST') {
      calls++
      if (calls === 1) return route.fulfill({ status: 429, json: { code: 429, message: '任务额度已满', data: null } })
      const body = route.request().postDataJSON()
      return route.fulfill({ json: { code: 0, message: 'ok', data: task('turn-1', body.input, 'rules') } })
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data: { total: 4, list: [wrong,
      { questionId: 4, content: '手动标记未答题', snapshotStatus: 'NOT_ANSWERED' },
      { ...wrong, questionId: 5, recordId: 72, isCorrect: 1 },
      { ...wrong, questionId: 6, recordId: 73, snapshotStatus: 'PARTIAL' }] } } })
  })
  await page.goto('/wrong')
  await expect(page.getByRole('button', { name: 'AI 解释与追问' })).toHaveCount(1)
  await page.getByRole('button', { name: 'AI 解释与追问' }).click()
  await page.getByRole('button', { name: '生成解释' }).click()
  await expect(page.getByRole('alert').filter({ hasText: '暂时无法生成' })).toBeVisible()
  await expect(page.locator('.card.item').first()).toContainText('原解析')
  await page.getByRole('button', { name: '生成解释' }).click()
  await expect(page.locator('.task-result')).toContainText('未启用 AI')
  await expect(page.locator('.task-result')).not.toContainText('AI解释')
})

test('late response cannot populate a different attempt after navigation', async ({ page }) => {
  await login(page)
  let release: () => void = () => {}
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/tasks')) {
      await gate
      return route.fulfill({ json: { code: 0, message: 'ok', data: task('turn-1', { recordId: 71, query: '旧问题' }) } })
    }
    return route.fulfill({ json: { code: 0, message: 'ok', data: path.endsWith('/review')
      ? { total: 1, list: [{ ...wrong, recordId: 72, content: '另一次作答' }] }
      : path.includes('/sessions/') ? [{ id: 72, questionId: 3, orderIndex: 0, isCorrect: 0 }]
      : { total: 1, list: [wrong] } } })
  })
  await page.goto('/wrong')
  await page.getByRole('button', { name: 'AI 解释与追问' }).click()
  await page.getByRole('button', { name: '生成解释' }).click()
  await expect(page.getByRole('textbox', { name: '错题追问' })).toBeDisabled()
  await page.goto('/practice/session/another')
  await expect(page.getByText('另一次作答', { exact: true })).toBeVisible()
  release()
  await page.getByRole('button', { name: 'AI 解释与追问' }).click()
  await expect(page.locator('.task-result')).toHaveCount(0)
})

test('agent offline keeps original analysis and permits retrying the same question', async ({ page }) => {
  await login(page)
  let calls = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    if (route.request().method() === 'POST') {
      calls++
      const input = route.request().postDataJSON().input
      expect(input).not.toHaveProperty('parentTaskId')
      const data = calls === 1 ? { id: 'failed-1', taskType: 'WRONG_QUESTION_TUTOR', status: 'FAILED',
        tutoring: { ...input, messages: [] }, errorMessage: 'Agent 暂时不可用' } : task('turn-1', input)
      return route.fulfill({ json: { code: 0, message: 'ok', data } })
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data: { total: 1, list: [wrong] } } })
  })
  await page.goto('/wrong')
  await page.getByRole('button', { name: 'AI 解释与追问' }).click()
  await page.getByRole('textbox', { name: '错题追问' }).fill('想了解原理')
  await page.getByRole('button', { name: '生成解释' }).click()
  await expect(page.locator('.task-result')).toContainText('Agent 暂时不可用')
  await expect(page.getByRole('textbox', { name: '错题追问' })).toHaveValue('想了解原理')
  await expect(page.locator('.body')).toContainText('原解析')
  await page.getByRole('button', { name: '生成解释' }).click()
  await expect(page.locator('.task-result')).toContainText('标准答案 B')
  expect(calls).toBe(2)
})
