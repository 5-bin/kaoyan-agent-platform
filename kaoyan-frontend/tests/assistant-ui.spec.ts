import { test, expect } from '@playwright/test'

const user = { id: 1, username: 'ui-browser', role: 'STUDENT', status: 1 }
const releaseId = 'rag-v1-internal-release'
const source = { id: 'source-one', title: '官方招生目录', url: 'https://gs.nau.edu.cn/', locator: '计算机学院招生目录', version: 'admissions-2027-v1', retrievedAt: '2026-10-23', excerpt: '招生资料原文摘要' }
const result = { outcome: 'COMPLETED', answer: '这是保留的回答正文。', explanationMode: 'ai', releaseId, references: [source] }
const conversations = [
  { id: 'short', title: '短标题', conditions: {} },
  { id: 'long', title: '请给出清华大学2027年计算机专业的招生信息，并帮助我整理接下来的复习计划和需要核对的资料', conditions: {} },
  { id: 'unbroken', title: 'LongUnbrokenConversationTitle'.repeat(5), conditions: {} },
  ...Array.from({ length: 15 }, (_, index) => ({ id: `other-${index}`, title: `其他会话 ${index}`, conditions: {} }))
]

test.beforeEach(async ({ page }) => {
  await page.addInitScript(value => { localStorage.setItem('token', 'ui-test-token'); localStorage.setItem('userInfo', JSON.stringify(value)) }, user)
})

test('conversation rows stay equal, truncate titles and preserve accessible selection', async ({ page }, info) => {
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    const current = conversations.find(item => path.includes(`/conversations/${item.id}/`)) || conversations[0]
    const data = path.endsWith('/users/me') ? user : path === '/api/conversations' ? { list: conversations, total: conversations.length }
      : path.endsWith('/messages') ? { conversation: current, list: [], total: 0 } : { list: [], total: 0 }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/tasks?conversationId=short')
  const mobile = info.project.name === 'mobile'
  if (mobile) await page.getByRole('button', { name: '会话', exact: true }).click()
  const list = mobile ? page.getByRole('dialog', { name: '会话', exact: true }) : page.locator('.conversation-list')
  const rows = list.locator('.conversation')
  await expect(rows).toHaveCount(conversations.length)
  const dimensions = await rows.evaluateAll(nodes => nodes.map(node => {
    const style = getComputedStyle(node), rect = node.getBoundingClientRect()
    return { width: rect.width, height: rect.height, whiteSpace: style.whiteSpace, overflow: style.overflow, ellipsis: style.textOverflow }
  }))
  for (const row of dimensions) expect(row).toEqual({ width: dimensions[0]!.width, height: 44, whiteSpace: 'nowrap', overflow: 'hidden', ellipsis: 'ellipsis' })
  for (const item of conversations.slice(0, 3)) {
    const button = list.getByRole('button', { name: item.title, exact: true })
    await expect(button).toHaveAttribute('title', item.title)
  }
  const long = list.getByRole('button', { name: conversations[1]!.title, exact: true })
  expect(await long.evaluate(node => node.scrollWidth > node.clientWidth)).toBe(true)
  await long.click()
  await expect(page).toHaveURL(/conversationId=long/)
  if (mobile) await page.getByRole('button', { name: '会话', exact: true }).click()
  await expect(list.getByRole('button', { name: conversations[1]!.title, exact: true })).toHaveClass(/active/)
  await expect(list.getByRole('button', { name: conversations[1]!.title, exact: true })).toHaveAttribute('aria-current', 'true')
  await expect(list.getByRole('button', { name: conversations[1]!.title, exact: true })).toBeInViewport()
  await expect(list.getByRole('button', { name: '短标题', exact: true })).not.toHaveClass(/active/)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false)
  await page.screenshot({ path: info.outputPath('conversation-titles.png'), fullPage: true, animations: 'disabled' })
})

test('chat and saved history hide internal metadata while retaining attempts and sources', async ({ page }, info) => {
  const attempts = [
    { taskId: 'internal-failed-id', attemptNo: 1, status: 'FAILED', version: 1, errorMessage: '本次生成失败，请重试' },
    { taskId: 'internal-cancelled-id', attemptNo: 2, status: 'CANCELLED', version: 2 },
    { taskId: 'internal-success-id', attemptNo: 3, status: 'SUCCESS', version: 3, result }
  ]
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    const data = path.endsWith('/users/me') ? user : path === '/api/conversations' ? { list: [conversations[0]], total: 1 }
      : path.endsWith('/messages') ? { conversation: conversations[0], total: 1, list: [{ id: 'message-one', sequenceNo: 1, content: '请查询资料', attempts }] }
      : path === '/api/tasks' ? { list: [{ id: 'internal-success-id', taskType: 'CHAT', status: 'SUCCESS', createdAt: '2026-10-23', releaseId, resultPayload: result }], total: 1 }
      : { list: [], total: 0 }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/tasks?conversationId=short')
  await expect(page.locator('.assistant-message')).toHaveCount(3)
  await expect(page.getByText('本次生成失败，请重试', { exact: true })).toBeVisible()
  await expect(page.getByText('已停止生成', { exact: true })).toBeVisible()
  const messages = page.locator('.messages')
  await expect(messages.getByText(result.answer, { exact: true })).toBeVisible()
  await expect(messages.getByRole('link', { name: source.title })).toHaveAttribute('href', source.url)
  await expect(messages).toContainText(source.version)
  await expect(messages).toContainText(source.locator)
  await expect(messages).not.toContainText(/尝试\s*\d|任务编号|rag-v1-|已完成|AI解释|规则 \/ 来源摘要|internal-.*-id/)
  await expect(messages.locator('.meta')).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('simplified-results.png'), fullPage: true, animations: 'disabled' })
  await page.goto('/tasks/history')
  await page.getByRole('button', { name: '查看', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '历史结果' })
  await expect(dialog).toContainText(result.answer)
  await expect(dialog).toContainText(source.version)
  await expect(dialog).not.toContainText(/任务编号|rag-v1-|已完成|AI解释|internal-success-id/)
})

for (const scenario of [
  { outcome: 'NEEDS_INPUT', explanationMode: 'rules', label: '需补充条件' },
  { outcome: 'UNSUPPORTED', explanationMode: 'rules', label: '资料未覆盖' },
  { outcome: 'COMPLETED', explanationMode: 'fallback', label: 'AI解释暂不可用，已保留资料与规则结果。' }
]) {
  test(`retain necessary outcome and fallback notice: ${scenario.outcome}/${scenario.explanationMode}`, async ({ page }) => {
    await page.route('http://127.0.0.1:4173/api/**', async route => {
      const path = new URL(route.request().url()).pathname
      const data = path.endsWith('/users/me') ? user : path === '/api/conversations' ? { list: [conversations[0]], total: 1 }
        : path.endsWith('/messages') ? { conversation: conversations[0], total: 1, list: [{ id: 'message-one', sequenceNo: 1, content: '查询', attempts: [{ taskId: 'task-one', attemptNo: 1, status: 'SUCCESS', version: 1, result: { ...result, ...scenario } }] }] }
        : { list: [], total: 0 }
      await route.fulfill({ json: { code: 0, message: 'ok', data } })
    })
    await page.goto('/tasks?conversationId=short')
    await expect(page.getByText(scenario.label, { exact: true })).toBeVisible()
    await expect(page.locator('.task-result')).not.toContainText(releaseId)
  })
}
