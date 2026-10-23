import { test, expect } from '@playwright/test'

const user = { id: 71, username: 'synthetic-notes', role: 'STUDENT', status: 1 }
const conversation = { id: 'notes-conversation', title: '修改复习计划', conditions: {} }
test.beforeEach(async ({ page }) => {
  await page.addInitScript(value => { localStorage.setItem('token', 'notes-test-token'); localStorage.setItem('userInfo', JSON.stringify(value)) }, user)
})

test('notes navigation, manual versions, assistant selection and confirmed proposal stay in sync', async ({ page }, info) => {
  let note: any, proposalSaved = false, submitted: any, messages: any[] = []
  const history: any[] = []
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/privacy/settings')) data = { modelAllowed: false, scopes: [], provider: 'synthetic.invalid', version: 1, retentionDays: 30 }
    else if (path === '/api/conversations') data = method === 'POST' ? conversation : { list: [conversation], total: 1 }
    else if (path === '/api/personal-documents' && method === 'GET') data = { list: note ? [note] : [], total: note ? 1 : 0 }
    else if (path === '/api/personal-documents' && method === 'POST' || path === '/api/personal-documents/note-one' && method === 'PUT') {
      const input = route.request().postDataJSON()
      if (method === 'PUT') expect(input.baseVersion).toBe(note.version)
      note = { id: 'note-one', title: input.title, content: input.content, version: (note?.version || 0) + 1 }
      history.unshift({ ...note }); data = note
    } else if (path === '/api/personal-documents/note-one') data = note
    else if (path.endsWith('/versions')) data = { list: history, total: history.length }
    else if (path.includes('/versions/')) data = history.find(item => item.version === Number(path.split('/').at(-1)))
    else if (path.endsWith('/messages')) {
      if (method === 'POST') {
        submitted = route.request().postDataJSON()
        messages = [{ id: 'note-message', content: submitted.query, attempts: [{ taskId: 'note-task', status: 'SUCCESS', version: 1,
          result: { outcome: 'COMPLETED', explanationMode: 'ai', answer: '笔记建议已生成', conditions: {}, references: [], documentProposal: { operation: 'update', documentId: 'note-one', baseVersion: 2, title: '综合复习计划', content: '# 数据结构与操作系统\n每天30分钟' } } }] }]
        data = { taskId: 'note-task', messageId: 'note-message' }
      } else data = { conversation, list: messages, total: messages.length }
    } else if (path.endsWith('/apply-document')) {
      proposalSaved = true
      const input = route.request().postDataJSON()
      note = { ...note, ...input, version: 3 }; history.unshift({ ...note }); data = note
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/notes')
  await expect(page.getByRole('menuitem', { name: '个人笔记' })).toBeVisible()
  await page.getByRole('button', { name: '新建笔记', exact: true }).click()
  await page.getByRole('textbox', { name: '笔记标题', exact: true }).fill('操作系统复习计划')
  await page.getByRole('textbox', { name: '笔记正文', exact: true }).fill('# 原计划\n每天1小时')
  await expect(page.locator('.note-preview')).toContainText('原计划')
  await page.getByRole('button', { name: '创建笔记', exact: true }).click()
  await expect(page).toHaveURL(/noteId=note-one/)
  await page.getByRole('textbox', { name: '笔记正文', exact: true }).fill('# 原计划\n每天30分钟')
  await page.getByText('查看修改差异（基于 v1）', { exact: true }).click()
  await expect(page.locator('.diff .removed')).toContainText('每天1小时')
  await page.getByRole('button', { name: '保存新版本', exact: true }).click()
  await expect(page.getByText('编辑笔记 · v2', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('textbox', { name: '笔记正文', exact: true })).toHaveValue('# 原计划\n每天30分钟')
  await page.getByRole('button', { name: '历史版本', exact: true }).click()
  await page.getByRole('dialog', { name: '笔记历史版本', exact: true }).getByRole('button', { name: '查看此版本' }).last().click()
  await expect(page.getByRole('dialog', { name: '历史版本（只读）' })).toContainText('每天1小时')
  await page.getByRole('dialog', { name: '历史版本（只读）' }).locator('.el-dialog__headerbtn').click()
  await page.getByRole('dialog', { name: '笔记历史版本', exact: true }).locator('.el-dialog__headerbtn').click()
  await page.getByRole('button', { name: '让助手修改', exact: true }).click()
  await expect(page.locator('.document-selection')).toContainText('操作系统复习计划')
  await page.getByRole('textbox', { name: '聊天输入' }).fill('根据当前我的薄弱点帮我改进一下该计划')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByRole('button', { name: '预览笔记建议' })).toBeVisible()
  expect(submitted.documentId).toBe('note-one'); expect(submitted.documentVersion).toBe(2)
  expect(submitted.pageContext).toEqual({ page: 'notes' })
  await page.getByRole('button', { name: '预览笔记建议' }).click()
  expect(proposalSaved).toBe(false)
  await page.getByRole('button', { name: '确认保存建议' }).click()
  await expect.poll(() => proposalSaved).toBe(true)
  await page.locator('.chat-heading').getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByRole('textbox', { name: '笔记标题', exact: true })).toHaveValue('综合复习计划')
  await expect(page.getByRole('textbox', { name: '笔记正文', exact: true })).toHaveValue('# 数据结构与操作系统\n每天30分钟')
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  await page.screenshot({ path: info.outputPath('personal-notes.png'), fullPage: true })
})

test('version conflict keeps unsaved note text', async ({ page }) => {
  const note = { id: 'note-one', title: '合成笔记', content: '# 原文', version: 1 }
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() === 'PUT') { await route.fulfill({ status: 409, json: { code: 409, message: '笔记已有新版本' } }); return }
    const data = path.endsWith('/users/me') ? user : path.endsWith('/note-one') ? note : { list: [note], total: 1 }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/notes?noteId=note-one')
  await page.getByRole('textbox', { name: '笔记正文', exact: true }).fill('保留我的尚未保存内容')
  await page.getByRole('button', { name: '保存新版本', exact: true }).click()
  await expect(page.getByText('笔记已有新版本。你的编辑内容已保留，请重新读取并核对后再保存。')).toBeVisible()
  await expect(page.getByRole('textbox', { name: '笔记正文', exact: true })).toHaveValue('保留我的尚未保存内容')
})

test('clearing a note while it loads unblocks sending and ignores the late note response', async ({ page }) => {
  let started = false, release!: () => void
  const delayed = new Promise<void>(resolve => { release = resolve })
  const note = { id: 'note-delayed', title: '延迟加载的笔记', content: '迟到正文', version: 1 }
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = user
    else if (path === '/api/conversations') data = { list: [conversation], total: 1 }
    else if (path.endsWith('/messages')) data = { conversation, list: [], total: 0 }
    else if (path === '/api/personal-documents') data = { list: [note], total: 1 }
    else if (path.endsWith('/note-delayed')) { started = true; await delayed; data = note }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/tasks')
  const select = page.locator('.document-selection .el-select')
  await select.click()
  await page.getByRole('option', { name: '延迟加载的笔记', exact: true }).click()
  await expect.poll(() => started).toBe(true)
  await select.hover()
  await select.locator('.el-select__clear').click()
  await page.getByRole('textbox', { name: '聊天输入' }).fill('进程与线程')
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeEnabled()
  release()
  await expect(page.locator('.document-selection small')).toHaveCount(0)
})
