import { test, expect, type Page } from '@playwright/test'

async function login(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'keyboard-fixture')
    localStorage.setItem('userInfo', JSON.stringify({ id: 1, username: 'keyboard-test', role: 'STUDENT', status: 1 }))
  })
}

async function mockSession(page: Page) {
  const answers: unknown[] = []
  const records = [
    { questionId: 1, orderIndex: 0, isCorrect: null as number | null },
    { questionId: 2, orderIndex: 1, isCorrect: null as number | null }
  ]
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown = { list: [], total: 0 }
    if (path.endsWith('/answer')) {
      const body = route.request().postDataJSON()
      answers.push(body)
      const record = records.find(r => r.questionId === body.questionId)!
      record.isCorrect = body.answer === 'B' ? 1 : 0
      data = { questionId: body.questionId, userAnswer: body.answer, isCorrect: record.isCorrect, answer: 'B', analysis: '服务端解析' }
    } else if (/\/questions\/\d+$/.test(path)) {
      const id = Number(path.split('/').pop())
      data = { id, content: `键盘题干${id}`, subject: '数据结构', difficulty: 'MEDIUM', optionA: `甲${id}`, optionB: `乙${id}`, optionC: `丙${id}`, optionD: `丁${id}` }
    } else if (path.endsWith('/practice/sessions/kb-session')) data = records
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
  return answers
}

test('letter and number keys choose an option, Enter submits then advances', async ({ page }) => {
  await login(page)
  const answers = await mockSession(page)
  await page.goto('/practice/session/kb-session')
  await expect(page.locator('.q-title')).toHaveText('键盘题干1')

  // Enter without a choice submits nothing.
  await page.keyboard.press('Enter')
  expect(answers).toHaveLength(0)

  await page.keyboard.press('c')
  await expect(page.getByRole('radio', { name: 'C 丙1' })).toBeChecked()
  await page.keyboard.press('2')
  await expect(page.getByRole('radio', { name: 'B 乙1' })).toBeChecked()
  await expect(page.getByRole('status').filter({ hasText: '已选择 B' })).toBeVisible()

  await page.keyboard.press('Enter')
  await expect(page.locator('.feedback')).toContainText('回答正确')
  expect(answers).toEqual([{ questionId: 1, answer: 'B' }])

  // After grading, option keys no longer change the saved choice.
  await page.keyboard.press('a')
  await expect(page.getByRole('radio', { name: 'B 乙1' })).toBeChecked()
  await expect(page.getByRole('radio', { name: 'A 甲1' })).toBeDisabled()

  await page.keyboard.press('Enter')
  await expect(page.locator('.q-title')).toHaveText('键盘题干2')
  await expect(page.locator('.picked')).toHaveCount(0)
  expect(answers).toHaveLength(1)
})

test('clicking an option focuses its native radio and arrow keys move the choice', async ({ page }) => {
  await login(page)
  await mockSession(page)
  await page.goto('/practice/session/kb-session')
  await page.getByText('甲1', { exact: true }).click()
  await expect(page.getByRole('radio', { name: 'A 甲1' })).toBeFocused()
  await page.keyboard.press('ArrowDown')
  await expect(page.getByRole('radio', { name: 'B 乙1' })).toBeChecked()
  await expect(page.locator('.opt.picked')).toContainText('乙1')
})

test('shortcuts do not fire while typing in a text field', async ({ page }) => {
  await login(page)
  const answers = await mockSession(page)
  await page.goto('/practice/session/kb-session')
  await expect(page.locator('.q-title')).toHaveText('键盘题干1')
  await page.evaluate(() => {
    const input = document.createElement('textarea')
    input.id = 'probe'
    document.body.appendChild(input)
  })
  await page.locator('#probe').focus()
  await page.keyboard.type('b1')
  await page.keyboard.press('Enter')
  await expect(page.locator('.picked')).toHaveCount(0)
  expect(answers).toHaveLength(0)
})

test('practice settings are radio groups and the summary follows the selection', async ({ page }) => {
  await login(page)
  await page.route('http://127.0.0.1:4173/api/**', route => route.fulfill({ json: { code: 0, message: 'ok', data: { list: [], total: 0 } } }))
  await page.goto('/practice')
  const subject = page.getByRole('radiogroup', { name: '科目' })
  await expect(subject.getByRole('radio', { name: '数据结构' })).toBeChecked()
  await subject.getByRole('radio', { name: '数据结构' }).focus()
  await page.keyboard.press('ArrowRight')
  await expect(subject.getByRole('radio', { name: '操作系统' })).toBeChecked()
  await page.getByRole('radiogroup', { name: '难度' }).getByText('困难', { exact: true }).click()
  await expect(page.locator('.cfg-summary')).toHaveText('将从 普通练习 · 操作系统 · 困难 · 5 题 中抽题')

  await page.getByRole('radiogroup', { name: '题量' }).getByText('自定义', { exact: true }).click()
  const custom = page.getByLabel('自定义题量')
  await expect(custom).toBeFocused()
  await custom.fill('12')
  await expect(page.locator('.cfg-summary')).toContainText('12 题')
})
