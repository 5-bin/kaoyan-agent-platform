import { expect, test } from '@playwright/test'
import { existsSync } from 'node:fs'
import { extname, resolve } from 'node:path'

test('saved clarification is sent once and old choices disappear', async ({ page }, info) => {
  const user = { id: 1, username: 'student', role: 'STUDENT', status: 1 }
  const conversation = { id: 'c1', title: '澄清', conditions: {} }
  const result = { outcome: 'NEEDS_INPUT', answer: '请选择处理方式', resolvedTaskType: 'CHAT', explanationMode: 'rules', releaseId: 'fixture', references: [], clarificationOptions: [{ label: '知识辅导', reply: '我想咨询408知识' }] }
  const messages: any[] = [{ id: 'm1', content: '帮帮我', attempts: [{ taskId: 't1', status: 'SUCCESS', version: 1, result }] }]
  const sent: string[] = []
  const types: Record<string, string> = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2' }
  await page.route('http://127.0.0.1:4173/**', async route => {
    const pathname = decodeURIComponent(new URL(route.request().url()).pathname)
    if (pathname.startsWith('/api/')) return route.abort()
    const asset = resolve(process.cwd(), 'dist', '.' + pathname)
    const path = pathname !== '/' && existsSync(asset) ? asset : resolve(process.cwd(), 'dist/index.html')
    await route.fulfill({ path, contentType: types[extname(path)] || 'application/octet-stream' })
  })
  await page.addInitScript(u => { localStorage.setItem('token', 'token'); localStorage.setItem('userInfo', JSON.stringify(u)) }, user)
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/privacy/settings')) data = { modelAllowed: false, scopes: [], version: 1 }
    else if (path.endsWith('/learning/status')) data = { enabled: false }
    else if (path === '/api/conversations') data = { list: [conversation], total: 1 }
    else if (path.endsWith('/messages')) {
      if (route.request().method() === 'POST') {
        sent.push(route.request().postDataJSON().query)
        messages.unshift({ id: 'm2', content: sent[0], attempts: [{ taskId: 't2', status: 'RUNNING', version: 0, draft: {} }] })
        data = { taskId: 't2', messageId: 'm2' }
      } else data = { conversation, list: messages, total: messages.length }
    } else if (path.endsWith('/stream')) {
      return route.fulfill({ contentType: 'text/event-stream', body: '' })
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/tasks')
  if (info.project.name === 'mobile') await page.getByRole('button', { name: '会话', exact: true }).click()
  await (info.project.name === 'mobile' ? page.locator('.el-drawer').getByText('澄清', { exact: true }) : page.getByText('澄清', { exact: true }).first()).click()
  await expect(page.getByRole('button', { name: '知识辅导', exact: true })).toBeVisible()
  await page.reload()
  if (info.project.name === 'mobile') await page.getByRole('button', { name: '会话', exact: true }).click()
  await (info.project.name === 'mobile' ? page.locator('.el-drawer').getByText('澄清', { exact: true }) : page.getByText('澄清', { exact: true }).first()).click()
  await page.getByRole('button', { name: '知识辅导', exact: true }).click()
  await expect.poll(() => sent.length).toBe(1)
  expect(sent).toEqual(['我想咨询408知识'])
  await expect(page.getByRole('button', { name: '知识辅导', exact: true })).toHaveCount(0)
})
