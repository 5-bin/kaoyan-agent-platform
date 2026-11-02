<template>
  <ChartFrame
    title="画像变化"
    subtitle="按画像版本展示参考分与蓝图覆盖；版本稀疏，不代表连续时间趋势。"
    :option="option"
    :empty="points.length < 2"
    empty-text="暂无足够历史版本；完成更多诊断或练习后显示变化。"
    :height="230"
    :summary="summary"
    test-id="profile-history"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { LearningProfile } from '@/api/learning'
import type { EChartsOption } from '@/lib/echarts'
import ChartFrame from './ChartFrame.vue'
import { buildHistoryPoints, formatDateTime } from './profile-data'

const props = defineProps<{ history: LearningProfile[] }>()
const points = computed(() => buildHistoryPoints(props.history))
const summary = computed(() =>
  points.value.length < 2
    ? '暂无足够历史版本。'
    : `共 ${points.value.length} 个画像版本；参考分为实验性，覆盖率按蓝图权重。`,
)

const option = computed<EChartsOption>(() => ({
  animation: false,
  legend: { top: 0, left: 0, textStyle: { color: '#646a73', fontSize: 11 } },
  tooltip: {
    trigger: 'axis',
    confine: true,
    formatter: (params: any) => {
      const rows = Array.isArray(params) ? params : [params]
      const point = points.value[rows[0]?.dataIndex ?? -1]
      if (!point) return ''
      const score = rows.find((row: any) => row.seriesName === '408 参考分')
      const coverage = rows.find((row: any) => row.seriesName === '蓝图覆盖')
      return [
        `<strong>${point.label}</strong>`,
        point.updatedAt ? `更新 ${formatDateTime(point.updatedAt)}` : '',
        score?.value == null ? '参考分：暂无' : `参考分：${score.value} / 150（实验性）`,
        coverage?.value == null ? '' : `蓝图覆盖：${Math.round(coverage.value)}%`,
      ]
        .filter(Boolean)
        .join('<br/>')
    },
  },
  grid: { left: 42, right: 42, top: 46, bottom: 30 },
  xAxis: {
    type: 'category',
    data: points.value.map(point => point.label),
    axisLabel: { color: '#646a73' },
    boundaryGap: false,
  },
  yAxis: [
    {
      type: 'value',
      min: 0,
      max: 150,
      axisLabel: { color: '#646a73' },
      splitLine: { lineStyle: { color: '#eef0f3' } },
    },
    {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { color: '#646a73', formatter: '{value}%' },
      splitLine: { show: false },
    },
  ],
  series: [
    {
      name: '408 参考分',
      type: 'line',
      connectNulls: false,
      symbolSize: 6,
      data: points.value.map(point => point.score),
      lineStyle: { color: '#3b6cff', width: 2 },
      itemStyle: { color: '#3b6cff' },
    },
    {
      name: '蓝图覆盖',
      type: 'line',
      yAxisIndex: 1,
      connectNulls: false,
      symbolSize: 5,
      data: points.value.map(point => Math.round(point.coverage * 100)),
      lineStyle: { color: '#0f9d8a', width: 2, type: 'dashed' },
      itemStyle: { color: '#0f9d8a' },
    },
  ],
}))
</script>
