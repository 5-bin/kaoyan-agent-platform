import { test, expect } from '@playwright/test'

const user = { id: 1, username: 'chat-browser', role: 'STUDENT', status: 1 }
const releaseId = 'rag-v1-1234567890abcdef'
const document = { id: 'document-one', title: '个人笔记', content: '# 原文\n保留这段内容', version: 1 }
const result = { outcome: 'COMPLETED', answer: '线程共享地址空间。', explanationMode: 'ai', resolvedTaskType: 'KNOWLEDGE_QA', releaseId, references: [], conditions: { examYear: 2027 } }
const conversation = { id: 'conversation-one', title: '进程与线程', conditions: { examYear: 2027 } }

test.beforeEach(async ({ page }) => {
  await page.addInitScript(u => { localStorage.setItem('token', 'chat-token'); localStorage.setItem('userInfo', JSON.stringify(u)) }, user)
})

test('persistent chat, IME input, streaming final, history and responsive drawer', async ({ page }, info) => {
  const messages: any[] = []
  let sends = 0, final = false, saved = false
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    let data: unknown = {}
    if (path.endsWith('/users/me')) data = user
    else if (path === '/api/conversations') data = { list: [conversation], total: 1 }
    else if (path === '/api/personal-documents') data = { list: [document], total: 1 }
    else if (path.endsWith('/messages') && method === 'GET') data = { list: [...messages].reverse(), total: messages.length, conversation }
    else if (path.endsWith('/messages') && method === 'POST') {
      sends++
      const body = route.request().postDataJSON()
      expect(body.clientRequestId).toBeTruthy()
      expect(body.userId).toBeUndefined()
      messages.push({ id: 'message-one', sequenceNo: 1, content: body.query, attempts: [{ taskId: 'task-one', attemptNo: 1, status: 'RUNNING', version: 0, draft: {} }] })
      data = { taskId: 'task-one', messageId: 'message-one' }
    } else if (path.endsWith('/stream')) {
      const proposal = { operation: 'create', title: '线程笔记', content: '# 新笔记\n<script>alert(1)</script>' }
      const value = { ...result, documentProposal: proposal }
      messages[0].attempts[0] = { taskId: 'task-one', attemptNo: 1, status: 'SUCCESS', version: 3, result: value, draft: {} }
      final = true
      await route.fulfill({ contentType: 'text/event-stream', body:
        'event: snapshot\ndata: ' + JSON.stringify({ taskId: 'task-one', status: 'RUNNING', version: 0, draft: {} }) + '\n\n' +
        'event: delta\ndata: ' + JSON.stringify({ taskId: 'task-one', version: 1, slot: 'answer', offset: 0, text: '线程' }) + '\n\n' +
        'event: completed\ndata: ' + JSON.stringify({ taskId: 'task-one', status: 'SUCCESS', version: 3, result: value, draft: {} }) + '\n\n' })
      return
    } else if (path.endsWith('/apply-document')) { saved = true; data = { ...document, title: '线程笔记', version: 1 } }
    else if (path === '/api/tasks') data = { list: [], total: 0 }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/tasks')
  await expect(page).toHaveURL(/conversationId=conversation-one/)
  const input = page.getByRole('textbox', { name: '聊天输入' })
  await input.fill('进程与线程')
  await input.dispatchEvent('compositionstart')
  await input.press('Enter')
  expect(sends).toBe(0)
  await input.dispatchEvent('compositionend')
  await input.press('Shift+Enter')
  expect(sends).toBe(0)
  await input.press('Enter')
  await expect(page.getByText('线程共享地址空间。', { exact: true })).toBeVisible()
  expect(final).toBe(true); expect(sends).toBe(1)
  await page.getByRole('button', { name: '预览笔记建议' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('heading', { name: '新笔记', exact: true })).toBeVisible()
  await expect(dialog.locator('.markdown script')).toHaveCount(0)
  expect(saved).toBe(false)
  await dialog.getByRole('button', { name: '确认保存建议' }).click()
  await expect(page.getByText('已保存', { exact: true })).toBeVisible()
  expect(saved).toBe(true)
  await page.reload()
  await expect(page.getByText('线程共享地址空间。', { exact: true })).toBeVisible()
  expect(sends).toBe(1)
  if (info.project.name === 'mobile') {
    await page.getByRole('button', { name: '会话', exact: true }).click()
    await expect(page.getByRole('dialog', { name: '会话' })).toBeVisible()
    await page.getByRole('dialog', { name: '会话' }).getByRole('link', { name: '任务历史' }).click()
  } else await page.getByRole('link', { name: '任务历史' }).click()
  await expect(page).toHaveURL(/\/tasks\/history/)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false)
})

test('stop, retry, reconnect snapshot and account switch discard late responses', async ({ page }) => {
  let status = 'RUNNING', retryCount = 0, streamCount = 0, cancelCount = 0
  let resolveLate!: () => void
  const late = new Promise<void>(resolve => { resolveLate = resolve })
  const attempt = () => ({ taskId: retryCount ? 'task-two' : 'task-one', attemptNo: retryCount + 1, status, version: status === 'RUNNING' ? 0 : 4, draft: status === 'RUNNING' ? { answer: '已恢复的临时内容' } : {} })
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    const newerAccount = route.request().headers().authorization === 'Bearer new-account-token'
    let data: unknown = {}
    if (path.endsWith('/users/me')) data = newerAccount ? { ...user, id: 2, username: 'new-account' } : user
    else if (path === '/api/conversations') data = { list: newerAccount ? [] : [conversation], total: newerAccount ? 0 : 1 }
    else if (path === '/api/personal-documents') data = { list: [], total: 0 }
    else if (path.endsWith('/messages')) data = { conversation, total: newerAccount ? 0 : 1, list: newerAccount ? [] : [{ id: 'message-one', sequenceNo: 1, content: '进程与线程', attempts: [attempt()] }] }
    else if (path.endsWith('/cancel')) { status = 'CANCELLED'; cancelCount++; data = attempt() }
    else if (path.endsWith('/retry')) { status = 'RUNNING'; retryCount++; data = { taskId: 'task-two', messageId: 'message-one' } }
    else if (path.endsWith('/stream')) {
      streamCount++
      if (retryCount) {
        await late
        await route.fulfill({ status: 401, json: { code: 401, message: 'old token' } }).catch(() => {})
      } else await route.fulfill({ contentType: 'text/event-stream', body: 'event: snapshot\ndata: ' + JSON.stringify(attempt()) + '\n\n' })
      return
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/tasks?conversationId=conversation-one')
  await expect(page.getByText('已恢复的临时内容', { exact: true })).toBeVisible()
  await expect.poll(() => streamCount).toBeGreaterThan(1)
  await page.getByRole('button', { name: '停止生成' }).click()
  await expect(page.getByText('已停止生成', { exact: true })).toBeVisible()
  expect(cancelCount).toBe(1)
  await page.getByRole('button', { name: '重试此问题' }).click()
  await expect.poll(() => retryCount).toBe(1)
  await page.getByRole('textbox', { name: '聊天输入' }).fill('不应留给下个账号的草稿')
  await page.evaluate(() => {
    const store = (document.querySelector('#app') as any).__vue_app__.config.globalProperties.$pinia._s.get('user')
    store.token = 'new-account-token'; store.setUserInfo({ id: 2, username: 'new-account', role: 'STUDENT' })
    localStorage.setItem('token', 'new-account-token')
  })
  resolveLate()
  await expect(page.getByRole('textbox', { name: '聊天输入' })).toHaveValue('')
  await expect(page.locator('.uname')).toHaveText('new-account')
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBe('new-account-token')
})
