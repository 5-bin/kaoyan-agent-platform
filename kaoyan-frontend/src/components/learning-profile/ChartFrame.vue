<template>
  <section class="chart-frame" :data-testid="testId">
    <header class="chart-head">
      <div class="chart-heading">
        <h4>{{ title }}</h4>
        <p v-if="subtitle" class="chart-subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.actions" class="chart-actions">
        <slot name="actions" />
      </div>
    </header>
    <div v-if="empty" class="chart-empty" role="status">{{ emptyText }}</div>
    <template v-else>
      <div
        ref="chartEl"
        class="chart-canvas"
        :style="{ height: `${height}px` }"
        role="img"
        :aria-label="ariaLabel"
      />
      <div v-if="$slots.legend" class="chart-legend">
        <slot name="legend" />
      </div>
      <p v-if="summary" class="chart-summary">{{ summary }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import echarts, { type EChartsInstance, type EChartsOption } from '@/lib/echarts'

const props = withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    option: EChartsOption
    empty?: boolean
    emptyText?: string
    height?: number
    summary?: string
    testId?: string
  }>(),
  {
    subtitle: '',
    empty: false,
    emptyText: '暂无足够数据',
    height: 320,
    summary: '',
    testId: undefined,
  },
)

const chartEl = ref<HTMLDivElement>()
const ariaLabel = computed(() => props.summary || props.title)

let chart: EChartsInstance | undefined
let observer: ResizeObserver | undefined
let resizeFrame = 0
let disposed = false
let renderVersion = 0
let lastWidth = 0
let lastHeight = 0

function resizeChart(force = false) {
  if (disposed || !chart || !chartEl.value) return
  const width = chartEl.value.clientWidth
  const height = chartEl.value.clientHeight
  if (width <= 0 || height <= 0) return
  if (!force && width === lastWidth && height === lastHeight) return
  lastWidth = width
  lastHeight = height
  // Pass explicit dimensions so a pending layout change cannot leave canvas CSS
  // and the ECharts drawing surface out of sync.
  chart.resize({ width, height, silent: true })
}

function observeChart() {
  if (typeof ResizeObserver === 'undefined' || disposed) return
  observer ??= new ResizeObserver(() => {
    if (disposed || resizeFrame) return
    // Coalesce observer notifications and run after layout, avoiding a resize
    // feedback loop while still catching card width changes.
    resizeFrame = window.requestAnimationFrame(() => {
      resizeFrame = 0
      resizeChart()
    })
  })
  observer.disconnect()
  if (chartEl.value) observer.observe(chartEl.value)
}

function disposeChart() {
  observer?.disconnect()
  if (resizeFrame) {
    window.cancelAnimationFrame(resizeFrame)
    resizeFrame = 0
  }
  chart?.dispose()
  chart = undefined
  lastWidth = 0
  lastHeight = 0
}

async function refresh() {
  const version = ++renderVersion
  await nextTick()
  if (disposed || version !== renderVersion || props.empty) return
  if (!chartEl.value) return
  if (!chart) {
    chart = echarts.init(chartEl.value)
  }
  chart.setOption(props.option, true)
  await nextTick()
  if (disposed || version !== renderVersion) return
  resizeChart(true)
  observeChart()
}

watch(
  () => props.option,
  () => void refresh(),
  { deep: true },
)

watch(
  () => props.height,
  async () => {
    await nextTick()
    resizeChart(true)
  },
)

watch(
  () => props.empty,
  async empty => {
    renderVersion++
    await nextTick()
    if (disposed) return
    if (empty) {
      disposeChart()
      return
    }
    await refresh()
  },
)

onMounted(() => {
  void refresh()
})

onBeforeUnmount(() => {
  disposed = true
  renderVersion++
  disposeChart()
})
</script>

<style scoped>
.chart-frame {
  position: relative;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  background: var(--c-surface);
}
.chart-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 10px 16px;
  margin-bottom: 12px;
}
.chart-heading {
  flex: 1 1 220px;
  min-width: 0;
}
.chart-head h4 {
  margin: 0;
  overflow-wrap: anywhere;
  font-size: 15px;
  line-height: 1.4;
}
.chart-subtitle {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
  color: var(--c-ink-2);
  font-size: 12px;
  line-height: 1.5;
}
.chart-actions {
  flex: 0 0 auto;
  min-width: 0;
  margin-left: auto;
}
.chart-canvas {
  position: relative;
  width: 100%;
  min-width: 0;
}
.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  align-items: center;
  min-width: 0;
  margin-top: 10px;
  color: var(--c-ink-2);
  font-size: 12px;
  line-height: 1.5;
}
.chart-summary {
  margin: 10px 0 0;
  overflow-wrap: anywhere;
  color: var(--c-ink-2);
  font-size: 12px;
  line-height: 1.6;
}
.chart-empty {
  display: flex;
  min-height: 140px;
  align-items: center;
  justify-content: center;
  padding: 20px;
  border: 1px dashed var(--c-line);
  border-radius: var(--r-sm);
  color: var(--c-ink-3);
  font-size: 13px;
  text-align: center;
}
@media (max-width: 560px) {
  .chart-heading {
    flex-basis: 160px;
  }
  .chart-frame {
    padding: 14px;
  }
}
</style>
