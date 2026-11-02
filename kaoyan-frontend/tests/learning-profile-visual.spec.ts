import { test, expect, type Locator, type Page } from '@playwright/test'

const user = { id: 41, username: 'profile-visual', role: 'STUDENT', status: 1 }

const groups = [
  {
    knowledgePointId: 'ds-sort', subject: '数据结构', knowledgePoint: '排序', difficulty: 'MEDIUM',
    samples: 8, correct: 6, assisted: 1, unknown: 0, masteryIndex: 0.7,
    sampleStatus: 'SUFFICIENT', weight: 0.12, priority: 0.036, anomaly: false,
  },
  {
    knowledgePointId: 'ds-tree', subject: '数据结构', knowledgePoint: '二叉树', difficulty: 'EASY',
    samples: 3, correct: 1, assisted: 0, unknown: 1, masteryIndex: 0.4,
    sampleStatus: 'INSUFFICIENT', weight: 0.1, priority: 0.06, anomaly: false,
  },
  {
    knowledgePointId: 'os-process', subject: '操作系统', knowledgePoint: '进程与线程', difficulty: 'MEDIUM',
    samples: 10, correct: 3, assisted: 2, unknown: 0, masteryIndex: 0.36,
    sampleStatus: 'SUFFICIENT', weight: 0.15, priority: 0.096, anomaly: true,
  },
  {
    knowledgePointId: 'net-tcp', subject: '计算机网络', knowledgePoint: 'TCP 拥塞控制', difficulty: 'HARD',
    samples: 6, correct: 5, assisted: 1, unknown: 1, masteryIndex: 0.8,
    sampleStatus: 'SUFFICIENT', weight: 0.1, priority: 0.02, anomaly: false,
  },
  {
    knowledgePointId: 'co-storage', subject: '计算机组成原理', knowledgePoint: '存储层次', difficulty: 'EASY',
    samples: 0, correct: 0, assisted: 0, unknown: 0, masteryIndex: null,
    sampleStatus: 'NOT_DIAGNOSED', weight: 0.05, priority: null, anomaly: false,
  },
]

const profile = {
  revision: 3,
  algorithmVersion: 'learning-v1',
  blueprintVersion: 'blueprint-test',
  referenceScore: 112,
  coverage: 0.68,
  independentSamples: 27,
  assistedSamples: 4,
  unknownSamples: 2,
  sufficient: false,
  status: 'ACTIVE',
  updatedAt: '2026-10-30T10:00:00Z',
  groups,
  notices: ['超过30天未产生有效证据，建议复测；未直接判定遗忘。'],
}

const history = [
  { ...profile, revision: 1, referenceScore: null, coverage: 0.3, groups: [] },
  profile,
]

const longPoint = '超长知识点名称：多阶段流水线冲突与数据冒险综合判定'
const manyGroups = Array.from({ length: 12 }, (_, index) => ({
  knowledgePointId: `many-${index}`,
  subject: index % 2 === 0 ? '数据结构' : '操作系统',
  knowledgePoint: index === 0 ? longPoint : `知识点 ${index + 1}`,
  difficulty: ['EASY', 'MEDIUM', 'HARD'][index % 3],
  samples: 6 + index,
  correct: 4,
  assisted: 0,
  unknown: 0,
  masteryIndex: Math.min(0.85, 0.45 + index * 0.03),
  sampleStatus: 'SUFFICIENT',
  weight: 0.05,
  priority: 0.2 - index * 0.01,
  anomaly: false,
}))

const insufficientGroups = [
  {
    ...groups[0], knowledgePointId: 'ins-0', knowledgePoint: '尚未诊断知识点', difficulty: 'MEDIUM',
    samples: 0, correct: 0, assisted: 0, unknown: 0, masteryIndex: null,
    sampleStatus: 'NOT_DIAGNOSED', weight: 0.08, priority: 0.09,
  },
  {
    ...groups[0], knowledgePointId: 'ins-1', knowledgePoint: '样本不足知识点甲', difficulty: 'MEDIUM',
    samples: 2, correct: 1, assisted: 0, unknown: 0, masteryIndex: 0.5,
    sampleStatus: 'INSUFFICIENT', weight: 0.07, priority: 0.08,
  },
  {
    ...groups[0], knowledgePointId: 'ins-2', knowledgePoint: '样本不足知识点乙', difficulty: 'MEDIUM',
    samples: 4, correct: 3, assisted: 0, unknown: 0, masteryIndex: 0.8,
    sampleStatus: 'INSUFFICIENT', weight: 0.06, priority: 0.07,
  },
]

const undiagnosedProfile = {
  ...profile,
  independentSamples: 0,
  assistedSamples: 0,
  unknownSamples: 0,
  sufficient: false,
  groups: groups.map(group => ({
    ...group,
    samples: 0,
    correct: 0,
    assisted: 0,
    unknown: 0,
    masteryIndex: null,
    sampleStatus: 'NOT_DIAGNOSED',
  })),
}

type SetupOverrides = {
  profile?: unknown
  profiles?: unknown[]
  history?: unknown
  historyFails?: boolean
}

async function setup(page: Page, overrides: SetupOverrides = {}) {
  await page.addInitScript(value => {
    localStorage.setItem('token', 'profile-visual-token')
    localStorage.setItem('userInfo', JSON.stringify(value))
  }, user)
  let profileRequest = 0
  await page.route('http://127.0.0.1:4173/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data: any = { list: [], total: 0 }
    if (path.endsWith('/users/me')) data = user
    else if (path.endsWith('/learning/status')) data = { enabled: true }
    else if (path.endsWith('/learning/profile/history')) {
      if (overrides.historyFails) {
        await route.fulfill({ status: 500, json: { code: 500, message: 'history failed', data: null } })
        return
      }
      data = { list: overrides.history ?? history, total: 2 }
    } else if (path.endsWith('/learning/profile')) {
      if (overrides.profiles?.length) {
        data = overrides.profiles[Math.min(profileRequest, overrides.profiles.length - 1)]
        profileRequest += 1
      } else {
        data = overrides.profile ?? profile
      }
    } else if (path.endsWith('/stats/learning')) {
      data = {
        questionCount: 12, correctCount: 9, uniqueQuestions: 8, wrongCount: 3, accuracy: 0.75,
        from: '2026-10-01', to: '2026-10-30', daily: [], knowledgePoints: [],
      }
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data } })
  })
}

async function boxOf(locator: Locator) {
  const box = await locator.boundingBox()
  expect(box, 'element should have a layout box').not.toBeNull()
  return box!
}

async function expectNoHorizontalOverflow(page: Page) {
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }))
  expect(widths.scroll, 'page should not scroll horizontally').toBeLessThanOrEqual(widths.viewport + 1)
}

// ECharts 6 may stack several layer canvases for one chart (heatmap cells use an
// incremental layer). One chart instance means every canvas shares one zrender root.
async function expectSingleChart(container: Locator) {
  await expect(container.locator('canvas').first()).toBeAttached()
  const roots = await container.evaluate(element =>
    new Set(Array.from(element.querySelectorAll('canvas'), canvas => canvas.parentElement)).size,
  )
  expect(roots, 'chart should not be initialised twice').toBe(1)
}

async function expectCanvasMatchesContainer(page: Page, testId: string) {
  const container = page.getByTestId(testId).locator('.chart-canvas')
  await expectSingleChart(container)
  await expect
    .poll(async () => {
      const deltas = await container.evaluate(element => {
        const containerRect = element.getBoundingClientRect()
        return Array.from(element.querySelectorAll('canvas'), canvas => {
          const canvasRect = canvas.getBoundingClientRect()
          return Math.max(
            Math.abs(containerRect.width - canvasRect.width),
            Math.abs(containerRect.height - canvasRect.height),
          )
        })
      })
      return deltas.length ? Math.max(...deltas) : 999
    })
    .toBeLessThanOrEqual(1.5)
}

async function expectChartFrameLayout(page: Page, testId: string) {
  const frame = page.getByTestId(testId)
  await expect(frame).toBeVisible()
  const header = frame.locator('.chart-head')
  const canvas = frame.locator('.chart-canvas')
  const legend = frame.locator('.chart-legend')
  const summary = frame.locator('.chart-summary')
  await expect(canvas).toHaveCount(1)
  await expectSingleChart(canvas)
  await expect(legend).toHaveCount(1)
  await expect(summary).toHaveCount(1)

  const frameBox = await boxOf(frame)
  const headerBox = await boxOf(header)
  const canvasBox = await boxOf(canvas)
  const legendBox = await boxOf(legend)
  const summaryBox = await boxOf(summary)

  for (const [name, box] of [
    ['drawing area', canvasBox],
    ['legend', legendBox],
    ['summary', summaryBox],
  ] as const) {
    expect(box.x, `${name} should start inside the card`).toBeGreaterThanOrEqual(frameBox.x - 1)
    expect(box.x + box.width, `${name} should end inside the card`).toBeLessThanOrEqual(
      frameBox.x + frameBox.width + 1,
    )
    expect(box.y, `${name} should start inside the card`).toBeGreaterThanOrEqual(frameBox.y - 1)
    expect(box.y + box.height, `${name} should end inside the card`).toBeLessThanOrEqual(
      frameBox.y + frameBox.height + 1,
    )
  }

  // Reading order is title/actions → drawing area → in-card legend → summary.
  expect(headerBox.y + headerBox.height).toBeLessThanOrEqual(canvasBox.y + 1)
  expect(canvasBox.y + canvasBox.height).toBeLessThanOrEqual(legendBox.y + 1)
  expect(legendBox.y + legendBox.height).toBeLessThanOrEqual(summaryBox.y + 1)
  expect(summaryBox.y + summaryBox.height).toBeLessThanOrEqual(frameBox.y + frameBox.height + 1)

  expect(await summary.innerText()).not.toBe('')
}

// These constants mirror MasteryHeatmap's cartesian grid. The tests use them to
// aim at a real heat cell/axis label, not merely to assert that a canvas exists.
const HEAT_GRID = { left: 116, right: 20, top: 16, bottom: 42 }

async function heatCellPoint(page: Page, rows: number, row: number, column: number) {
  const canvas = page.getByTestId('mastery-heatmap').locator('.chart-canvas')
  await canvas.scrollIntoViewIfNeeded()
  const canvasBox = await boxOf(canvas)
  const plotWidth = canvasBox.width - HEAT_GRID.left - HEAT_GRID.right
  const plotHeight = canvasBox.height - HEAT_GRID.top - HEAT_GRID.bottom
  return {
    x: canvasBox.x + HEAT_GRID.left + ((column + 0.5) * plotWidth) / 3,
    y: canvasBox.y + HEAT_GRID.top + ((row + 0.5) * plotHeight) / rows,
  }
}

async function sampleHeatPixel(page: Page, rows: number, row: number, column: number) {
  const canvasBox = await boxOf(page.getByTestId('mastery-heatmap').locator('.chart-canvas'))
  const plotWidth = canvasBox.width - HEAT_GRID.left - HEAT_GRID.right
  const plotHeight = canvasBox.height - HEAT_GRID.top - HEAT_GRID.bottom
  const point = {
    x: canvasBox.x + HEAT_GRID.left + ((column + 0.15) * plotWidth) / 3,
    y: canvasBox.y + HEAT_GRID.top + ((row + 0.15) * plotHeight) / rows,
  }
  // Composite every layer in DOM (paint) order, then read the pixel the user sees.
  return page
    .getByTestId('mastery-heatmap')
    .locator('.chart-canvas')
    .evaluate((element, target) => {
      const layers = Array.from(element.querySelectorAll('canvas'))
      if (!layers.length) return null
      const canvas = document.createElement('canvas')
      canvas.width = layers[0].width
      canvas.height = layers[0].height
      const context = canvas.getContext('2d')
      if (!context) return null
      for (const layer of layers) context.drawImage(layer, 0, 0)
      const rect = layers[0].getBoundingClientRect()
      const x = Math.max(
        0,
        Math.min(canvas.width - 1, Math.round(((target.x - rect.left) / rect.width) * canvas.width)),
      )
      const y = Math.max(
        0,
        Math.min(canvas.height - 1, Math.round(((target.y - rect.top) / rect.height) * canvas.height)),
      )
      const data = context.getImageData(x, y, 1, 1).data
      return { r: data[0], g: data[1], b: data[2], a: data[3] }
    }, point)
}

async function hoverHeatCell(page: Page, rows: number, row: number, column: number, tooltip: Locator) {
  const point = await heatCellPoint(page, rows, row, column)
  // A late chart re-render can drop the first hover (seen on ECharts 5 and 6),
  // so leave the cell and hover again until the tooltip appears.
  await expect(async () => {
    await page.mouse.move(0, 0)
    await page.mouse.move(point.x, point.y)
    await expect(tooltip).toBeVisible({ timeout: 1000 })
  }).toPass({ timeout: 8000 })
}

async function selectSubject(page: Page, label: string) {
  const select = page.getByTestId('mastery-heatmap').locator('.el-select__wrapper')
  await select.click()
  await page.getByRole('option', { name: label, exact: true }).click()
}

test('learning profile renders evidence-aware charts, ranking and table fallback', async ({ page }) => {
  await setup(page)
  await page.goto('/stat')

  const panel = page.getByTestId('learning-profile')
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('学情画像')
  await expect(page.getByTestId('profile-kpi')).toContainText('112')
  await expect(page.getByTestId('profile-kpi')).toContainText('实验性')
  await expect(page.getByTestId('profile-kpi')).toContainText('68')
  await expect(page.getByTestId('profile-kpi')).toContainText('独立证据')

  await expect(page.getByTestId('mastery-heatmap')).toBeVisible()
  await expectSingleChart(page.getByTestId('mastery-heatmap').locator('.chart-canvas'))
  await expect(page.getByTestId('mastery-heatmap')).toContainText('样本不足')
  await expect(page.getByTestId('heatmap-legend')).toBeVisible()
  await expect(page.getByTestId('evidence-scatter')).toBeVisible()
  await expectSingleChart(page.getByTestId('evidence-scatter').locator('.chart-canvas'))
  await expect(page.getByTestId('evidence-scatter')).toContainText('尚未诊断')
  await expect(page.getByTestId('scatter-legend')).toContainText('数据结构')
  await expect(page.getByTestId('scatter-legend')).toContainText('点大小')

  const subjectToggle = page.getByTestId('scatter-legend').getByRole('button', { name: '显示数据结构证据' })
  await subjectToggle.click()
  await expect(subjectToggle).toHaveAttribute('aria-pressed', 'false')
  await subjectToggle.click()
  await expect(subjectToggle).toHaveAttribute('aria-pressed', 'true')

  await expectChartFrameLayout(page, 'mastery-heatmap')
  await expectChartFrameLayout(page, 'evidence-scatter')
  await expectCanvasMatchesContainer(page, 'mastery-heatmap')
  await expectCanvasMatchesContainer(page, 'evidence-scatter')

  // The chart cards, including their in-card legends and summaries, must end
  // before the lower ranking/subject cards start.
  const lowerTop = (await boxOf(page.getByTestId('weak-ranking'))).y
  for (const testId of ['mastery-heatmap', 'evidence-scatter']) {
    const chartBox = await boxOf(page.getByTestId(testId))
    expect(chartBox.y + chartBox.height).toBeLessThanOrEqual(lowerTop + 1)
  }

  // Proof that the first heat row actually painted its medium-difficulty cell:
  // the first row is 进程与线程 (priority 0.096), whose MEDIUM cell is weak red.
  const pixel = await sampleHeatPixel(page, 5, 0, 1)
  expect(pixel, 'heatmap canvas should be readable').not.toBeNull()
  expect(pixel!.a).toBeGreaterThan(200)
  expect(pixel!.r).toBeGreaterThan(200)
  expect(pixel!.g).toBeLessThan(220)

  await hoverHeatCell(page, 5, 0, 1, page.getByTestId('mastery-heatmap').getByText('独立样本 10'))
  await expect(page.getByTestId('mastery-heatmap')).toContainText('进程与线程')
  await expect(page.getByTestId('mastery-heatmap')).toContainText('独立样本 10')
  await expect(page.getByTestId('mastery-heatmap')).toContainText('近期表现异常')

  await expect(page.getByTestId('weak-ranking')).toContainText('进程与线程')
  await expect(page.getByTestId('weak-ranking')).toContainText('样本不足')
  await expect(page.getByTestId('subject-cards')).toContainText('数据结构')

  await page.locator('summary', { hasText: '查看完整数据表' }).click()
  await expect(page.getByText('掌握指数', { exact: true })).toBeVisible()
  await expect(page.locator('.table-wrap').getByText('补充独立诊断样本', { exact: true }).first()).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('learning profile keeps the panel usable when history fails', async ({ page }) => {
  await setup(page, { historyFails: true })
  await page.goto('/stat')
  await expect(page.getByTestId('profile-kpi')).toContainText('112')
  await expect(page.getByTestId('mastery-heatmap')).toBeVisible()
  await expect(page.getByTestId('profile-history')).toHaveCount(0)
  await expectChartFrameLayout(page, 'mastery-heatmap')
  await expectNoHorizontalOverflow(page)
})

test('learning profile explains insufficient evidence without inventing a score', async ({ page }) => {
  await setup(page, {
    profile: {
      ...profile,
      referenceScore: null,
      coverage: 0.2,
      independentSamples: 3,
      sufficient: false,
      groups: [groups[1]],
    },
    history: [profile],
  })
  await page.goto('/stat')
  await expect(page.getByTestId('profile-kpi')).toContainText('证据不足')
  await expect(page.getByTestId('profile-kpi')).toContainText('仍有样本不足')
  await expect(page.getByTestId('weak-ranking')).toContainText('暂无独立样本达到 5 条')
  await expect(page.getByTestId('profile-history')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)
})

test('heatmap keeps undiagnosed and insufficient cells grey and textual', async ({ page }) => {
  await setup(page, {
    profile: {
      ...profile,
      groups: insufficientGroups,
      independentSamples: 6,
      assistedSamples: 0,
      unknownSamples: 0,
      sufficient: false,
    },
    history: [profile],
  })
  await page.goto('/stat')
  const heatmap = page.getByTestId('mastery-heatmap')
  await expect(heatmap).toBeVisible()
  await expectChartFrameLayout(page, 'mastery-heatmap')

  const pixel = await sampleHeatPixel(page, 3, 1, 1)
  expect(pixel, 'heatmap canvas should be readable').not.toBeNull()
  expect(pixel!.a).toBeGreaterThan(200)
  // The insufficient fill is the neutral grey, not a mastery green.
  expect(Math.abs(pixel!.r - 243)).toBeLessThanOrEqual(8)
  expect(Math.abs(pixel!.g - 244)).toBeLessThanOrEqual(8)
  expect(Math.abs(pixel!.b - 246)).toBeLessThanOrEqual(8)

  await hoverHeatCell(page, 3, 0, 1, heatmap.getByText('掌握指数：待诊断', { exact: false }))
  await hoverHeatCell(page, 3, 1, 1, heatmap.getByText('样本不足，暂不作为掌握结论', { exact: false }))
  await expect(heatmap).toContainText('独立样本 2')
  await expectNoHorizontalOverflow(page)
})

test('heatmap truncates long labels but exposes the full name on hover', async ({ page }) => {
  await setup(page, {
    profile: {
      ...profile,
      groups: manyGroups,
      independentSamples: 120,
      assistedSamples: 0,
      unknownSamples: 0,
      sufficient: true,
    },
    history: [profile],
  })
  await page.goto('/stat')
  const heatmap = page.getByTestId('mastery-heatmap')
  await expect(heatmap).toBeVisible()

  await heatmap.locator('.chart-canvas').scrollIntoViewIfNeeded()
  const canvasBox = await boxOf(heatmap.locator('.chart-canvas'))
  expect(canvasBox.height).toBeGreaterThan(400)
  await expectCanvasMatchesContainer(page, 'mastery-heatmap')
  await expectChartFrameLayout(page, 'mastery-heatmap')

  // The long first row is sorted first by priority. Hover its truncated axis
  // label; the card tooltip must reveal the complete knowledge point name.
  const plotHeight = canvasBox.height - HEAT_GRID.top - HEAT_GRID.bottom
  await heatmap.locator('.chart-canvas').hover({
    position: { x: 55, y: HEAT_GRID.top + plotHeight / 12 / 2 },
  })
  await expect(heatmap.getByText(longPoint, { exact: true })).toBeVisible()

  const before = await boxOf(heatmap.locator('.chart-canvas'))
  await selectSubject(page, '数据结构')
  await expect
    .poll(async () => (await boxOf(heatmap.locator('.chart-canvas'))).height)
    .toBeLessThan(before.height - 20)
  await expectCanvasMatchesContainer(page, 'mastery-heatmap')
  await expectChartFrameLayout(page, 'mastery-heatmap')
  await expectNoHorizontalOverflow(page)
})

test('learning profile handles empty data and a chart empty-to-data transition', async ({ page }) => {
  const emptyProfile = {
    ...profile,
    groups: [],
    independentSamples: 0,
    assistedSamples: 0,
    unknownSamples: 0,
    sufficient: false,
  }
  await setup(page, {
    profiles: [emptyProfile, undiagnosedProfile, profile, undiagnosedProfile],
    history: [profile],
  })
  await page.goto('/stat')

  const panel = page.getByTestId('learning-profile')
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('尚未建立知识点画像')
  await expect(page.getByTestId('mastery-heatmap')).toHaveCount(0)
  await expect(page.getByTestId('evidence-scatter')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  // All knowledge points are still undiagnosed: the scatter frame stays empty
  // while the heatmap remains available with textual "未诊断" cells.
  await panel.getByRole('button', { name: '刷新' }).click()
  await expect(page.getByTestId('mastery-heatmap')).toBeVisible()
  const scatter = page.getByTestId('evidence-scatter')
  await expect(scatter).toContainText('暂无独立证据')
  await expect(scatter.locator('canvas')).toHaveCount(0)

  // Empty → non-empty inside the same ChartFrame.
  await panel.getByRole('button', { name: '刷新' }).click()
  await expect(scatter.locator('canvas')).toHaveCount(1)
  await expectChartFrameLayout(page, 'evidence-scatter')
  await expectCanvasMatchesContainer(page, 'evidence-scatter')

  // Non-empty → empty disposes the canvas instead of leaving a stale drawing.
  await panel.getByRole('button', { name: '刷新' }).click()
  await expect(scatter).toContainText('暂无独立证据')
  await expect(scatter.locator('canvas')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)
})

test('learning profile stays inside the mobile viewport', async ({ page }, info) => {
  await setup(page)
  await page.goto('/stat')
  await expect(page.getByTestId('mastery-heatmap')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  if (info.project.name === 'mobile') {
    await expectChartFrameLayout(page, 'mastery-heatmap')
    await expectChartFrameLayout(page, 'evidence-scatter')
  }
})
