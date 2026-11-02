import { test, expect, type Page } from '@playwright/test'

async function setup(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'handoff-token')
    localStorage.setItem('userInfo', JSON.stringify({ id: 1, username: 'handoff', role: 'STUDENT', status: 1 }))
  })
  const messages: any[] = [], sent: any[] = []
  let created = false, taskSubmissions = 0
  const conversation = { id: 'handoff-conversation', title: '错题辅导', conditions: {} }
  const legacy = { id: 'legacy-parent', taskType: 'WRONG_QUESTION_TUTOR', status: 'SUCCESS',
    tutoring: { recordId: 71, query: '原有问题', messages: [] },
    resultPayload: { outcome: 'COMPLETED', answer: '原解释', explanationMode: 'rules', resolvedTaskType: 'WRONG_QUESTION_TUTOR',
      recordId: 71, standardAnswer: 'B', userAnswer: 'A', questionVersion: 2, references: [] } }
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = { id: 1, username: 'handoff', role: 'STUDENT', status: 1 }
    else if (path.endsWith('/privacy/settings')) data = { modelAllowed: false, scopes: [], version: 1 }
    else if (path.endsWith('/learning/status')) data = { enabled: true }
    else if (path.endsWith('/marks/wrong')) data = { total: 1, list: [{ questionId: 3, recordId: 71, isCorrect: 0,
      content: '线程错题', answer: 'B', analysis: '已保存解析', snapshotStatus: 'AVAILABLE' }] }
    else if (path === '/api/tasks') { if (method === 'POST') taskSubmissions++; data = { list: [legacy], total: 1 } }
    else if (path === '/api/conversations') {
      if (method === 'POST') { created = true; data = conversation }
      else data = { list: created ? [conversation] : [], total: created ? 1 : 0 }
    } else if (path.endsWith('/messages')) {
      if (method === 'POST') {
        const body = route.request().postDataJSON(); sent.push(body)
        messages.push({ id: 'm' + sent.length, sequenceNo: sent.length, content: body.query, tutoring: body.tutoring,
          attempts: [{ taskId: 't' + sent.length, status: 'RUNNING', version: 0, draft: {} }] })
        data = { taskId: 't' + sent.length, messageId: 'm' + sent.length }
      } else data = { conversation, list: [...messages].reverse(), total: messages.length }
    } else if (path.endsWith('/stream')) {
      const message = messages.at(-1), result = { ...legacy.resultPayload, answer: '本轮辅导已完成', conditions: {} }
      message.attempts[0] = { taskId: 't' + sent.length, status: 'SUCCESS', version: 1, result }
      return route.fulfill({ contentType: 'text/event-stream', body: 'event: completed\ndata: ' + JSON.stringify(message.attempts[0]) + '\n\n' })
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  return { sent, taskSubmissions: () => taskSubmissions }
}

for (const fromHistory of [false, true]) {
  test(`owned wrong attempt enters the main assistant without sending: history=${fromHistory}`, async ({ page }) => {
    const state = await setup(page)
    await page.goto(fromHistory ? '/tasks/history' : '/wrong')
    if (fromHistory) await page.getByRole('button', { name: '查看', exact: true }).click()
    await page.getByRole('button', { name: '到助手继续辅导', exact: true }).click()
    await expect(page).toHaveURL(/\/tasks\?tutorRecordId=71/)
    await expect(page.getByText('已选择一条已判分错题，后续问题将围绕这次作答。')).toBeVisible()
    expect(state.sent).toHaveLength(0); expect(state.taskSubmissions()).toBe(0)
    await page.getByRole('button', { name: '发送', exact: true }).click()
    await expect(page.locator('.task-result')).toContainText('标准答案 B')
    expect(state.sent[0].tutoring).toEqual(fromHistory ? { recordId: 71, parentTaskId: 'legacy-parent' } : { recordId: 71 })
    expect(state.sent[0]).not.toHaveProperty('attempt'); expect(state.sent[0]).not.toHaveProperty('messages')
    await page.reload()
    await expect(page.getByRole('button', { name: '清除错题上下文', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '清除错题上下文', exact: true }).click()
    await page.getByRole('textbox', { name: '聊天输入', exact: true }).fill('你好')
    await page.getByRole('button', { name: '发送', exact: true }).click()
    await expect.poll(() => state.sent.length).toBe(2)
    expect(state.sent[1]).not.toHaveProperty('tutoring')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

for (const diagnostic of [false, true]) {
  test(`managed practice only offers tutoring after grades are revealed: diagnostic=${diagnostic}`, async ({ page }) => {
    await setup(page)
    let finished = false
    await page.route('**/api/practice/sessions/L-handoff/**', async route => {
      const path = new URL(route.request().url()).pathname
      if (path.endsWith('/finish')) finished = true
      const revealed = !diagnostic || finished
      const state = { sessionId: 'L-handoff', kind: diagnostic ? 'DIAGNOSTIC' : 'PRACTICE', state: finished ? 'FINISHED' : 'RUNNING',
        revision: 0, currentIndex: 0, blueprint: { missing: [] }, items: [{ itemId: 71, questionId: 3, orderIndex: 0, subject: '操作系统', knowledgePoint: '线程', difficulty: 'EASY',
          content: '线程题', optionA: '甲', optionB: '乙', submitted: true, userAnswer: 'A', withdrawn: false, hintLevelUsed: 0,
          isCorrect: revealed ? 0 : null, answer: revealed ? 'B' : null, analysis: revealed ? '原解析' : null }] }
      const data = (path.endsWith('/result') || path.endsWith('/finish')) ? { session: state, total: 1, answered: 1, unanswered: 0, correct: 0, withdrawn: 0, accuracy: 0, assisted: 0 } : state
      await route.fulfill({ json: { code: 0, data } })
    })
    await page.goto('/practice/session/L-handoff')
    if (diagnostic) {
      await expect(page.getByRole('button', { name: '到助手继续辅导', exact: true })).toHaveCount(0)
      await expect(page.getByText('标准答案：B')).toHaveCount(0)
      await page.getByRole('button', { name: '结束批次并查看结果', exact: true }).click()
      await page.getByRole('dialog').getByRole('button', { name: '确定', exact: true }).click()
    }
    await expect(page.getByRole('button', { name: '到助手继续辅导', exact: true })).toBeVisible()
  })
}


test('account switch discards a late compatibility tutor result', async ({ page }) => {
  await setup(page)
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  let started = false
  await page.route('**/api/tasks', async route => {
    if (route.request().method() !== 'POST') return route.fallback()
    started = true; await pending
    await route.fulfill({ json: { code: 0, data: { id: 'late-private', status: 'SUCCESS', taskType: 'WRONG_QUESTION_TUTOR',
      tutoring: { recordId: 71, query: 'old-account-question', messages: [] },
      resultPayload: { outcome: 'COMPLETED', answer: 'old-account-private-result', explanationMode: 'rules', resolvedTaskType: 'WRONG_QUESTION_TUTOR', references: [] } } } }).catch(() => {})
  })
  await page.goto('/wrong')
  await page.getByRole('button', { name: 'AI 解释与追问', exact: true }).click()
  await page.getByRole('button', { name: '生成解释', exact: true }).click()
  await expect.poll(() => started).toBe(true)
  await page.evaluate(() => {
    const user = (document.querySelector('#app') as any).__vue_app__.config.globalProperties.$pinia._s.get('user')
    user.token = 'next-account'; user.setUserInfo({ id: 2, username: 'next-account', role: 'STUDENT' })
  })
  release()
  await expect(page.locator('.uname')).toHaveText('next-account')
  await expect(page.locator('.tutor .task-result')).toHaveCount(0)
  await expect(page.getByText('old-account-private-result')).toHaveCount(0)
})
