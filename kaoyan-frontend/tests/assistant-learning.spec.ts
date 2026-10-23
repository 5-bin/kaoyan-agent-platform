import { test, expect } from '@playwright/test'
const user = { id: 91, username: 'synthetic-learning', role: 'STUDENT', status: 1 }
const conversation = { id: 'learning-conversation', title: '合成学习会话', conditions: {} }
const privacy = { modelAllowed: false, scopes: [] as string[], version: 1, provider: 'synthetic-model.invalid', retentionDays: 30 }
const question = { questionId: 101, content: '合成错题正文，不发送给前端上下文', snapshotStatus: 'MISSING', isFavorite: 0 }
const action = { id: 'action-one', type: 'FAVORITE_REMOVE', status: 'PENDING', title: '取消所选题目收藏', count: 1, requiresConfirmation: true }
const answer = { outcome: 'COMPLETED', explanationMode: 'rules', answer: '合成学习分析 [外传](https://evil.invalid/?data=private) [依据](https://example.org/reference)', references: [{ id: 's1', title: '批准来源', url: 'https://example.org/reference', locator: '第1段', version: 'synthetic-v1', retrievedAt: '2026-10-23', excerpt: '合成公开资料' }], actions: [action], evidence: [{ ref: 'D1', kind: 'document', title: '合成资料正文', resource: { type: 'document', id: 7 } }] }

test.beforeEach(async ({ page }) => {
  action.status = 'PENDING'
  await page.addInitScript(value => { localStorage.setItem('token', 'synthetic-learning-token'); localStorage.setItem('userInfo', JSON.stringify(value)) }, user)
})

test('question buttons bind Q aliases to their original answer', async ({ page }) => {
  let submitted: any
  const messages = ['堆', 'AVL树'].map((title, index) => ({ id: 'm' + index, content: title, attempts: [{ taskId: 'source-' + index, status: 'SUCCESS', version: 1,
    result: { outcome: 'COMPLETED', explanationMode: 'rules', answer: title, references: [], evidence: [{ ref: 'Q1', title, resource: { type: 'question', id: 100 + index } }] } }] }))
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/privacy/settings')) data = privacy
    else if (path === '/api/conversations') data = { list: [conversation], total: 1 }
    else if (path.endsWith('/messages')) {
      if (route.request().method() === 'POST') { submitted = route.request().postDataJSON(); data = { taskId: 't1', messageId: 'm2' } }
      else data = { conversation, list: [...messages].reverse(), total: 2 }
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/tasks')
  await page.getByRole('button', { name: '收藏 Q1 · 堆', exact: true }).click()
  await expect(page.getByRole('textbox', { name: '聊天输入' })).toHaveValue('收藏 Q1')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect.poll(() => submitted?.referenceTaskId).toBe('source-0')
})

test('page context contains only identifiers; one chat survives page changes and action refreshes records', async ({ page }, info) => {
  let messages: any[] = [], sends = 0, reads = 0, confirmations = 0
  let submitted: any
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/privacy/settings')) data = privacy
    else if (path === '/api/conversations') data = { list: [conversation], total: 1 }
    else if (path.endsWith('/marks/wrong')) { reads++; data = { list: [question], total: 1 } }
    else if (path.endsWith('/marks/favorite')) data = { list: [], total: 0 }
    else if (path.endsWith('/messages')) {
      if (method === 'POST') {
        sends++; submitted = route.request().postDataJSON()
        messages = [{ id: 'm1', sequenceNo: 1, content: submitted.query, attempts: [{ taskId: 't1', status: 'SUCCESS', version: 1, result: answer }] }]
        data = { taskId: 't1', messageId: 'm1' }
      } else data = { conversation, list: messages, total: messages.length }
    } else if (path.endsWith('/confirm')) { confirmations++; action.status = 'SUCCESS'; data = { ...action } }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/wrong')
  await page.locator('.item-head .el-checkbox').click()
  await page.getByRole('button', { name: '考研助手', exact: true }).click()
  await expect(page.locator('.assistant')).toHaveCount(1)
  expect((await page.locator('.chat-heading h2').boundingBox())!.height).toBeLessThan(40)
  if (info.project.name === 'mobile') await expect(page.locator('.assistant')).toHaveCSS('width', '390px')
  else await expect(page.locator('.assistant')).toHaveCSS('width', '440px')
  await expect(page.getByText('外部模型未授权 · 使用本地规则')).toBeVisible()
  await page.getByRole('textbox', { name: '聊天输入' }).fill('取消所选题目收藏')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByRole('button', { name: '确认操作' })).toBeVisible()
  expect(submitted.pageContext).toEqual({ page: 'wrong', selectedQuestionIds: [101], visibleQuestionIds: [101] })
  expect(JSON.stringify(submitted)).not.toContain(question.content)
  expect(confirmations).toBe(0)
  await expect(page.locator('.task-result a[href*="evil.invalid"]')).toHaveCount(0)
  await expect(page.locator('.task-result .markdown a')).toHaveAttribute('href', 'https://example.org/reference')
  await expect(page.locator('.task-result .markdown a')).toHaveAttribute('rel', 'noopener noreferrer')
  const before = reads
  await page.getByRole('button', { name: '确认操作' }).click()
  await expect(page.getByText('涉及 1 题 · 执行成功')).toBeVisible()
  await expect.poll(() => reads).toBeGreaterThan(before)
  if (info.project.name === 'mobile') await page.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('menuitem', { name: '我的收藏', exact: true }).click()
  if (info.project.name === 'mobile') await page.getByRole('button', { name: '考研助手', exact: true }).click()
  await expect(page.getByText('合成学习分析', { exact: false })).toBeVisible()
  if (info.project.name === 'mobile') await page.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Agent 助手', exact: true }).click()
  await expect(page.locator('.assistant')).toHaveCount(1)
  await expect(page.getByText('涉及 1 题 · 执行成功')).toBeVisible()
  expect(sends).toBe(1)
})

test('privacy defaults off, persists categories and clears online chat independently', async ({ page }) => {
  let settings = { ...privacy }, payload: any, cleared = false
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/privacy/settings')) {
      if (method === 'PUT') { payload = route.request().postDataJSON(); settings = { ...settings, ...payload, version: settings.version + 1 } }
      data = settings
    } else if (path === '/api/conversations') {
      if (method === 'DELETE') { cleared = true; data = null }
      else data = { list: cleared ? [] : [conversation], total: cleared ? 0 : 1 }
    } else if (path.endsWith('/messages')) data = { conversation, list: [], total: 0 }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/tasks?conversationId=learning-conversation')
  await page.getByRole('button', { name: '隐私', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '考研助手隐私设置' })
  await expect(dialog).toContainText('synthetic-model.invalid')
  await expect(dialog.getByRole('switch')).not.toBeChecked()
  for (const checkbox of await dialog.getByRole('checkbox').all()) await expect(checkbox).not.toBeChecked()
  await dialog.locator('.el-switch').click()
  await dialog.locator('.el-checkbox').filter({ hasText: '学习统计' }).click()
  await dialog.getByRole('button', { name: '保存隐私设置' }).click()
  await expect(dialog).not.toBeVisible()
  expect(payload).toEqual({ modelAllowed: true, scopes: ['stats'], provider: 'synthetic-model.invalid' })
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual(expect.arrayContaining(['token', 'userInfo']))
  expect(await page.evaluate(() => Object.keys(localStorage).some(key => /privacy|assistant|learning|conversation/i.test(key)))).toBe(false)
  await page.getByRole('button', { name: '隐私', exact: true }).click()
  await dialog.getByRole('button', { name: '清除全部助手记录' }).click()
  await page.getByRole('button', { name: '确定', exact: true }).click()
  await expect.poll(() => cleared).toBe(true)
  await expect(page).toHaveURL(/\/tasks$/)
})

test('published content opens in place and statistics use complete range aggregates', async ({ page }) => {
  let documentReads = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/privacy/settings')) data = privacy
    else if (path === '/api/documents') { documentReads++; data = [{ id: 7, subject: '操作系统', title: '合成资料正文', content: '# 同步与互斥\n' + '正文第十行。'.repeat(50), status: 'PUBLISHED' }] }
    else if (path === '/api/conversations') data = { list: [conversation], total: 1 }
    else if (path.endsWith('/messages')) data = { conversation, total: 1, list: [{ id: 'restored-message', content: '收藏这道题', attempts: [{ taskId: 'restored-task', status: 'SUCCESS', version: 1, result: { ...answer, actions: [{ ...action, id: 'restored-action', status: 'SUCCESS', requiresConfirmation: false }] } }] }] }
    else if (path.endsWith('/stats/learning')) data = { questionCount: 12, correctCount: 9, uniqueQuestions: 8, wrongCount: 3, accuracy: 0.75, from: '2026-09-24', to: '2026-10-23', daily: [], knowledgePoints: [] }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/documents?documentId=7')
  await expect(page.getByRole('dialog')).toContainText('同步与互斥')
  await expect(page.getByRole('dialog')).toContainText('正文第十行。'.repeat(50))
  await page.getByRole('dialog').locator('.el-dialog__headerbtn').click()
  await expect(page).not.toHaveURL(/documentId=/)
  await page.getByRole('button', { name: '考研助手', exact: true }).click()
  await expect.poll(() => documentReads).toBeGreaterThan(1)
  await expect(page.getByRole('dialog', { name: '合成资料正文' })).not.toBeVisible()
  await page.locator('.chat-heading').getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('menuitem', { name: '学习统计', exact: true }).click()
  await expect(page.locator('.stats')).toContainText('12')
  await expect(page.locator('.stats')).toContainText('75%')
  await expect(page.getByText('去重题数：8', { exact: false })).toBeVisible()
})

test('an already completed direct favorite refreshes the page without requiring an SSE event', async ({ page }) => {
  let completed = false, reads = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/privacy/settings')) data = privacy
    else if (path === '/api/conversations') data = { list: [conversation], total: 1 }
    else if (path.endsWith('/marks/wrong')) { reads++; data = { list: [{ ...question, isFavorite: completed ? 1 : 0 }], total: 1 } }
    else if (path.endsWith('/messages')) {
      if (route.request().method() === 'POST') { completed = true; data = { taskId: 'direct-task', messageId: 'direct-message' } }
      else data = { conversation, total: completed ? 1 : 0, list: completed ? [{ id: 'direct-message', content: '收藏这道题', attempts: [{ taskId: 'direct-task', status: 'SUCCESS', version: 1, result: { ...answer, actions: [{ ...action, id: 'direct-action', type: 'FAVORITE_ADD', status: 'SUCCESS', requiresConfirmation: false }] } }] }] : [] }
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/wrong')
  await page.getByRole('button', { name: '考研助手', exact: true }).click()
  const before = reads
  await page.getByRole('textbox', { name: '聊天输入' }).fill('收藏这道题')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByText('涉及 1 题 · 执行成功')).toBeVisible()
  await expect.poll(() => reads).toBeGreaterThan(before)
  if (test.info().project.name === 'mobile') await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByText('已收藏', { exact: true })).toBeVisible()
})
