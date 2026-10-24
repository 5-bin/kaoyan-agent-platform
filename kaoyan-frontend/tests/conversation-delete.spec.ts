import { test, expect, type Page, type Route } from '@playwright/test'
const user = { id: 1, username: 'delete-browser', role: 'STUDENT', status: 1 }
const make = (id: string) => ({ id, title: `对话 ${id}`, conditions: {} })
const ok = (route: Route, data: unknown) => route.fulfill({ json: { code: 0, message: 'ok', data } })
async function setup(page: Page, options: { ids?: string[]; fail?: boolean; running?: boolean } = {}) {
  let items = (options.ids || ['a', 'b']).map(make), deletes = 0, creates = 0
  let release: (() => void) | undefined, hold = false
  await page.addInitScript(value => { localStorage.setItem('token', 'delete-token'); localStorage.setItem('userInfo', JSON.stringify(value)) }, user)
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method()
    if (method === 'DELETE') {
      deletes++
      if (hold) await new Promise<void>(resolve => { release = resolve })
      if (options.fail) return route.fulfill({ status: 500, json: { message: '删除失败，请重试' } })
      items = items.filter(item => !path.endsWith('/' + item.id)); return ok(route, null)
    }
    if (path === '/api/conversations' && method === 'POST') { creates++; const item = make('new'); items.unshift(item); return ok(route, item) }
    if (path === '/api/conversations') {
      const num = Number(url.searchParams.get('pageNum') || 1), size = Number(url.searchParams.get('pageSize') || 20)
      return ok(route, { list: items.slice((num - 1) * size, num * size), total: items.length })
    }
    if (path.endsWith('/messages') && method === 'GET') {
      const id = path.split('/')[3]!, running = options.running && id === 'a'
      return ok(route, { conversation: make(id), list: running ? [{ id: 'msg', content: '正在处理的问题', attempts: [{ taskId: 'running', attemptNo: 1, status: 'RUNNING', version: 1 }] }] : [], total: running ? 1 : 0 })
    }
    if (path.endsWith('/stream')) return route.fulfill({ contentType: 'text/event-stream', body: '' })
    return ok(route, path.endsWith('/users/me') ? user : { list: [], total: 0 })
  })
  await page.goto('/tasks?conversationId=a')
  await expect(page.locator('.chat-heading h2')).toHaveText('考研助手')
  return { get deletes() { return deletes }, get creates() { return creates }, hold() { hold = true }, release() { release?.() } }
}
async function list(page: Page) {
  if (test.info().project.name === 'mobile') {
    const drawer = page.getByRole('dialog', { name: '会话', exact: true })
    if (!await drawer.isVisible()) await page.getByRole('button', { name: '会话', exact: true }).click()
    return drawer
  }
  return page.locator('.conversation-list')
}
async function askDelete(page: Page, id: string) {
  const dialog = page.getByRole('dialog', { name: '删除对话', exact: true })
  // A completed DELETE can update the list before the previous dialog's leave
  // transition removes it. Wait for teardown before opening another dialog.
  await expect(dialog).toHaveCount(0)
  const button = (await list(page)).getByRole('button', { name: `删除对话：对话 ${id}`, exact: true })
  await button.scrollIntoViewIfNeeded(); await expect(button).toBeInViewport(); await button.focus(); await page.keyboard.press('Enter')
  await expect(dialog).toHaveCount(1)
  await expect(dialog).toBeVisible()
  return dialog
}
const input = (page: Page) => page.getByRole('textbox', { name: '聊天输入', exact: true })

test('cancel and failure preserve selection and draft', async ({ page }) => {
  const state = await setup(page, { fail: true }); await input(page).fill('保留草稿')
  let dialog = await askDelete(page, 'b')
  await expect(dialog).toContainText('已保存的个人笔记不受影响')
  await dialog.getByRole('button', { name: '取消', exact: true }).click(); await expect(dialog).toHaveCount(0); expect(state.deletes).toBe(0)
  dialog = await askDelete(page, 'b'); await dialog.getByRole('button', { name: '删除', exact: true }).click()
  await expect(page.getByText('删除失败，请重试', { exact: true })).toBeVisible()
  await expect((await list(page)).getByRole('button', { name: '对话 b', exact: true })).toBeVisible()
  await expect(page).toHaveURL(/conversationId=a/)
  if (test.info().project.name === 'mobile') await page.keyboard.press('Escape')
  await expect(input(page)).toHaveValue('保留草稿')
})
test('delete other once and retain draft and persisted list', async ({ page }) => {
  const state = await setup(page); await input(page).fill('保留草稿'); state.hold()
  const dialog = await askDelete(page, 'b'); await dialog.getByRole('button', { name: '删除', exact: true }).click()
  const rows = await list(page)
  await expect(rows.getByRole('button', { name: '删除对话：对话 b', exact: true })).toBeDisabled()
  await expect.poll(() => state.deletes).toBe(1); state.release()
  await expect(rows.getByRole('button', { name: '对话 b', exact: true })).toHaveCount(0)
  await expect(page).toHaveURL(/conversationId=a/)
  if (test.info().project.name === 'mobile') await page.keyboard.press('Escape')
  await expect(input(page)).toHaveValue('保留草稿'); await page.reload()
  await expect((await list(page)).getByRole('button', { name: '对话 b', exact: true })).toHaveCount(0)
})
test('delete running current then last and send into a new conversation', async ({ page }) => {
  const state = await setup(page, { running: true })
  await expect(page.getByRole('button', { name: '停止生成', exact: true })).toBeVisible(); await input(page).fill('应清除的草稿')
  let dialog = await askDelete(page, 'a'); await dialog.getByRole('button', { name: '删除', exact: true }).click()
  await expect(page).toHaveURL(/conversationId=b/)
  if (test.info().project.name === 'mobile') await expect(page.getByRole('dialog', { name: '会话', exact: true })).toBeHidden()
  await expect(page.getByRole('button', { name: '停止生成', exact: true })).toHaveCount(0); await expect(input(page)).toHaveValue('')
  dialog = await askDelete(page, 'b'); await dialog.getByRole('button', { name: '删除', exact: true }).click()
  await expect(page).toHaveURL(/\/tasks$/); expect(state.creates).toBe(0)
  await expect(page.getByText('可以询问408知识、咨询择校，或创建和修改学习笔记')).toBeVisible()
  await input(page).fill('新的问题'); await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page).toHaveURL(/conversationId=new/); expect(state.creates).toBe(1)
})
test('deletion resets pagination without skipping rows', async ({ page }) => {
  await setup(page, { ids: ['a', ...Array.from({ length: 10 }, (_, i) => String(i))] })
  let rows = await list(page); await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect(rows.locator('.conversation')).toHaveCount(10)
  const dialog = await askDelete(page, '0'); await dialog.getByRole('button', { name: '删除', exact: true }).click()
  rows = await list(page); await expect(rows.locator('.conversation')).toHaveCount(5)
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect(rows.locator('.conversation')).toHaveCount(10)
  await expect(rows.getByRole('button', { name: '对话 9', exact: true })).toHaveCount(1)
  await expect(rows.getByRole('button', { name: '展开更多', exact: true })).toHaveCount(0)
})

test('late pagination cannot restore deleted rows', async ({ page }) => {
  await setup(page, { ids: ['a', ...Array.from({ length: 10 }, (_, i) => String(i))] })
  let resume!: () => void
  const late = new Promise<void>(resolve => { resume = resolve })
  let started = false
  await page.route('http://127.0.0.1:4173/api/conversations?*', async route => {
    if (new URL(route.request().url()).searchParams.get('pageNum') !== '2') return route.fallback()
    started = true; await late
    await ok(route, { list: [make('0'), make('stale')], total: 99 })
  })
  let rows = await list(page); await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect.poll(() => started).toBe(true)
  const dialog = await askDelete(page, '0'); await dialog.getByRole('button', { name: '删除', exact: true }).click()
  rows = await list(page); await expect(rows.getByRole('button', { name: '对话 0', exact: true })).toHaveCount(0)
  const response = page.waitForResponse(r => r.url().includes('pageNum=2'))
  resume(); await response
  await expect(rows.locator('.conversation')).toHaveCount(5)
  await expect(rows.getByRole('button', { name: '对话 stale', exact: true })).toHaveCount(0)
})

test('account switch ignores pending deletion response', async ({ page }) => {
  const state = await setup(page); state.hold()
  const dialog = await askDelete(page, 'a'); await dialog.getByRole('button', { name: '删除', exact: true }).click()
  await expect.poll(() => state.deletes).toBe(1)
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    if (route.request().headers().authorization !== 'Bearer new-account-token') return route.fallback()
    const path = new URL(route.request().url()).pathname
    return ok(route, path.endsWith('/users/me') ? { ...user, id: 2 } : path === '/api/conversations' ? { list: [make('new-owner')], total: 1 }
      : path.endsWith('/messages') ? { conversation: make('new-owner'), list: [], total: 0 } : { list: [], total: 0 })
  })
  await page.evaluate(() => {
    const store = (document.querySelector('#app') as any).__vue_app__.config.globalProperties.$pinia._s.get('user')
    store.token = 'new-account-token'; store.setUserInfo({ id: 2, username: 'new-account', role: 'STUDENT' })
    localStorage.setItem('token', 'new-account-token')
  })
  await expect(page).toHaveURL(/conversationId=new-owner/)
  await input(page).fill('新账号的输入')
  const response = page.waitForResponse(r => r.request().method() === 'DELETE')
  state.release(); await response
  await expect(page).toHaveURL(/conversationId=new-owner/)
  await expect(input(page)).toHaveValue('新账号的输入')
  await expect((await list(page)).getByRole('button', { name: '对话 new-owner', exact: true })).toBeVisible()
})

test('late messages cannot repopulate a deleted conversation', async ({ page }) => {
  await setup(page)
  let resume!: () => void, started = false
  const late = new Promise<void>(resolve => { resume = resolve })
  await page.route('http://127.0.0.1:4173/api/conversations/b/messages?*', async route => {
    started = true; await late
    await ok(route, { conversation: make('b'), list: [{ id: 'late', content: '已删除会话的迟到消息', attempts: [] }], total: 1 })
  })
  await (await list(page)).getByRole('button', { name: '对话 b', exact: true }).click()
  await expect.poll(() => started).toBe(true)
  if (test.info().project.name === 'mobile') await expect(page.getByRole('dialog', { name: '会话', exact: true })).toBeHidden()
  const dialog = await askDelete(page, 'b'); await dialog.getByRole('button', { name: '删除', exact: true }).click()
  await expect(page).toHaveURL(/conversationId=a/)
  const response = page.waitForResponse(r => r.url().includes('/b/messages'))
  resume(); await response
  await expect(page.locator('.messages')).not.toContainText('已删除会话的迟到消息')
  await expect(page).toHaveURL(/conversationId=a/)
})

for (const count of [0, 5, 6, 12]) {
  test(`expand conversations in batches of five: ${count} total`, async ({ page }) => {
    await setup(page, { ids: Array.from({ length: count }, (_, i) => i === 0 ? 'a' : String(i)) })
    const rows = await list(page), more = rows.getByRole('button', { name: '展开更多', exact: true })
    await expect(rows.locator('.conversation')).toHaveCount(Math.min(5, count))
    for (let visible = 5; visible < count; visible += 5) {
      await expect(more).toBeVisible(); await more.click()
      await expect(rows.locator('.conversation')).toHaveCount(Math.min(visible + 5, count))
    }
    await expect(more).toHaveCount(0)
    const titles = await rows.locator('.conversation').allTextContents()
    expect(new Set(titles).size).toBe(count)
  })
}

test('pending expansion blocks repeated clicks and failure retries the same page', async ({ page }) => {
  await setup(page, { ids: ['a', ...Array.from({ length: 7 }, (_, i) => String(i))] })
  const rows = await list(page), more = rows.getByRole('button', { name: '展开更多', exact: true })
  let requests = 0, resume!: () => void
  const held = new Promise<void>(resolve => { resume = resolve })
  await page.route('http://127.0.0.1:4173/api/conversations?*', async route => {
    const url = new URL(route.request().url())
    if (url.searchParams.get('pageNum') !== '2') return route.fallback()
    expect(url.searchParams.get('pageSize')).toBe('5')
    requests++
    if (requests === 1) {
      await held
      return route.fulfill({ status: 500, json: { message: '会话加载失败，请重试' } })
    }
    return route.fallback()
  })
  await more.click(); await expect.poll(() => requests).toBe(1)
  await expect(more).toBeDisabled()
  await more.evaluate((button: HTMLButtonElement) => { button.click(); button.click() })
  expect(requests).toBe(1)
  resume()
  await expect(page.getByText('会话加载失败，请重试', { exact: true })).toBeVisible()
  await expect(rows.locator('.conversation')).toHaveCount(5)
  await expect(more).toBeEnabled(); await more.click()
  await expect(rows.locator('.conversation')).toHaveCount(8)
  expect(requests).toBe(2)
  await expect(more).toHaveCount(0)
})

async function switchChat(page: Page, id: string) {
  await (await list(page)).getByRole('button', { name: `对话 ${id}`, exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`conversationId=${id}(?:&|$)`))
  if (test.info().project.name === 'mobile') await expect(page.getByRole('dialog', { name: '会话', exact: true })).toBeHidden()
}

test('switching retains expanded pages while creating and reloading reset them', async ({ page }) => {
  await setup(page, { ids: ['a', ...Array.from({ length: 11 }, (_, i) => String(i))] })
  let rows = await list(page)
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect(rows.locator('.conversation')).toHaveCount(10)
  await switchChat(page, '5')
  rows = await list(page); await expect(rows.locator('.conversation')).toHaveCount(10)
  await expect(rows.getByRole('button', { name: '对话 5', exact: true })).toHaveAttribute('aria-current', 'true')
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect(rows.locator('.conversation')).toHaveCount(12)
  await switchChat(page, '10')
  rows = await list(page); await expect(rows.locator('.conversation')).toHaveCount(12)
  expect(new Set(await rows.locator('.conversation').allTextContents()).size).toBe(12)
  await expect(rows.getByRole('button', { name: '展开更多', exact: true })).toHaveCount(0)
  await page.reload()
  rows = await list(page); await expect(rows.locator('.conversation')).toHaveCount(5)
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect(rows.locator('.conversation')).toHaveCount(10)
  await rows.getByRole('button', { name: '新建会话', exact: true }).click()
  await expect(page).toHaveURL(/conversationId=new/)
  if (test.info().project.name === 'mobile') await expect(page.getByRole('dialog', { name: '会话', exact: true })).toBeHidden()
  rows = await list(page); await expect(rows.locator('.conversation')).toHaveCount(5)
  await expect(rows.getByRole('button', { name: '对话 new', exact: true })).toBeVisible()
})

test('switching keeps list scroll position', async ({ page }) => {
  await page.setViewportSize({ width: test.info().project.name === 'mobile' ? 390 : 1280, height: 600 })
  await setup(page, { ids: ['a', ...Array.from({ length: 11 }, (_, i) => String(i))] })
  let rows = await list(page)
  for (const count of [10, 12]) {
    await rows.getByRole('button', { name: '展开更多', exact: true }).click()
    await expect(rows.locator('.conversation')).toHaveCount(count)
  }
  const scroller = () => test.info().project.name === 'mobile' ? rows.locator('.el-drawer__body') : rows
  await rows.getByRole('button', { name: '对话 8', exact: true }).scrollIntoViewIfNeeded()
  const before = await scroller().evaluate(node => node.scrollTop)
  expect(before).toBeGreaterThan(0)
  await switchChat(page, '8'); rows = await list(page)
  await expect.poll(() => scroller().evaluate(node => node.scrollTop)).toBe(before)
  await expect(rows.locator('.conversation')).toHaveCount(12)
})

test('pending pagination survives switching and continues from the next page', async ({ page }) => {
  await setup(page, { ids: ['a', ...Array.from({ length: 11 }, (_, i) => String(i))] })
  let resume!: () => void, started = false
  const held = new Promise<void>(resolve => { resume = resolve })
  await page.route('http://127.0.0.1:4173/api/conversations?*', async route => {
    if (new URL(route.request().url()).searchParams.get('pageNum') !== '2') return route.fallback()
    started = true; await held; return route.fallback()
  })
  let rows = await list(page)
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect.poll(() => started).toBe(true)
  await switchChat(page, '2'); rows = await list(page)
  await expect(rows.getByRole('button', { name: '展开更多', exact: true })).toBeDisabled()
  resume()
  await expect(rows.locator('.conversation')).toHaveCount(10)
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect(rows.locator('.conversation')).toHaveCount(12)
  expect(new Set(await rows.locator('.conversation').allTextContents()).size).toBe(12)
})

test('rapid switching ignores old messages without reloading the expanded list', async ({ page }) => {
  await setup(page, { ids: ['a', ...Array.from({ length: 11 }, (_, i) => String(i))] })
  const rows = await list(page)
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect(rows.locator('.conversation')).toHaveCount(10)
  let resume!: () => void, started = false, listRequests = 0
  const held = new Promise<void>(resolve => { resume = resolve })
  page.on('request', request => { if (new URL(request.url()).pathname === '/api/conversations') listRequests++ })
  await page.route('http://127.0.0.1:4173/api/conversations/5/messages?*', async route => {
    started = true; await held
    return ok(route, { conversation: make('5'), list: [{ id: 'late', content: '旧会话迟到消息', attempts: [] }], total: 1 })
  })
  await switchChat(page, '5'); await expect.poll(() => started).toBe(true)
  await switchChat(page, '6')
  const response = page.waitForResponse(r => r.url().includes('/5/messages'))
  resume(); await response
  const currentRows = await list(page)
  await expect(currentRows.locator('.conversation')).toHaveCount(10)
  await expect(currentRows.getByRole('button', { name: '对话 6', exact: true })).toHaveAttribute('aria-current', 'true')
  await expect(page.locator('.messages')).not.toContainText('旧会话迟到消息')
  expect(listRequests).toBe(0)
})

test('generation refresh retains expanded pages even when switching during refresh', async ({ page }) => {
  await setup(page, { ids: ['a', ...Array.from({ length: 11 }, (_, i) => String(i))] })
  let rows = await list(page)
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect(rows.locator('.conversation')).toHaveCount(10)
  let finish!: () => void, resume!: () => void, started = false, streamStarted = false
  const streamHeld = new Promise<void>(resolve => { finish = resolve })
  const refreshHeld = new Promise<void>(resolve => { resume = resolve })
  await page.route('http://127.0.0.1:4173/api/conversations/5/messages?*', route => ok(route, {
    conversation: make('5'), list: [{ id: 'msg', content: '测试生成', attempts: [{ taskId: 'refresh', status: 'RUNNING', version: 1 }] }], total: 1
  }))
  await page.route('http://127.0.0.1:4173/api/conversations/5/generations/refresh/stream', async route => {
    streamStarted = true; await streamHeld
    return route.fulfill({ contentType: 'text/event-stream', body: 'event: completed\ndata: ' + JSON.stringify({ taskId: 'refresh', status: 'SUCCESS', version: 2, result: { outcome: 'COMPLETED', answer: '生成完成' } }) + '\n\n' })
  })
  await page.route('http://127.0.0.1:4173/api/conversations?*', async route => {
    if (new URL(route.request().url()).searchParams.get('pageNum') !== '2') return route.fallback()
    started = true; await refreshHeld; return route.fallback()
  })
  await switchChat(page, '5'); await expect.poll(() => streamStarted).toBe(true)
  finish(); await expect.poll(() => started).toBe(true)
  rows = await list(page)
  await expect(rows.locator('.conversation')).toHaveCount(10)
  await switchChat(page, '6'); resume()
  rows = await list(page)
  await expect(rows.getByRole('button', { name: '展开更多', exact: true })).toBeEnabled()
  await expect(rows.locator('.conversation')).toHaveCount(10)
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect(rows.locator('.conversation')).toHaveCount(12)
})

test('account switch discards expanded pages and pending pagination', async ({ page }) => {
  await setup(page, { ids: ['a', ...Array.from({ length: 11 }, (_, i) => String(i))] })
  let rows = await list(page)
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect(rows.locator('.conversation')).toHaveCount(10)
  let resume!: () => void, started = false
  const held = new Promise<void>(resolve => { resume = resolve })
  await page.route('http://127.0.0.1:4173/api/conversations?*', async route => {
    if (new URL(route.request().url()).searchParams.get('pageNum') !== '3') return route.fallback()
    started = true; await held; return ok(route, { list: [make('stale')], total: 11 })
  })
  await rows.getByRole('button', { name: '展开更多', exact: true }).click()
  await expect.poll(() => started).toBe(true)
  await page.route('http://127.0.0.1:4173/api/**', route => {
    if (route.request().headers().authorization !== 'Bearer new-account-token') return route.fallback()
    const path = new URL(route.request().url()).pathname
    return ok(route, path.endsWith('/users/me') ? { ...user, id: 2 } : path === '/api/conversations' ? { list: [make('new-owner')], total: 1 }
      : path.endsWith('/messages') ? { conversation: make('new-owner'), list: [], total: 0 } : { list: [], total: 0 })
  })
  await page.evaluate(() => {
    const store = (document.querySelector('#app') as any).__vue_app__.config.globalProperties.$pinia._s.get('user')
    store.token = 'new-account-token'; store.setUserInfo({ id: 2, username: 'new-account', role: 'STUDENT' })
    localStorage.setItem('token', 'new-account-token')
  })
  await expect(page).toHaveURL(/conversationId=new-owner/)
  resume(); rows = await list(page)
  await expect(rows.locator('.conversation')).toHaveCount(1)
  await expect(rows.getByRole('button', { name: '对话 new-owner', exact: true })).toBeVisible()
  await expect(rows.getByRole('button', { name: '对话 stale', exact: true })).toHaveCount(0)
})
