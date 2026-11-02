import { test, expect, type Page } from '@playwright/test'

const user = { id: 1, username: 'practice-navigation', role: 'STUDENT', status: 1 }
const conversation = { id: 'practice-conversation', title: '排序', conditions: {} }
const fixtureAction = () => ({ id: 'practice-action', type: 'PRACTICE_CREATE', status: 'PENDING', title: '排序专项练习', count: 5, requestedCount: 5,
  requiresConfirmation: true, result: {} as any, targets: [{ title: '排序审核题目', resource: { type: 'question', id: 101 } }] })
const fixtureResult = (action: any) => ({ outcome: 'COMPLETED', explanationMode: 'rules', answer: '排序专项练习 · 5 题。点击“开始练习”，即可进入刷题页面作答。', references: [], actions: [action],
  evidence: [{ ref: 'Q1', title: '排序证据', summary: '仅预览，不含答案', resource: { type: 'question', id: 101 } }] })

async function setup(page: Page, result: any, options: { empty?: boolean; confirm?: (route: any) => Promise<void> } = {}) {
  let confirmations = 0, sent = ''
  const messages: any[] = options.empty ? [] : [{ id: 'm1', sequenceNo: 1, content: '给我出几道有关排序的题', attempts: [{ taskId: 't1', status: 'SUCCESS', version: 1, result }] }]
  await page.addInitScript(u => { localStorage.setItem('token', 'practice-token'); localStorage.setItem('userInfo', JSON.stringify(u)) }, user)
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    let data: any = { list: [], total: 0 }
    if (route.request().headers().authorization === 'Bearer new-account-token') {
      if (path.endsWith('/users/me')) data = { id: 2, username: 'new-account', role: 'STUDENT', status: 1 }
      return route.fulfill({ json: { code: 0, message: 'ok', data } })
    }
    if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/privacy/settings')) data = { modelAllowed: false, scopes: [], version: 1 }
    else if (path === '/api/conversations') data = { list: [conversation], total: 1 }
    else if (path.endsWith('/messages')) {
      if (method === 'POST') {
        sent = route.request().postDataJSON().query
        messages.push({ id: 'm1', sequenceNo: 1, content: sent, attempts: [{ taskId: 't1', status: 'RUNNING', version: 0, draft: {} }] })
        data = { taskId: 't1', messageId: 'm1' }
      } else data = { conversation, list: messages, total: messages.length }
    } else if (path.endsWith('/stream')) {
      messages[0].attempts[0] = { taskId: 't1', status: 'SUCCESS', version: 1, result }
      return route.fulfill({ contentType: 'text/event-stream', body: 'event: completed\ndata: ' + JSON.stringify(messages[0].attempts[0]) + '\n\n' })
    } else if (path.endsWith('/confirm')) {
      confirmations++
      if (options.confirm) return options.confirm(route)
      await new Promise(resolve => setTimeout(resolve, 60))
      Object.assign(result.actions[0], { status: 'SUCCESS', requiresConfirmation: false, result: { sessionId: 'L-practice-one', actualCount: 5 } })
      data = result.actions[0]
    } else if (path.endsWith('/state')) data = { sessionId: 'L-practice-one', kind: 'PRACTICE', state: 'RUNNING', revision: 0, currentIndex: 0, blueprint: { missing: [] },
      items: [{ itemId: 1, questionId: 101, subject: '数据结构', knowledgePoint: '排序', difficulty: 'EASY', content: '排序审核题目', optionA: '甲', optionB: '乙', submitted: false }] }
    else if (path.endsWith('/enabled')) data = { enabled: true }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  return { confirmations: () => confirmations, sent: () => sent }
}

test('original request produces compact card; one click opens a reusable practice session', async ({ page }) => {
  const action = fixtureAction(), result = fixtureResult(action), state = await setup(page, result, { empty: true })
  await page.goto('/tasks')
  await page.getByRole('textbox', { name: '聊天输入' }).fill('给我出几道有关排序的题')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  const card = page.locator('.action-card')
  await expect(card).toContainText('排序专项练习')
  await expect(card.getByText('排序审核题目')).not.toBeVisible()
  await expect(page.getByText('仅预览，不含答案')).not.toBeVisible()
  expect(state.confirmations()).toBe(0)
  const start = card.getByRole('button', { name: '开始练习', exact: true })
  await start.evaluate(element => { (element as HTMLButtonElement).click(); (element as HTMLButtonElement).click() })
  await expect(page).toHaveURL(/\/practice\/session\/L-practice-one$/)
  await expect(page.getByRole('radio', { name: 'A. 甲' })).toBeEnabled()
  expect(state.sent()).toBe('给我出几道有关排序的题'); expect(state.confirmations()).toBe(1)
  await page.goto('/tasks?conversationId=practice-conversation')
  await expect(page.getByRole('link', { name: '继续练习（5题）' })).toHaveAttribute('href', '/practice/session/L-practice-one')
  await page.reload()
  await page.getByRole('link', { name: '继续练习（5题）' }).click()
  await expect(page).toHaveURL(/L-practice-one$/)
  expect(state.confirmations()).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('conflict preserves preview and asks for a fresh request without navigating', async ({ page }) => {
  await setup(page, fixtureResult(fixtureAction()), { confirm: route => route.fulfill({ status: 409, json: { code: 409, message: '目标已变化' } }) })
  await page.goto('/tasks')
  await page.getByRole('button', { name: '开始练习', exact: true }).click()
  await expect(page.locator('.action-card [role=alert]')).toContainText('重新发送组题请求')
  await expect(page.getByRole('button', { name: '开始练习', exact: true })).toBeDisabled()
  expect(new URL(page.url()).pathname).toBe('/tasks')
})

test('late confirmation after account switch does not navigate or change the new account', async ({ page }) => {
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  const action = fixtureAction()
  const state = await setup(page, fixtureResult(action), { confirm: async route => {
    await pending
    await route.fulfill({ json: { code: 0, data: { ...action, status: 'SUCCESS', result: { sessionId: 'L-old-account' } } } }).catch(() => {})
  } })
  await page.goto('/tasks')
  await page.getByRole('button', { name: '开始练习', exact: true }).click()
  await expect.poll(state.confirmations).toBe(1)
  await page.evaluate(() => {
    const store = (document.querySelector('#app') as any).__vue_app__.config.globalProperties.$pinia._s.get('user')
    store.token = 'new-account-token'; store.setUserInfo({ id: 2, username: 'new-account', role: 'STUDENT' })
  })
  release()
  await expect(page.locator('.uname')).toHaveText('new-account')
  await expect(page.locator('.action-card')).toHaveCount(0)
  expect(new URL(page.url()).pathname).toBe('/tasks')
})

test('old messages link all nine destinations; code, existing links and hostile URLs stay safe', async ({ page }) => {
  const labels = ['首页', '刷题', 'Agent 助手', '个人笔记', '错题本', '我的收藏', '学习统计', '院校库', '备考资料']
  const paths = ['/', '/practice', '/tasks', '/notes', '/wrong', '/favorite', '/stat', '/schools', '/documents']
  const result = { outcome: 'COMPLETED', explanationMode: 'rules', answer: labels.join('、') + '\n`错题本`\n```\n学习统计\n```\n[已批准来源](https://example.org/ref)\n[危险](javascript:alert(1))\n[外部](https://evil.invalid)\n[任意站内](/unregistered)\n管理后台',
    references: [{ id: 's1', title: '来源', url: 'https://example.org/ref' }], navigation: [{ target: 'https://evil.invalid' }, { target: 'ADMIN_DOCUMENTS' }] }
  await setup(page, result)
  await page.goto('/tasks')
  const markdown = page.locator('.task-result .markdown'), nav = page.getByRole('navigation', { name: '相关功能入口' })
  for (let i = 0; i < labels.length; i++) {
    await expect(markdown.getByRole('link', { name: labels[i], exact: true })).toHaveAttribute('href', paths[i])
    await expect(nav.getByRole('link', { name: '前往' + labels[i], exact: true })).toHaveAttribute('href', paths[i])
  }
  await expect(markdown.locator('code a')).toHaveCount(0)
  await expect(markdown.locator('a[href="https://example.org/ref"]')).toHaveAttribute('target', '_blank')
  await expect(markdown.locator('a[href*="evil"], a[href^="javascript"], a[href="/unregistered"], a[href^="/admin"]')).toHaveCount(0)
  await expect(nav.getByRole('link', { name: '前往管理后台' })).toHaveCount(0)
  await markdown.getByRole('link', { name: '错题本', exact: true }).click()
  await expect(page).toHaveURL(/\/wrong$/)
})

test('unready retrieval offers no start button and still links the practice page', async ({ page }) => {
  await setup(page, { outcome: 'UNSUPPORTED', explanationMode: 'rules', answer: '题目索引正在准备，可稍后重试或前往刷题页面。', retrievalStatus: 'BUILDING', references: [] })
  await page.goto('/tasks')
  await expect(page.locator('.task-result')).toContainText('索引正在准备')
  await expect(page.getByRole('button', { name: '开始练习', exact: true })).toHaveCount(0)
  await expect(page.getByRole('navigation', { name: '相关功能入口' }).getByRole('link', { name: '前往刷题' })).toHaveAttribute('href', '/practice')
})

for (const hasAction of [false, true]) test(`partial compound result only offers retry without existing actions: actions=${hasAction}`, async ({ page }) => {
  await setup(page, { outcome: 'COMPLETED', explanationMode: 'rules', answer: '知识解释已保留，题目索引正在准备。',
    partial: true, retrievalStatus: 'BUILDING', references: [], actions: hasAction ? [fixtureAction()] : [],
    sections: [{ agent: 'KNOWLEDGE', outcome: 'COMPLETED', explanationMode: 'rules' },
      { agent: 'PRACTICE', outcome: 'UNSUPPORTED', explanationMode: 'rules', notice: '题目检索尚未就绪' }] })
  await page.goto('/tasks')
  await expect(page.getByRole('region', { name: '分项处理结果' })).toContainText('知识辅导 · 已完成')
  await expect(page.getByRole('button', { name: '重试此问题', exact: true })).toHaveCount(hasAction ? 0 : 1)
})

test('transport failure can retry and reuse the server-created session', async ({ page }) => {
  const action = fixtureAction()
  let calls = 0
  await setup(page, fixtureResult(action), { confirm: async route => {
    calls++
    if (calls === 1) return route.abort('failed')
    return route.fulfill({ json: { code: 0, data: { ...action, status: 'SUCCESS', result: { sessionId: 'L-recovered-session', actualCount: 5 } } } })
  } })
  await page.goto('/tasks')
  await page.getByRole('button', { name: '开始练习', exact: true }).click()
  await expect(page.locator('.action-card [role=alert]')).toContainText('请重试')
  await page.getByRole('button', { name: '开始练习', exact: true }).click()
  await expect(page).toHaveURL(/L-recovered-session$/)
  expect(calls).toBe(2)
})

test('admin destinations follow current role; draft preview does not acquire navigation links', async ({ page }) => {
  await setup(page, { outcome: 'COMPLETED', explanationMode: 'rules', answer: '管理后台与题目录入与审核。个人笔记建议如下。', references: [],
    documentProposal: { operation: 'create', title: '导航文字草稿', content: '错题本 学习统计 首页' } })
  await page.goto('/tasks')
  await expect(page.locator('.task-result a[href^="/admin"]')).toHaveCount(0)
  await page.evaluate(() => {
    const store = (document.querySelector('#app') as any).__vue_app__.config.globalProperties.$pinia._s.get('user')
    store.setUserInfo({ id: 1, username: 'practice-navigation', role: 'ADMIN', status: 1 })
  })
  await expect(page.locator('.task-result .markdown a[href^="/admin"]')).toHaveCount(2)
  await page.getByRole('button', { name: '预览笔记建议' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.locator('.markdown')).toContainText('错题本 学习统计 首页')
  await expect(dialog.locator('.markdown a')).toHaveCount(0)
})
