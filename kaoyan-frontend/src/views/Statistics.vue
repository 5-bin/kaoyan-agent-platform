<template>
  <div class="page">
    <LearningProfilePanel />
    <div class="page-head">
      <h2 class="page-title">学习统计</h2>
      <ExportButton :source="{ source: 'LEARNING_REPORT' }" label="导出学情报告" />
      <p class="page-sub">近30天（含今天，上海日期）有效已提交作答 · {{ stats?.from }} 至 {{ stats?.to }}</p>
    </div>
    <div class="stats">
      <div class="card stat"><div class="num">{{ stats?.questionCount ?? 0 }}</div><div class="lbl">有效作答次数</div></div>
      <div class="card stat"><div class="num" style="color:var(--c-success)">{{ stats?.correctCount ?? 0 }}</div><div class="lbl">正确次数</div></div>
      <div class="card stat"><div class="num" style="color:var(--c-primary)">{{ stats?.questionCount && stats.accuracy != null ? Math.round(stats.accuracy * 100) : '暂无作答' }}<span v-if="stats?.questionCount" class="unit">%</span></div><div class="lbl">正确率</div></div>
    </div>
    <p>去重题数：{{ stats?.uniqueQuestions ?? 0 }} · 当前错题标记：{{ stats?.wrongCount ?? 0 }} · 学习时长：未记录</p>
    <p>区间统计按有效提交次数计算；启用学情后，画像按去重独立证据计算，二者分母不同。</p>
    <div class="card" style="padding:20px">
      <div ref="chartEl" style="height:340px"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ExportButton from '@/components/ExportButton.vue'
import LearningProfilePanel from '@/components/LearningProfilePanel.vue'
import { onMounted, onUnmounted, ref } from 'vue'
import echarts, { type EChartsInstance } from '@/lib/echarts'
import { getLearningStat, type LearningStat } from '@/api/stat'
import { useAssistantPage } from '@/composables/assistant-page'
const stats = ref<LearningStat>()
const chartEl = ref<HTMLDivElement>()
let chart: EChartsInstance | undefined
async function load() {
  stats.value = await getLearningStat()
  if (!chartEl.value) return
  chart ??= echarts.init(chartEl.value)
  chart.setOption({ tooltip: { trigger: 'axis' }, grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: stats.value.daily.map(day => day.statDate) },
    yAxis: { type: 'value', minInterval: 1 }, series: [{ name: '有效作答次数', type: 'line', data: stats.value.daily.map(day => day.questionCount) }] })
}
useAssistantPage(() => ({ page: 'stat', from: stats.value?.from, to: stats.value?.to }), load)
const resize = () => chart?.resize()
onMounted(() => { void load(); window.addEventListener('resize', resize) })
onUnmounted(() => { chart?.dispose(); window.removeEventListener('resize', resize) })
</script>

<style scoped>
.stats { display: grid; grid-template-columns: repeat(3,1fr); gap:16px; margin-bottom:16px; }
.stat { padding:20px; }
.stat .num { font-size:28px; font-weight:700; }
.stat .num .unit { font-size:14px; color:var(--c-ink-2); }
.stat .lbl { color:var(--c-ink-2); margin-top:4px; font-size:13px; }
</style>
