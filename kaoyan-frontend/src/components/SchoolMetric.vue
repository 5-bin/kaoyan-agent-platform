<template>
  <div class="school-metric">
    <template v-if="metric">
      <strong class="metric-value">{{ metric.year ? `${metric.year}年 ` : '' }}{{ heading }}：{{ valueLabel }}</strong>
      <el-tag v-if="metric.status === 'UNVERIFIED'" type="warning" size="small">第三方·待核实</el-tag>
      <el-tag v-else-if="metric.status === 'OFFICIAL'" type="success" size="small">官方来源</el-tag>
      <p v-if="metric.basis !== 'NOT_APPLICABLE'" class="metric-note">{{ basisLabel[metric.basis] }}</p>
      <p class="metric-note">{{ metric.scopeLabel }}</p>
      <p v-if="metric.notice" class="metric-note">{{ metric.notice }}</p>
      <details v-if="metric.sources.length" class="metric-sources">
        <summary>来源与适用范围（{{ metric.sources.length }}）</summary>
        <div v-for="(source, index) in metric.sources" :key="`${source.url}-${index}`" class="metric-source">
          <a v-if="safeUrl(source.url)" :href="safeUrl(source.url)" target="_blank" rel="noopener noreferrer">{{ source.title }}</a>
          <span v-else>{{ source.title }}（链接不可用）</span>
          <p>{{ source.sourceType === 'THIRD_PARTY' ? '第三方登记，待核实' : '官方来源' }} · 获取于 {{ source.retrievedAt }}</p>
          <p>{{ source.locator }}</p>
        </div>
      </details>
    </template>
    <span v-else>{{ legacyValue == null ? '未收录' : `${legacyYear}年原登记：${legacyValue}${kind === 'enrollment' ? '人' : '分'}` }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AdmissionMetric } from '@/types/api'

const props = defineProps<{
  metric?: AdmissionMetric | null
  kind: 'enrollment' | 'cutoff'
  legacyValue?: number | null
  legacyYear: number
}>()
const heading = computed(() => props.kind === 'enrollment' ? '招生计划' : '复试参考线')
const statusLabel = {
  NOT_PUBLISHED: '未公布', NOT_FOUND: '未找到可靠来源', SCOPE_MISMATCH: '范围不匹配', CONFLICT: '来源冲突'
}
const basisLabel = {
  ORDINARY_EXAM: '统考计划', TOTAL_INCLUDING_RECOMMENDED: '招生总计划（含推免）',
  TOTAL_UNSPECIFIED: '招生总计划（是否含推免未说明）', NOT_APPLICABLE: ''
}
const valueLabel = computed(() => {
  const metric = props.metric
  if (!metric) return '未收录'
  if (metric.value != null && (metric.status === 'OFFICIAL' || metric.status === 'UNVERIFIED')) {
    return `${metric.value}${props.kind === 'enrollment' ? '人' : '分'}`
  }
  return statusLabel[metric.status as keyof typeof statusLabel] || '未找到可靠来源'
})
function safeUrl(value: string): string | undefined {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && !url.username && !url.password ? url.href : undefined
  } catch { return undefined }
}
</script>

<style scoped>
.school-metric { display: grid; gap: 6px; padding: 4px 0; font-size: 13px; }
.metric-value { font-weight: 600; color: var(--c-ink); }
.school-metric :deep(.el-tag) { justify-self: start; }
.metric-note, .metric-source p { margin: 0; color: var(--c-ink-2); line-height: 1.6; }
.metric-sources summary { cursor: pointer; color: var(--c-primary); }
.metric-source { margin-top: 10px; overflow-wrap: anywhere; }
.metric-source a { color: var(--c-primary); }
</style>
