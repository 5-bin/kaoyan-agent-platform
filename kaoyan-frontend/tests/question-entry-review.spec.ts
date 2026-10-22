import { test, expect, type Page } from '@playwright/test'

const entry = { subject: '数据结构', knowledgePoint: '栈', difficulty: 'EASY', content: '自编题：栈遵循什么次序？',
  optionA: '后进先出', optionB: '先进先出', optionC: '随机次序', optionD: '按大小', answer: 'A',
  analysis: '栈只在栈顶入栈和出栈，因此后入先出。', sourceType: 'ORIGINAL', sourceName: '小组自编验证记录',
  sourceLocator: '<img src=x onerror=alert(1)> 第1题', sourceQuestionNo: '', permissionNote: '自编验证题，仅用于工程验收。' }
const question = { ...entry, id: 101, version: 1, questionType: 'SINGLE_CHOICE', active: 1, reviewStatus: 'PENDING_REVIEW' }

async function login(page: Page, role = 'ADMIN') {
  await page.addInitScript(role => {
    localStorage.setItem('token', 'entry-test-token')
    localStorage.setItem('userInfo', JSON.stringify({ id: 1, username: 'entry-test', role, status: 1 }))
  }, role)
}
async function fillEntry(page: Page) {
  await page.getByLabel('难度', { exact: true }).selectOption('EASY')
  const fields = { '知识点': entry.knowledgePoint, '题干': entry.content, '选项A': entry.optionA,
    '选项B': entry.optionB, '选项C': entry.optionC, '选项D': entry.optionD, '解析': entry.analysis,
    '来源名称／试卷名称': entry.sourceName, '来源定位': entry.sourceLocator, '使用权限说明': entry.permissionNote }
  for (const [label, value] of Object.entries(fields)) await page.getByLabel(label, { exact: true }).fill(value)
}
async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
}

test('enter, recover from a failed save, approve and read the persisted result', async ({ page }, info) => {
  await login(page)
  let saved: typeof question | undefined
  let writes = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown
    if (path === '/api/questions/admin' && route.request().method() === 'POST') {
      expect(route.request().postDataJSON()).toEqual(entry)
      writes++
      if (writes === 1) return route.fulfill({ status: 400, json: { code: 400, message: '请核对来源说明', data: null } })
      saved = { ...question }; data = saved
    } else if (path.endsWith('/review')) {
      expect(route.request().postDataJSON()).toEqual({ status: 'APPROVED', comment: '已核对自编说明', version: 1 })
      saved = { ...question, reviewStatus: 'APPROVED' }; data = null
    } else if (path.endsWith('/pending')) data = { total: saved?.reviewStatus === 'PENDING_REVIEW' ? 1 : 0, page: 1, size: 10, list: saved?.reviewStatus === 'PENDING_REVIEW' ? [saved] : [] }
    else data = saved
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/admin/questions')
  await expect(page.locator('.crumb')).toHaveText('题目录入与审核')
  await expect(page.locator('.el-menu-item.is-active')).toContainText('题目录入与审核')
  await page.getByRole('button', { name: '录入题目', exact: true }).click()
  await page.getByRole('button', { name: '保存并送审' }).click()
  await expect(page.getByRole('alert')).toContainText('请填写题目')
  expect(writes).toBe(0)
  await fillEntry(page)
  await noOverflow(page)
  await page.screenshot({ path: info.outputPath('entry-form.png'), fullPage: true })
  await page.getByRole('button', { name: '保存并送审' }).click()
  await expect(page.getByText('保存未成功，内容已保留，请核对错误信息后重试。')).toBeVisible()
  await expect(page.getByLabel('题干', { exact: true })).toHaveValue(entry.content)
  await page.getByRole('button', { name: '保存并送审' }).click()
  const detail = page.getByRole('region', { name: '题目详情' })
  await expect(detail).toContainText(entry.analysis)
  await expect(detail).toContainText(entry.sourceLocator)
  await expect(detail.locator('img')).toHaveCount(0)
  await page.getByLabel('审核意见（驳回必填）').fill('已核对自编说明')
  await page.getByRole('button', { name: '审核通过', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('审核通过')
  await expect(detail.getByText('审核通过', { exact: true })).toBeVisible()
  await expect(detail.getByRole('button', { name: '补充／修改' })).toHaveCount(0)
  await page.reload()
  await page.getByLabel('按题目ID查看').fill('101')
  await page.getByRole('button', { name: '查看题目', exact: true }).click()
  await expect(detail).toContainText('审核通过')
  await noOverflow(page)
  await page.screenshot({ path: info.outputPath('approved-detail.png'), fullPage: true })
  expect(writes).toBe(2)
})

test('reject requires a reason, stale review refreshes, and a corrected question resubmits', async ({ page }) => {
  await login(page)
  let current = { ...question }
  let reviews = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown = current
    if (path.endsWith('/review')) {
      reviews++
      if (reviews === 1) {
        current = { ...current, version: 2 }
        return route.fulfill({ status: 409, json: { code: 409, message: '题目已被修改，请刷新', data: null } })
      }
      expect(route.request().postDataJSON()).toEqual({ status: 'REJECTED', comment: '请补充解析', version: 2 })
      current = { ...current, reviewStatus: 'REJECTED' }; data = null
    } else if (route.request().method() === 'PUT') {
      expect(route.request().postDataJSON()).toEqual({ ...entry, analysis: '补充后的完整解析' })
      current = { ...current, analysis: '补充后的完整解析', version: 3, reviewStatus: 'PENDING_REVIEW' }; data = current
    } else if (path.endsWith('/pending')) data = { total: current.reviewStatus === 'PENDING_REVIEW' ? 1 : 0, page: 1, size: 10,
      list: current.reviewStatus === 'PENDING_REVIEW' ? [current] : [] }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  await page.goto('/admin/questions')
  await page.getByRole('button', { name: '查看并审核' }).click()
  await page.getByRole('button', { name: '驳回题目' }).click()
  await expect(page.getByText('驳回请填写审核意见。')).toBeVisible()
  expect(reviews).toBe(0)
  await page.getByLabel('审核意见（驳回必填）').fill('请补充解析')
  await page.getByRole('button', { name: '驳回题目' }).click()
  await expect(page.getByText('审核未成功，请查看错误信息并刷新详情后重试。')).toBeVisible()
  await page.getByRole('button', { name: '刷新详情' }).click()
  await expect(page.getByRole('heading', { name: '题目 #101 · 版本 2' })).toBeVisible()
  await page.getByLabel('审核意见（驳回必填）').fill('请补充解析')
  await page.getByRole('button', { name: '驳回题目' }).click()
  await page.getByRole('button', { name: '修改后重新送审' }).click()
  await page.getByLabel('解析', { exact: true }).fill('补充后的完整解析')
  await page.getByRole('button', { name: '保存并送审' }).click()
  await expect(page.getByRole('heading', { name: '题目 #101 · 版本 3' })).toBeVisible()
  await expect(page.getByRole('region', { name: '题目详情' })).toContainText('待审核')
})

test('real exams require year and question number before sending to review', async ({ page }) => {
  await login(page)
  let writes = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    if (route.request().method() === 'POST') {
      writes++
      const data = route.request().postDataJSON()
      expect(data.sourceYear).toBe(2024); expect(data.sourceQuestionNo).toBe('第1题')
      await route.fulfill({ json: { code: 0, message: 'ok', data: { ...question, ...data } } })
    } else await route.fulfill({ json: { code: 0, message: 'ok', data: { total: 0, list: [], page: 1, size: 10 } } })
  })
  await page.goto('/admin/questions')
  await page.getByRole('button', { name: '录入题目', exact: true }).click()
  await fillEntry(page)
  await page.getByLabel('来源类别').selectOption('REAL_EXAM')
  await page.getByRole('button', { name: '保存并送审' }).click()
  await expect(page.getByText('真题必须填写年份和原题号。')).toBeVisible()
  expect(writes).toBe(0)
  await page.getByLabel('年份（必填）', { exact: true }).fill('2024')
  await page.getByLabel('原题号（必填）', { exact: true }).fill('第1题')
  await page.getByRole('button', { name: '保存并送审' }).click()
  await expect(page.getByRole('region', { name: '题目详情' })).toContainText('2024')
  expect(writes).toBe(1)
})

test('list failures remain errors and pagination loads distinct pending records', async ({ page }) => {
  await login(page)
  let requests = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    requests++
    if (requests === 1) return route.fulfill({ status: 500, json: { code: 500, message: '暂时不可用', data: null } })
    const pageNum = Number(new URL(route.request().url()).searchParams.get('pageNum'))
    const row = { ...question, id: pageNum, content: '分页记录 ' + pageNum }
    await route.fulfill({ json: { code: 0, message: 'ok', data: { total: 21, list: [row], page: pageNum, size: 10 } } })
  })
  await page.goto('/admin/questions')
  await expect(page.getByRole('alert').filter({ hasText: '待审核列表加载失败' })).toBeVisible()
  await expect(page.getByText('没有待审核题目')).toHaveCount(0)
  await page.getByRole('button', { name: '重试加载' }).click()
  await expect(page.getByText('分页记录 1', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '下一页' }).click()
  await expect(page.getByText('分页记录 2', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '上一页' }).click()
  await expect(page.getByText('分页记录 1', { exact: true })).toBeVisible()
  await noOverflow(page)
})

test('student route guard hides question management', async ({ page }) => {
  await login(page, 'STUDENT')
  let managementRequests = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    if (route.request().url().includes('/questions/admin')) managementRequests++
    await route.fulfill({ json: { code: 0, message: 'ok', data: { questionCount: 0, correctCount: 0, studyMinutes: 0 } } })
  })
  await page.goto('/admin/questions')
  await expect(page).toHaveURL('http://127.0.0.1:4173/')
  await expect(page.getByRole('button', { name: '录入题目' })).toHaveCount(0)
  expect(managementRequests).toBe(0)
})
