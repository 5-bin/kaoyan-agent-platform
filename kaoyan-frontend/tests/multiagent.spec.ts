import { expect, test, type Page } from '@playwright/test'

const user = { id: 1, username: 'multi-student', role: 'STUDENT', status: 1 }
const conversation = { id: 'multi-conversation', title: '复习安排', conditions: {} }

async function setup(page: Page, authenticated = true, extended = true) {
  if (authenticated) await page.addInitScript(u => {
    localStorage.setItem('token', 'multi-token'); localStorage.setItem('userInfo', JSON.stringify(u))
  }, user)
  const messages: any[] = []
  let submitted = 0
  let created = false
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/auth/login')) data = { accessToken: 'multi-token' }
    else if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/privacy/settings')) data = { modelAllowed: false, scopes: [], version: 1 }
    else if (path.endsWith('/learning/status')) data = { enabled: true }
    else if (path.endsWith('/learning/profile')) data = { independentSamples: 0 }
    else if (path === '/api/conversations') {
      if (route.request().method() === 'POST') { created = true; data = conversation }
      else data = { list: created ? [conversation] : [], total: created ? 1 : 0 }
    }
    else if (path.endsWith('/messages')) {
      if (route.request().method() === 'POST') {
        submitted++
        messages.push({ id: 'm1', sequenceNo: 1, content: route.request().postDataJSON().query,
          attempts: [{ taskId: 't1', status: 'RUNNING', version: 0, draft: {} }] })
        data = { taskId: 't1', messageId: 'm1' }
      } else data = { conversation, list: messages, total: messages.length }
    } else if (path.endsWith('/stream')) {
      const result = { outcome: 'COMPLETED', answer: '学情分析与复习安排已完成', references: [], conditions: {},
        resolvedTaskType: 'CHAT', explanationMode: 'rules', releaseId: 'fixture', notice: '院校条件不足，请补充专业。',
        ...(extended ? { partial: true, sections: [
          { agent: 'LEARNING', outcome: 'COMPLETED', explanationMode: 'rules' },
          { agent: 'STUDY_PLAN', outcome: 'COMPLETED', explanationMode: 'rules' },
          { agent: 'SCHOOL', outcome: 'NEEDS_INPUT', explanationMode: 'rules', notice: '择校尚缺专业条件' }
        ] } : {}),
        studyPlan: { basis: ['样本不足，不输出完整408估分。'], days: [{ day: 1, topic: '线程', tasks: ['复习审核资料', '独立完成练习'] },
          ...[2, 3, 4, 5, 6, 7].map(day => ({ day, topic: `主题${day}`, tasks: [`主题${day}练习`] }))] } }
      messages[0].attempts[0] = { taskId: 't1', status: 'SUCCESS', version: 1, result }
      return route.fulfill({ contentType: 'text/event-stream', body: 'event: completed\ndata: ' + JSON.stringify(messages[0].attempts[0]) + '\n\n' })
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  return { submitted: () => submitted }
}

for (const extended of [true, false]) test(`diagnosis can be skipped and compound plan survives reload: sections=${extended}`, async ({ page }) => {
  const state = await setup(page, true, extended)
  await page.goto('/tasks')
  await expect(page.getByRole('button', { name: '开始单选诊断' })).toBeVisible()
  await page.getByRole('button', { name: '暂时跳过', exact: true }).click()
  await expect(page.getByRole('button', { name: '开始单选诊断' })).toHaveCount(0)
  expect(state.submitted()).toBe(0)
  await page.getByRole('button', { name: '分析学情并安排复习' }).click()
  expect(state.submitted()).toBe(0)
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByRole('region', { name: '复习安排', exact: true })).toContainText('第 1 天 · 线程')
  await expect(page.getByRole('region', { name: '复习安排', exact: true })).toContainText('样本不足')
  // A 7-day plan is fully expanded, and the card heading does not repeat the section label.
  await expect(page.getByRole('region', { name: '复习安排', exact: true }).getByRole('heading', { name: '每日安排（7天）' })).toBeVisible()
  await expect(page.getByText('主题7练习', { exact: true })).toBeVisible()
  await expect(page.getByText('院校条件不足，请补充专业。')).toBeVisible()
  if (extended) {
    await expect(page.getByRole('region', { name: '分项处理结果' })).toContainText('部分事项已完成')
    await expect(page.getByRole('region', { name: '分项处理结果' })).toContainText('院校比较 · 需补充条件')
  } else await expect(page.getByRole('region', { name: '分项处理结果' })).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('region', { name: '复习安排', exact: true })).toContainText('独立完成练习')
  if (extended) await expect(page.getByRole('region', { name: '分项处理结果' })).toContainText('择校尚缺专业条件')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

for (const redirect of ['', '?redirect=%2F', '?redirect=%2Fnotes']) {
  test(`login defaults to assistant and preserves business deep links ${redirect}`, async ({ page }) => {
    await setup(page, false)
    await page.goto('/login' + redirect)
    await page.getByPlaceholder('用户名', { exact: true }).fill('multi-student')
    await page.getByPlaceholder('密码', { exact: true }).fill('test-password')
    await page.getByRole('button', { name: '登 录' }).click()
    await expect(page).toHaveURL(redirect.includes('notes') ? /\/notes$/ : /\/tasks$/)
  })
}
