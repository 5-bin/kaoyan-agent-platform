import { test, expect, type Page } from '@playwright/test'

const note = { id: 'export-note', title: '合成笔记', version: 2, content: '已保存正文' }
const preview = { id: 'export-snapshot', title: note.title, sourceVersion: '笔记 v2', generatedAt: '2026-11-01', expiresAt: '2026-11-01 13:00', markdown: '# 合成笔记\n\n已保存正文', charts: [] }
async function setup(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'export-test-token')
    localStorage.setItem('userInfo', JSON.stringify({ id: 81, username: 'export-user', role: 'STUDENT', status: 1 }))
  })
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown = { list: [], total: 0 }
    if (path === '/api/users/me') data = { id: 81, username: 'export-user', role: 'STUDENT', status: 1 }
    else if (path === '/api/personal-documents') data = { list: [note], total: 1 }
    else if (path === '/api/personal-documents/export-note') data = note
    else if (path === '/api/exports/preview') data = preview
    else if (path.endsWith('/privacy/settings')) data = { modelAllowed: false, scopes: [], version: 1 }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/notes?noteId=export-note')
  await expect(page.getByRole('textbox', { name: '笔记正文', exact: true })).toHaveValue(note.content)
}
test('exports saved version with a draft warning and downloads Markdown', async ({ page }) => {
  await setup(page)
  let requested: unknown
  await page.route('**/api/exports/preview', async route => {
    requested = route.request().postDataJSON()
    await route.fulfill({ json: { code: 0, message: 'ok', data: preview } })
  })
  await page.route('**/api/exports/export-snapshot/file?*', route => route.fulfill({ contentType: 'text/markdown;charset=UTF-8', body: preview.markdown }))
  await page.getByRole('textbox', { name: '笔记正文', exact: true }).fill('尚未保存的私人草稿')
  await page.getByRole('button', { name: '导出文件', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '导出预览' })
  await expect(dialog).toContainText('当前导出已保存的 v2')
  await expect(dialog.getByLabel('文件内容预览')).not.toContainText('尚未保存的私人草稿')
  expect(requested).toEqual({ source: 'NOTE', documentId: note.id, version: 2 })
  await dialog.locator('.el-select').click()
  await page.getByRole('option', { name: 'Markdown（.md）' }).click()
  const download = page.waitForEvent('download')
  await dialog.getByRole('button', { name: '下载文件', exact: true }).click()
  expect((await download).suggestedFilename()).toBe('合成笔记.md')
})
test('expired Blob error is shown without producing a downloaded JSON file', async ({ page }) => {
  await setup(page)
  let downloads = 0
  page.on('download', () => downloads++)
  await page.route('**/api/exports/export-snapshot/file?*', route => route.fulfill({ status: 404, json: { code: 404, message: '预览已过期', data: null } }))
  await page.getByRole('button', { name: '导出文件', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '导出预览' })
  await dialog.getByRole('button', { name: '下载文件', exact: true }).click()
  await expect(dialog).toContainText('预览已过期或来源已清除')
  expect(downloads).toBe(0)
  await dialog.getByRole('button', { name: '重新生成预览' }).click()
  await expect(dialog.getByLabel('文件内容预览')).toContainText('已保存正文')
})
test('closing cancels a late preview and an expired login prevents download', async ({ page }) => {
  await setup(page)
  let finish: (() => void) | undefined
  const pending = new Promise<void>(resolve => { finish = resolve })
  await page.route('**/api/exports/preview', async route => {
    await pending
    await route.fulfill({ json: { code: 0, message: 'ok', data: preview } }).catch(() => {})
  })
  await page.getByRole('button', { name: '导出文件', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '导出预览' })
  await expect(dialog).toContainText('正在读取导出内容')
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  finish!()
  await expect(dialog).not.toBeVisible()
  await page.unroute('**/api/exports/preview')
  await page.route('**/api/exports/export-snapshot/file?*', route => route.fulfill({ status: 401, json: { code: 401, message: '未登录', data: null } }))
  let downloads = 0
  page.on('download', () => downloads++)
  await page.getByRole('button', { name: '导出文件', exact: true }).click()
  await dialog.getByRole('button', { name: '下载文件', exact: true }).click()
  await expect(page).toHaveURL(/\/login/)
  expect(downloads).toBe(0)
})
