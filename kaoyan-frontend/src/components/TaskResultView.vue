<template>
  <section class="task-result" aria-live="polite">
    <el-alert v-if="task.status === 'FAILED'" type="error" :closable="false" :title="task.errorMessage || '任务失败，请稍后重试'" />
    <el-alert v-else-if="task.status === 'CANCELLED'" type="info" :closable="false" title="已停止生成" />
    <template v-else-if="result">
      <div v-if="result.outcome !== 'COMPLETED'" class="meta">
        <el-tag>{{ result.retrievalStatus && retrievalLabels[result.retrievalStatus] || outcomeLabels[result.outcome] }}</el-tag>
      </div>
      <SafeMarkdown :content="result.answer" :allowed-urls="result.references?.map(source => source.url).filter(url => !!safeUrl(url))" />
      <div v-if="citation?.checked" class="grounding">
        <el-tag size="small" :type="citationType(citation?.status)">{{ citationLabel(citation?.status) }}</el-tag>
        <span class="muted">引用支持度 {{ Math.round((citation?.ratio ?? 0) * 100) }}%（{{ citation?.supported ?? 0 }}/{{ citation?.checked ?? 0 }} 条结论）</span>
        <details v-if="citation?.items?.length" class="claim-list">
          <summary>逐条结论与来源（{{ citation?.supported ?? 0 }}/{{ citation?.checked ?? 0 }} 条已核实）</summary>
          <ul>
            <li v-for="(item, index) in citation?.items ?? []" :key="index">
              <el-tag size="small" :type="item.supported ? 'success' : 'danger'">{{ item.supported ? '已核实' : '未核实' }}</el-tag>
              <span>{{ item.text }}</span>
              <span v-if="item.sourceIds?.length" class="muted">（{{ item.sourceIds.map(sourceLabel).join('、') }}）</span>
              <span v-if="item.reason" class="muted">· {{ reasonLabel(item.reason) }}</span>
            </li>
          </ul>
        </details>
        <details v-else-if="citation?.unsupported?.length">
          <summary>未充分核实的结论（{{ citation?.unsupported?.length }}）</summary>
          <ul><li v-for="(item, index) in citation?.unsupported ?? []" :key="index">{{ item.text }}<span class="muted">（{{ reasonLabel(item.reason) }}）</span></li></ul>
        </details>
      </div>
      <div v-if="result.evidence?.length" class="source"><strong>学习依据</strong><p v-for="item in result.evidence" :key="item.ref"><router-link v-if="resourceRoute(item.resource)" :to="resourceRoute(item.resource)!">{{ item.ref }} · {{ item.title }}</router-link><span v-else>{{ item.ref }} · {{ item.title }}</span> · {{ item.locator || '原文位置未记录' }} · {{ item.version || '版本未记录' }}<template v-if="item.matchMethod"><br><span class="match-label">{{ item.matchMethod === 'LABEL' ? '知识点匹配' : '语义相关' }} · {{ item.matchTopic }}</span><br>{{ item.summary }}</template></p></div>
      <el-alert v-if="result.notice || result.explanationMode === 'fallback'" type="warning" :closable="false" :title="result.notice || 'AI解释暂不可用，已保留资料与规则结果。'" />
      <ul v-if="result.followUp?.length"><li v-for="item in result.followUp" :key="item">{{ item }}</li></ul>
      <article v-for="(candidate, index) in result.candidates" :key="candidate.programId" class="candidate">
        <h3>{{ index + 1 }}. {{ candidate.school }} · {{ candidate.major }}</h3>
        <p>{{ candidate.college }} · {{ candidate.year }}年 · {{ candidate.degreeType === 'academic' ? '学硕' : '专硕' }} · {{ candidate.region }}</p>
        <p>初试科目代码：{{ candidate.examSubjects.join(' / ') }}</p>
        <div><el-tag v-for="condition in candidate.matchedConditions" :key="condition" size="small">{{ condition }}</el-tag></div>
        <p class="answer">{{ candidate.explanation }}</p>
        <p v-for="check in candidate.pendingChecks" :key="check" class="muted">待确认：{{ check }}</p>
      </article>
      <p v-if="result.coverage" class="muted">资料覆盖：{{ result.coverage }}</p>
      <p v-if="result.accuracy !== undefined">本次有效作答正确率：{{ result.accuracy }}%（不代表考试能力）</p>
      <p v-if="result.weakPoints?.length">本次错题涉及：{{ result.weakPoints.join('、') }}</p>
      <details v-if="result.references?.length" open>
        <summary>查看依据（{{ result.references.length }}）</summary>
        <div v-for="source in result.references" :key="source.id" class="source">
          <a v-if="safeUrl(source.url)" :href="safeUrl(source.url)" target="_blank" rel="noopener noreferrer">{{ source.title }}</a>
          <strong v-else>{{ source.title }}</strong>
          <p>{{ source.locator }} · {{ source.version }} · 核验 {{ source.retrievedAt }}</p>
          <p>{{ source.excerpt }}</p>
        </div>
      </details>
    </template>
    <template v-else-if="task.resultPayload">
      <el-alert type="warning" :closable="false" title="旧格式历史记录，未经过本轮来源校验，仅供回顾" />
      <pre class="answer">{{ JSON.stringify(task.resultPayload, null, 2) }}</pre>
    </template>
    <el-empty v-else description="处理中，请稍后刷新任务历史" />
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { Task } from '@/types/api'
import SafeMarkdown from '@/components/SafeMarkdown.vue'
import { resourceRoute, safeSourceUrl } from '@/utils/assistant-resource'
const props = defineProps<{ task: Task }>()
const result = computed(() => {
  const value = props.task.resultPayload
  return value?.outcome && value.explanationMode ? value : null
})
const outcomeLabels = { COMPLETED: '已完成', NEEDS_INPUT: '需补充条件', UNSUPPORTED: '资料未覆盖' }
const retrievalLabels = { READY: '', BUILDING: '题目索引准备中', BUSY: '题目索引准备中', FAILED: '题目索引构建失败', UNAVAILABLE: '题目检索暂不可用' }
const citation = computed(() => result.value?.citationSupport)
const sourceLabels = computed(() => {
  const labels: Record<string, string> = {}
  ;(result.value?.references ?? []).forEach((reference, index) => { labels[reference.id] = `S${index + 1}` })
  return labels
})
const citationLabels: Record<string, string> = {
  SUPPORTED: '引用已核实', PARTIAL: '部分引用待核对', UNSUPPORTED: '引用未通过核对', NOT_CHECKED: '未做引用核对',
}
const reasonLabels: Record<string, string> = {
  low_overlap: '与原文重合不足', no_overlap: '原文无对应内容', number_mismatch: '数字与原文不一致',
  unknown_source: '引用编号无效', empty_claim: '空结论', missing_excerpt: '原文缺失',
}
function citationType(status?: string): 'success' | 'warning' | 'danger' | 'info' {
  return status === 'SUPPORTED' ? 'success' : status === 'PARTIAL' ? 'warning' : status === 'UNSUPPORTED' ? 'danger' : 'info'
}
function citationLabel(status?: string) { return status ? citationLabels[status] || status : '未做引用核对' }
function reasonLabel(reason: string) { return reasonLabels[reason] || reason }
function sourceLabel(id: string) { return sourceLabels.value[id] || id }
function safeUrl(value: string) { return safeSourceUrl(value) }
</script>
<style scoped>
.match-label { display:inline-block; margin:4px 0; padding:2px 6px; border:1px solid var(--c-line); border-radius:4px; color:var(--c-primary); background:var(--c-primary-light); font-size:12px; white-space:normal }
.task-result { overflow-wrap: anywhere; }
.meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.grounding { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
.grounding details { width: 100%; }
.grounding ul { margin: 6px 0 0; padding-left: 20px; font-size: 13px; }
.claim-list li { margin: 6px 0; line-height: 1.6; }
.answer { white-space: pre-wrap; line-height: 1.8; }
.candidate, .source { padding: 16px; border: 1px solid var(--c-line); border-radius: 10px; margin: 14px 0; }
.candidate h3 { margin: 0 0 10px; }
.candidate .el-tag { margin: 0 6px 6px 0; }
.source p, .muted { color: var(--c-ink-2); font-size: 13px; }
summary { cursor: pointer; font-weight: 600; }
</style>
