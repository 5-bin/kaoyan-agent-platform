<template>
  <section class="subject-panel" data-testid="subject-cards">
    <header class="subject-head">
      <h4>科目证据</h4>
      <p>独立正确 / 独立错误 / 辅助 / 未知分段；分母是证据条数，不是题目总数。</p>
    </header>
    <div v-if="summaries.length" class="subject-grid">
      <article v-for="summary in summaries" :key="summary.subject" class="subject-card">
        <header>
          <span class="subject-dot" :style="{ background: subjectColor(summary.subject) }" />
          <h5>{{ summary.subject }}</h5>
          <span class="subject-count">{{ summary.diagnosed }}/{{ summary.total }} 有证据</span>
        </header>
        <div
          class="subject-bar"
          role="img"
          :aria-label="`${summary.subject}证据构成：独立正确 ${summary.correct}，独立错误 ${summary.wrong}，辅助 ${summary.assisted}，未知 ${summary.unknown}`"
        >
          <span
            v-for="segment in segments(summary)"
            :key="segment.key"
            class="subject-segment"
            :class="segment.key"
            :style="{ width: `${segment.percent}%` }"
            :title="`${segment.label} ${segment.value} 条`"
          />
        </div>
        <p class="subject-legend">
          独立正确 {{ summary.correct }} · 独立错误 {{ summary.wrong }} · 辅助
          {{ summary.assisted }} · 未知 {{ summary.unknown }}
        </p>
        <p class="subject-meta">
          蓝图覆盖 {{ Math.round(summary.coverage * 100) }}% · 样本不足 {{ summary.insufficient }} 个知识点
        </p>
        <p v-if="summary.weakest" class="subject-weak">
          建议先看：{{ summary.weakest.knowledgePoint }}（n={{ summary.weakest.samples }}）
        </p>
        <p v-else-if="summary.sufficient > 0" class="subject-weak muted">
          有证据知识点均达到 80% 以上，可尝试进阶题。
        </p>
        <p v-else class="subject-weak muted">暂无 5 条以上独立样本的知识点。</p>
      </article>
    </div>
    <p v-else class="subject-empty">暂无科目画像。</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { LearningGroup } from '@/api/learning'
import { subjectColor, subjectSummaries, type SubjectSummary } from './profile-data'

const props = defineProps<{ groups: LearningGroup[] }>()
const summaries = computed(() => subjectSummaries(props.groups))

function segments(summary: SubjectSummary) {
  const total = summary.samples + summary.assisted + summary.unknown
  const rows = [
    { key: 'correct', label: '独立正确', value: summary.correct },
    { key: 'wrong', label: '独立错误', value: summary.wrong },
    { key: 'assisted', label: '辅助', value: summary.assisted },
    { key: 'unknown', label: '未知', value: summary.unknown },
  ]
  return rows.map(row => ({ ...row, percent: total > 0 ? Math.round((row.value / total) * 100) : 0 }))
}
</script>

<style scoped>
.subject-panel {
  padding: 16px;
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  background: var(--c-surface);
}
.subject-head h4 {
  margin: 0;
  font-size: 15px;
}
.subject-head p {
  margin: 4px 0 0;
  color: var(--c-ink-2);
  font-size: 12px;
  line-height: 1.5;
}
.subject-grid {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}
.subject-card {
  padding: 10px 12px;
  border: 1px solid var(--c-line);
  border-radius: var(--r-sm);
}
.subject-card header {
  display: flex;
  gap: 6px;
  align-items: center;
}
.subject-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.subject-card h5 {
  flex: 1;
  margin: 0;
  font-size: 13px;
}
.subject-count {
  color: var(--c-ink-3);
  font-size: 11px;
}
.subject-bar {
  display: flex;
  overflow: hidden;
  height: 8px;
  margin: 8px 0 6px;
  border-radius: 999px;
  background: var(--c-line);
}
.subject-segment {
  height: 100%;
}
.subject-segment.correct {
  background: #7fcf9b;
}
.subject-segment.wrong {
  background: #f3b6b6;
}
.subject-segment.assisted {
  background: #f6c177;
}
.subject-segment.unknown {
  background: #cbd2dc;
}
.subject-legend,
.subject-meta,
.subject-weak {
  margin: 0;
  color: var(--c-ink-2);
  font-size: 11px;
  line-height: 1.6;
}
.subject-weak {
  margin-top: 3px;
  color: var(--c-ink);
}
.subject-weak.muted {
  color: var(--c-ink-3);
}
.subject-empty {
  margin: 10px 0 0;
  color: var(--c-ink-3);
  font-size: 13px;
}
</style>
