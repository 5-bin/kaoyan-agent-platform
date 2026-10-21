import { test, expect, type Page, type Route } from '@playwright/test'

type RecordRow = { questionId: number; orderIndex: number; isCorrect: number | null; gradingStatus: string; userAnswer?: string }
const rows = (count: number): RecordRow[] => Array.from({ length: count }, (_, i) => ({
  questionId: i + 1, orderIndex: i, isCorrect: null, gradingStatus: 'valid'
}))
const ok = (route: Route, data: unknown) => route.fulfill({ json: { code: 0, message: 'ok', data } })
const fail = (route: Route, status: number) => route.fulfill({ status,
  json: { code: status, message: '隔离测试请求失败', data: null } })

async function fixture(page: Page, records: RecordRow[]) {
  const calls = { answers: [] as number[], details: [] as number[], summary: 0 }
  await page.addInitScript(() => {
    localStorage.setItem('token', 'practice-recovery-fixture')
    localStorage.setItem('userInfo', JSON.stringify({ id: 1, username: 'recovery', role: 'STUDENT', status: 1 }))
  })
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/answer')) {
      const { questionId, answer } = route.request().postDataJSON()
      calls.answers.push(questionId)
      const record = records.find(r => r.questionId === questionId)!
      record.isCorrect = answer === 'B' ? 1 : 0
      record.userAnswer = answer
      return ok(route, { questionId, userAnswer: answer, isCorrect: record.isCorrect, answer: 'B', analysis: '保存的解析' })
    }
    if (url.pathname.includes('/questions/')) {
      const id = Number(url.pathname.split('/').pop())
      calls.details.push(id)
      return ok(route, { id, content: `题干${id}`, optionA: `选项甲${id}`, optionB: `选项乙${id}` })
    }
    if (url.pathname.endsWith('/review')) {
      const start = (Number(url.searchParams.get('pageNum') || 1) - 1) * 10
      return ok(route, { total: records.length, list: records.slice(start, start + 10).map(r => ({
        ...r, content: `题干${r.questionId}`, optionA: `选项甲${r.questionId}`, optionB: `选项乙${r.questionId}`,
        ...(r.isCorrect == null ? { snapshotStatus: 'NOT_ANSWERED' } : { snapshotStatus: 'AVAILABLE', answer: 'B', analysis: '保存的解析' })
      })) })
    }
    if (url.pathname.endsWith('/ai-summary')) { calls.summary++; return ok(route, { status: 'SUCCESS' }) }
    return ok(route, records)
  })
  return calls
}

async function answerAndNext(page: Page, id: number, last = false) {
  await page.getByText(`选项乙${id}`, { exact: true }).click()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.locator('.feedback')).toContainText('回答正确')
  await page.getByRole('button', { name: last ? '完成，查看结果' : '下一题', exact: true }).click()
}

test('legacy snapshots display saved answer and choice without fetching current options', async ({ page }) => {
  const records = rows(1); records[0].isCorrect = 0; records[0].userAnswer = 'A'
  const calls = await fixture(page, records)
  await page.route('**/api/practice/sessions/*/review?*', route => ok(route, { total: 1, list: [{
    ...records[0], content: '旧快照题干', answer: 'B', snapshotStatus: 'PARTIAL'
  }] }))
  await page.goto('/practice/session/legacy')
  await expect(page.locator('.saved-answer')).toContainText('正确答案：B')
  await expect(page.locator('.saved-answer')).toContainText('你的选择：A')
  await expect(page.locator('.q-card')).toContainText('历史快照不完整')
  await expect(page.locator('.q-card .opt')).toHaveCount(0)
  expect(calls.details).toEqual([])
})

test('partial review resumes at the next unanswered question and completes', async ({ page }) => {
  const records = rows(3)
  const calls = await fixture(page, records)
  await page.goto('/practice/session/resume')
  await answerAndNext(page, 1)
  await page.getByRole('button', { name: '查看已保存作答' }).click()
  await expect(page.locator('.saved-answer')).toHaveCount(1)
  await expect(page.locator('.sum-item').filter({ hasText: '未作答' }).locator('.sum-num')).toHaveText('2')
  await page.getByRole('button', { name: '继续作答', exact: true }).click()
  await expect(page.locator('.q-title')).toHaveText('题干2')
  await expect(page.locator('.picked')).toHaveCount(0)
  await expect(page.locator('.feedback')).toHaveCount(0)
  await answerAndNext(page, 2)
  await answerAndNext(page, 3, true)
  await expect(page.getByText('本次练习完成', { exact: true })).toBeVisible()
  expect(calls.answers).toEqual([1, 2, 3])
})

test('withdrawn record and unavailable first question skip without submitting', async ({ page }) => {
  const records = rows(3); records[0].gradingStatus = 'withdrawn'
  const calls = await fixture(page, records)
  await page.route('**/api/questions/2', route => fail(route, 404))
  await page.goto('/practice/session/skip-first')
  await expect(page.locator('.q-title')).toHaveText('题干3')
  await expect(page.getByText(/题目已不可用，已跳过 2 题/)).toBeVisible()
  expect(calls.details).toEqual([3])
  expect(calls.answers).toEqual([])
  expect(records.every(r => r.isCorrect == null)).toBe(true)
})

test('unavailable middle question skips and keeps remaining valid questions reachable', async ({ page }) => {
  const records = rows(3)
  const calls = await fixture(page, records)
  await page.route('**/api/questions/2', route => fail(route, 404))
  await page.goto('/practice/session/skip-middle')
  await answerAndNext(page, 1)
  await expect(page.locator('.q-title')).toHaveText('题干3')
  await answerAndNext(page, 3, true)
  await expect(page.getByText('暂无可继续作答的题目', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '生成 AI 总结' })).toBeDisabled()
  expect(calls.answers).toEqual([1, 3])
  expect(records[1].isCorrect).toBeNull()
})

test('all unavailable stays incomplete and refresh can recheck restored questions', async ({ page }) => {
  const records = rows(2)
  const calls = await fixture(page, records)
  let unavailable = true
  await page.route('**/api/questions/*', route => unavailable ? fail(route, 404) : route.fallback())
  await page.goto('/practice/session/all-unavailable')
  await expect(page.getByText('暂无可继续作答的题目', { exact: true })).toBeVisible()
  await expect(page.getByText('本次练习完成', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '生成 AI 总结' })).toBeDisabled()
  await page.getByRole('button', { name: '查看回顾', exact: true }).click()
  await expect(page.locator('.saved-answer')).toHaveCount(0)
  expect(calls.answers).toEqual([]); expect(calls.summary).toBe(0)
  unavailable = false
  await page.getByRole('button', { name: '继续作答', exact: true }).click()
  await expect(page.locator('.q-title')).toHaveText('题干1')
})

for (const failure of ['network', 'timeout', 'server'] as const) {
  test(`${failure} question load failure retries the same question without skipping`, async ({ page }) => {
    const calls = await fixture(page, rows(2))
    let attempts = 0
    await page.route('**/api/questions/1', async route => {
      if (++attempts > 1) return route.fallback()
      if (failure === 'server') return fail(route, 500)
      return route.abort(failure === 'timeout' ? 'timedout' : 'failed')
    })
    await page.goto('/practice/session/retry')
    await expect(page.getByRole('button', { name: '重试加载', exact: true })).toBeVisible()
    await expect(page.getByText(/题目已不可用，已跳过/)).toHaveCount(0)
    await page.getByRole('button', { name: '重试加载', exact: true }).click()
    await expect(page.locator('.q-title')).toHaveText('题干1')
    expect(calls.details).toEqual([1]); expect(calls.answers).toEqual([])
  })
}

for (const status of [404, 409]) {
  test(`submission ${status} rechecks unavailable question and proceeds without replay`, async ({ page }) => {
    const records = rows(2)
    const calls = await fixture(page, records)
    let submitted = false
    let submissionAttempts = 0
    await page.route('**/api/questions/1', route => submitted ? fail(route, 404) : route.fallback())
    await page.route('**/api/practice/sessions/*/answer', route => {
      submitted = true; submissionAttempts++
      return fail(route, status)
    })
    await page.goto('/practice/session/withdraw-during-submit')
    await page.getByText('选项甲1', { exact: true }).click()
    await page.getByRole('button', { name: '提交答案', exact: true }).click()
    await expect(page.locator('.q-title')).toHaveText('题干2')
    await expect(page.locator('.feedback')).toHaveCount(0)
    expect(submissionAttempts).toBe(1); expect(calls.answers).toEqual([])
    expect(records[0].isCorrect).toBeNull()
  })
}

test('duplicate submission syncs saved server result and can continue without grading again', async ({ page }) => {
  const records = rows(2)
  await fixture(page, records)
  let attempts = 0
  await page.route('**/api/practice/sessions/*/answer', route => {
    attempts++; records[0].isCorrect = 0; records[0].userAnswer = 'A'
    return fail(route, 409)
  })
  await page.goto('/practice/session/duplicate')
  await page.getByText('选项乙1', { exact: true }).click()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.locator('.saved-answer')).toContainText('你的选择：A')
  await expect(page.locator('.sum-item').filter({ hasText: '答错' }).locator('.sum-num')).toHaveText('1')
  await page.getByRole('button', { name: '继续作答', exact: true }).click()
  await expect(page.locator('.q-title')).toHaveText('题干2')
  expect(attempts).toBe(1)
})

test('configuration conflict keeps a playable question for retry instead of skipping', async ({ page }) => {
  await fixture(page, rows(2))
  await page.route('**/api/practice/sessions/*/answer', route => fail(route, 409))
  await page.goto('/practice/session/configuration-conflict')
  await page.getByText('选项甲1', { exact: true }).click()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.locator('.q-title')).toHaveText('题干1')
  await expect(page.getByRole('button', { name: '重试加载', exact: true })).toBeVisible()
  await expect(page.getByText(/题目已不可用，已跳过/)).toHaveCount(0)
})

test('failed review or resume keeps current view and blocks overlapping actions', async ({ page }) => {
  const records = rows(2)
  await fixture(page, records)
  let reviewFails = true
  await page.route('**/api/practice/sessions/*/review?*', route => reviewFails ? fail(route, 500) : route.fallback())
  await page.goto('/practice/session/failed-transitions')
  await page.getByRole('button', { name: '查看已保存作答' }).click()
  await expect(page.getByRole('button', { name: '查看已保存作答' })).toBeEnabled()
  await expect(page.locator('.q-title')).toHaveText('题干1')
  reviewFails = false
  await page.getByRole('button', { name: '查看已保存作答' }).click()
  await expect(page.locator('.summary')).toBeVisible()
  let release!: () => void
  let requested!: () => void
  const arrived = new Promise<void>(resolve => { requested = resolve })
  const held = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/questions/1', async route => { requested(); await held; await fail(route, 500) })
  await page.getByRole('button', { name: '继续作答', exact: true }).click()
  await arrived
  await expect(page.getByRole('button', { name: '继续作答', exact: true })).toBeDisabled()
  release()
  await expect(page.getByRole('button', { name: '重试加载', exact: true })).toBeVisible()
  await expect(page.locator('.summary')).toBeVisible()
  await expect(page.locator('.sum-item').filter({ hasText: '未作答' }).locator('.sum-num')).toHaveText('2')
})
