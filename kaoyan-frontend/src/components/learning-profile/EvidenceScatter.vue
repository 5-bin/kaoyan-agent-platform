<template>
  <ChartFrame
    title="证据散点"
    subtitle="每个点是一个知识点；横轴独立样本数，纵轴掌握指数；点越大表示蓝图权重越高。"
    :option="option"
    :empty="plotted.length === 0"
    empty-text="暂无独立证据；先完成诊断或练习后再看证据分布。"
    :height="340"
    :summary="summary"
    test-id="evidence-scatter"
  >
    <template #legend>
      <div class="scatter-legend" data-testid="scatter-legend" aria-label="散点图图例">
        <button
          v-for="subject in legendSubjects"
          :key="subject"
          type="button"
          class="legend-subject"
          :aria-label="`显示${subject}证据`"
          :aria-pressed="legendSelected[subject] !== false"
          @click="toggleSubject(subject)"
        >
          <i :style="{ background: subjectColor(subject) }" />{{ subject }}
        </button>
        <span class="legend-note">点大小 = 蓝图权重</span>
        <span class="legend-note">红描边 = 近期异常</span>
      </div>
    </template>
  </ChartFrame>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { LearningGroup } from '@/api/learning'
import type { EChartsOption } from '@/lib/echarts'
import ChartFrame from './ChartFrame.vue'
import {
  difficultyLabel,
  escapeHtml,
  masteryPercent,
  SAMPLE_THRESHOLD,
  subjectColor,
} from './profile-data'

const props = defineProps<{ groups: LearningGroup[] }>()
const legendSelected = ref<Record<string, boolean>>({})

function toggleSubject(subject: string): void {
  legendSelected.value = {
    ...legendSelected.value,
    [subject]: legendSelected.value[subject] === false,
  }
}

const plotted = computed(() =>
  props.groups.filter(group => group.samples > 0 && group.masteryIndex != null),
)
const undiagnosed = computed(() => props.groups.filter(group => group.samples <= 0).length)
const maxSamples = computed(() => Math.max(0, ...plotted.value.map(group => group.samples)))
const legendSubjects = computed(() => [...new Set(plotted.value.map(group => group.subject))])
const summary = computed(
  () =>
    `横轴为独立样本数，纵轴为掌握指数；共 ${plotted.value.length} 个知识点有独立证据，${undiagnosed.value} 个尚未诊断；虚线为独立样本 ${SAMPLE_THRESHOLD} 条和掌握指数 60% 的参考线。`,
)

function pointSize(group: LearningGroup): number {
  const weight = Math.max(0, Math.min(1, group.weight ?? 0))
  return Math.min(26, 9 + weight * 40)
}

function seriesForSubject(subject: string, rows: LearningGroup[]): any {
  return {
    name: subject,
    type: 'scatter',
    data: rows.map(group => ({
      value: [group.samples, masteryPercent(group) ?? 0],
      group,
      symbolSize: pointSize(group),
      itemStyle: {
        color: subjectColor(subject),
        borderColor: group.anomaly ? '#dc2626' : '#ffffff',
        borderWidth: group.anomaly ? 3 : 1,
        opacity: 0.9,
      },
    })),
    emphasis: { focus: 'series', scale: 1.15 },
  }
}

const option = computed<EChartsOption>(() => {
  const bySubject = new Map<string, LearningGroup[]>()
  for (const group of plotted.value) {
    const rows = bySubject.get(group.subject) ?? []
    rows.push(group)
    bySubject.set(group.subject, rows)
  }
  const series = [...bySubject.entries()].map(([subject, rows], index) => {
    const value = seriesForSubject(subject, rows)
    if (index === 0) {
      value.markLine = {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#8f959e' },
        label: { color: '#8f959e', fontSize: 11 },
        data: [
          { xAxis: SAMPLE_THRESHOLD, label: { formatter: `n=${SAMPLE_THRESHOLD}`, position: 'insideEndBottom' } },
          { yAxis: 60, label: { formatter: '60%', position: 'insideEndTop' } },
        ],
      }
    }
    return value
  })
  return {
    animation: false,
    legend: { show: false, selected: legendSelected.value },
    tooltip: {
      trigger: 'item',
      confine: true,
      formatter: (params: any) => {
        const group = params?.data?.group as LearningGroup | undefined
        if (!group) return ''
        const percent = masteryPercent(group)
        return [
          `<strong>${escapeHtml(group.knowledgePoint)}</strong> · ${escapeHtml(group.subject)}`,
          `${difficultyLabel(group.difficulty)} · 独立样本 ${group.samples}`,
          `正确 ${group.correct} · 辅助 ${group.assisted} · 未知 ${group.unknown}`,
          percent == null ? '掌握指数：待诊断' : `掌握指数：${percent}%（规则平滑值）`,
          group.samples < SAMPLE_THRESHOLD ? '<span style="color:#8f959e">样本不足，暂不作为掌握结论</span>' : '',
          group.anomaly ? '<span style="color:#dc2626">近期表现异常，建议复测</span>' : '',
        ]
          .filter(Boolean)
          .join('<br/>')
      },
    },
    grid: { left: 52, right: 28, top: 20, bottom: 64 },
    xAxis: {
      type: 'value',
      name: '独立样本数',
      nameLocation: 'middle',
      nameGap: 36,
      nameTextStyle: { color: '#646a73', fontSize: 11, align: 'center' },
      min: 0,
      max: Math.max(10, maxSamples.value + 1),
      minInterval: 1,
      axisLabel: { color: '#646a73' },
      splitLine: { lineStyle: { color: '#eef0f3' } },
    },
    yAxis: {
      type: 'value',
      name: '掌握指数（%）',
      nameGap: 14,
      nameTextStyle: { color: '#646a73', fontSize: 11 },
      min: 0,
      max: 100,
      axisLabel: { color: '#646a73' },
      splitLine: { lineStyle: { color: '#eef0f3' } },
    },
    series,
  }
})
</script>

<style scoped>
.scatter-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  align-items: center;
}
.legend-subject,
.legend-note {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}
.legend-subject i {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
}
.legend-subject {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.legend-subject[aria-pressed='false'] {
  opacity: 0.45;
  text-decoration: line-through;
}
.legend-subject:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 3px;
}
.legend-note {
  color: var(--c-ink-3);
}
</style>
