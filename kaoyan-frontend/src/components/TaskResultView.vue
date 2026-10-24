<template>
  <section class="task-result" aria-live="polite">
    <el-alert v-if="task.status === 'FAILED'" type="error" :closable="false" :title="task.errorMessage || '任务失败，请稍后重试'" />
    <el-alert v-else-if="task.status === 'CANCELLED'" type="info" :closable="false" title="已停止生成" />
    <template v-else-if="result">
      <div v-if="result.outcome !== 'COMPLETED'" class="meta">
        <el-tag>{{ result.retrievalStatus && retrievalLabels[result.retrievalStatus] || outcomeLabels[result.outcome] }}</el-tag>
      </div>
      <SafeMarkdown :content="result.answer" :allowed-urls="result.references?.map(source => source.url).filter(url => !!safeUrl(url))" />
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
function safeUrl(value: string) { return safeSourceUrl(value) }
</script>
<style scoped>
.match-label { display:inline-block; margin:4px 0; padding:2px 6px; border:1px solid var(--c-line); border-radius:4px; color:var(--c-primary); background:var(--c-primary-light); font-size:12px; white-space:normal }
.task-result { overflow-wrap: anywhere; }
.meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.answer { white-space: pre-wrap; line-height: 1.8; }
.candidate, .source { padding: 16px; border: 1px solid var(--c-line); border-radius: 10px; margin: 14px 0; }
.candidate h3 { margin: 0 0 10px; }
.candidate .el-tag { margin: 0 6px 6px 0; }
.source p, .muted { color: var(--c-ink-2); font-size: 13px; }
summary { cursor: pointer; font-weight: 600; }
</style>
