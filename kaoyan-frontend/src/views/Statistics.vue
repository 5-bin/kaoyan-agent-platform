<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">学习统计</h2>
      <p class="page-sub">近 30 天学习情况</p>
    </div>
    <div class="stats">
      <div class="card stat"><div class="num">{{ stats.questionCount }}</div><div class="lbl">累计做题</div></div>
      <div class="card stat"><div class="num" style="color:var(--c-success)">{{ stats.correctCount }}</div><div class="lbl">累计正确</div></div>
      <div class="card stat"><div class="num" style="color:var(--c-primary)">{{ accuracy }}<span class="unit">%</span></div><div class="lbl">正确率</div></div>
    </div>
    <div class="card" style="padding:20px">
      <div ref="chartEl" style="height:340px"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import * as echarts from 'echarts'
import { getRangeStat, getTodayStat } from '@/api/stat'

const stats = reactive({ questionCount: 0, correctCount: 0 })
const chartEl = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null
const accuracy = computed(() =>
  stats.questionCount ? Math.round((stats.correctCount / stats.questionCount) * 100) : 0)

onMounted(async () => {
  const today: any = await getTodayStat().catch(() => null)
  if (today) { stats.questionCount = today.questionCount; stats.correctCount = today.correctCount }
  const to = new Date()
  const from = new Date(Date.now() - 30 * 864e5)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  const range: any[] = await getRangeStat({ from: fmt(from), to: fmt(to) }).catch(() => [])
  if (chartEl.value) {
    chart = echarts.init(chartEl.value)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 30, right: 20, top: 20, bottom: 30 },
      xAxis: { type: 'category', data: range.map((r: any) => r.statDate), axisLine: { lineStyle: { color: '#e5e8ee' } } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0f2f5' } } },
      series: [{
        name: '做题数', type: 'line', smooth: true,
        data: range.map((r: any) => r.questionCount),
        lineStyle: { color: '#3b6cff', width: 3 },
        itemStyle: { color: '#3b6cff' },
        areaStyle: { color: 'rgba(59,108,255,.12)' }
      }]
    })
  }
})
onUnmounted(() => chart?.dispose())
</script>

<style scoped>
.stats { display: grid; grid-template-columns: repeat(3,1fr); gap:16px; margin-bottom:16px; }
.stat { padding:20px; }
.stat .num { font-size:28px; font-weight:700; }
.stat .num .unit { font-size:14px; color:var(--c-ink-2); }
.stat .lbl { color:var(--c-ink-2); margin-top:4px; font-size:13px; }
</style>
