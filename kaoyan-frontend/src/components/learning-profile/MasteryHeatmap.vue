<template>
  <ChartFrame
    title="知识点掌握热力图"
    :subtitle="`按知识点 × 难度；独立样本少于 ${SAMPLE_THRESHOLD} 条只标样本不足，不判定掌握。`"
    :option="option"
    :empty="!hasData"
    empty-text="所选科目暂无知识点画像；完成诊断或练习后生成。"
    :height="height"
    :summary="summary"
    test-id="mastery-heatmap"
  >
    <template #actions>
      <el-select v-model="subject" size="small" aria-label="筛选科目" class="subject-filter">
        <el-option v-for="item in subjectOptions" :key="item" :label="item" :value="item" />
      </el-select>
    </template>
    <template #legend>
      <div class="heat-legend" data-testid="heatmap-legend" aria-label="掌握档位图例">
        <span v-for="band in legendBands" :key="band">
          <i
            :class="{ 'is-insufficient': band === 'undiagnosed' || band === 'insufficient' }"
            :style="{ background: BAND_FILLS[band] }"
          />{{ bandLabel(band) }}
        </span>
      </div>
    </template>
  </ChartFrame>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { LearningGroup } from '@/api/learning'
import type { EChartsOption } from '@/lib/echarts'
import ChartFrame from './ChartFrame.vue'
import {
  bandColor,
  bandLabel,
  buildHeatmapRows,
  DIFFICULTIES,
  difficultyLabel,
  escapeHtml,
  masteryBand,
  masteryPercent,
  SAMPLE_THRESHOLD,
  SUBJECTS,
  type MasteryBand,
} from './profile-data'

const props = defineProps<{ groups: LearningGroup[] }>()

const MAX_ROWS = 12
const MAX_AXIS_LABEL_CHARS = 9
const GRID = { left: 116, right: 20, top: 16, bottom: 42 }

// Component tooltips receive the original category, even when its label is truncated.
const axisTooltip = {
  show: true,
  formatter: (params: { value?: string | number }): string => escapeHtml(String(params.value ?? '')),
}

const BAND_VALUES: Record<MasteryBand, number> = {
  undiagnosed: 0,
  insufficient: 1,
  weak: 2,
  developing: 3,
  steady: 4,
  strong: 5,
}

const BAND_FILLS: Record<MasteryBand, string> = {
  undiagnosed: '#f3f4f6',
  insufficient: '#f3f4f6',
  weak: bandColor('weak'),
  developing: bandColor('developing'),
  steady: bandColor('steady'),
  strong: bandColor('strong'),
}

const subject = ref('全部')
const subjectOptions = computed(() => {
  const present = SUBJECTS.filter(item => props.groups.some(group => group.subject === item))
  const extra = [...new Set(props.groups.map(group => group.subject))].filter(
    item => !SUBJECTS.includes(item as (typeof SUBJECTS)[number]),
  )
  return ['全部', ...present, ...extra]
})
watch(subjectOptions, options => {
  if (!options.includes(subject.value)) subject.value = '全部'
})

const heatmap = computed(() => buildHeatmapRows(props.groups, subject.value, MAX_ROWS))
const hasData = computed(() => heatmap.value.rows.length > 0)
const height = computed(() =>
  Math.max(190, Math.min(560, heatmap.value.rows.length * 36 + 62)),
)
const legendBands: MasteryBand[] = [
  'weak',
  'developing',
  'steady',
  'strong',
  'insufficient',
  'undiagnosed',
]
const summary = computed(() => {
  if (!heatmap.value.rows.length) return '所选科目暂无知识点画像。'
  const suffix = heatmap.value.truncated
    ? `仅显示优先级最高的 ${heatmap.value.rows.length} 个知识点，另有 ${heatmap.value.truncated} 个见下方数据表。`
    : `共 ${heatmap.value.total} 个知识点。`
  return `${suffix} 灰色虚框表示样本不足或未诊断；颜色只表示规则掌握档位，不是概率。`
})

function shortenPoint(point: string): string {
  const chars = [...point]
  if (chars.length <= MAX_AXIS_LABEL_CHARS) return point
  return `${chars.slice(0, MAX_AXIS_LABEL_CHARS).join('')}…`
}

const renderModel = computed(() => {
  const cells: any[] = []
  heatmap.value.rows.forEach((row, y) => {
    row.cells.forEach((cell, x) => {
      const group = cell.group
      if (!group) return
      const percent = masteryPercent(group)
      const insufficient = percent == null || group.samples < SAMPLE_THRESHOLD
      const band = masteryBand(group)
      cells.push({
        value: [x, y, BAND_VALUES[band]],
        group,
        itemStyle: {
          color: BAND_FILLS[band],
          borderColor: insufficient ? '#cbd2dc' : '#ffffff',
          borderWidth: 1,
          borderType: insufficient ? 'dashed' : 'solid',
        },
        label: {
          show: true,
          color: insufficient ? '#8f959e' : '#1f2329',
          fontSize: 10,
          lineHeight: 14,
          formatter:
            percent == null
              ? '未诊断'
              : insufficient
                ? `n=${group.samples}\n样本不足`
                : `${percent}%\nn=${group.samples}`,
        },
      })
    })
  })
  return { cells }
})

const option = computed<EChartsOption>(() => ({
  animation: false,
  // ECharts requires a visualMap for every heatmap series. It is intentionally
  // hidden because the accessible legend lives in the card; the pieces mirror
  // the existing rule bands and the grey undiagnosed/insufficient fills.
  visualMap: {
    show: false,
    type: 'piecewise',
    seriesIndex: 0,
    dimension: 2,
    pieces: (Object.keys(BAND_VALUES) as MasteryBand[]).map(band => ({
      value: BAND_VALUES[band],
      label: bandLabel(band),
      color: BAND_FILLS[band],
    })),
  },
  tooltip: {
    trigger: 'item',
    confine: true,
    extraCssText: 'max-width: min(260px, calc(100vw - 96px)); white-space: normal; overflow-wrap: anywhere;',
    formatter: (params: any) => {
      const group = params?.data?.group as LearningGroup | undefined
      if (!group) return ''
      const percent = masteryPercent(group)
      return [
        `<strong>${escapeHtml(group.knowledgePoint)}</strong> · ${escapeHtml(group.subject)}`,
        `${difficultyLabel(group.difficulty)} · ${bandLabel(masteryBand(group))}`,
        `独立样本 ${group.samples} · 正确 ${group.correct}`,
        `辅助 ${group.assisted} · 未知 ${group.unknown}`,
        percent == null ? '掌握指数：待诊断' : `掌握指数：${percent}%（规则平滑值）`,
        group.samples < SAMPLE_THRESHOLD ? '样本不足，暂不作为掌握结论' : '',
        group.anomaly ? '<span style="color:#dc2626">近期表现异常，建议复测</span>' : '',
      ]
        .filter(Boolean)
        .join('<br/>')
    },
  },
  grid: GRID,
  xAxis: {
    type: 'category',
    data: DIFFICULTIES.map(item => item.label),
    splitArea: { show: true },
    axisLabel: { color: '#646a73' },
  },
  yAxis: {
    type: 'category',
    data: heatmap.value.rows.map(row => row.point),
    inverse: true,
    tooltip: axisTooltip,
    splitArea: { show: true },
    axisLabel: {
      color: '#646a73',
      width: 104,
      margin: 10,
      overflow: 'truncate',
      fontSize: 11,
      formatter: (value: string) => shortenPoint(value),
    },
  },
  series: [
    {
      type: 'heatmap',
      data: renderModel.value.cells,
      label: { show: true },
      emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(31,35,41,.18)' } },
    },
  ],
}))

</script>

<style scoped>
.subject-filter {
  width: 150px;
}
.heat-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  align-items: center;
}
.heat-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}
.heat-legend i {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
}
.heat-legend i.is-insufficient {
  border: 1px dashed var(--c-ink-3);
}
@media (max-width: 560px) {
  .subject-filter {
    width: 124px;
  }
}
</style>
