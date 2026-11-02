<template>
  <section class="weak-panel" data-testid="weak-ranking">
    <header class="weak-head">
      <div>
        <h4>优先补强</h4>
        <p>按蓝图权重 × 未掌握程度排序；样本不足单列，不下“薄弱”结论。</p>
      </div>
    </header>
    <p v-if="weak.length === 0" class="weak-empty">
      {{ allSufficient.length
        ? '当前样本充足的知识点均已达到 80% 以上；可尝试进阶题，或继续补充新知识点样本。'
        : '暂无独立样本达到 5 条的知识点；先完成诊断或练习，再生成补强顺序。' }}
    </p>
    <ol v-else class="weak-list">
      <li v-for="(group, index) in weak" :key="group.knowledgePointId + group.difficulty">
        <span class="rank" aria-hidden="true">{{ index + 1 }}</span>
        <div class="weak-body">
          <div class="weak-title">
            <strong>{{ group.knowledgePoint }}</strong>
            <el-tag size="small" effect="plain">{{ group.subject }}</el-tag>
            <el-tag size="small" type="info" effect="plain">{{ difficultyLabel(group.difficulty) }}</el-tag>
            <el-tag v-if="group.anomaly" size="small" type="danger" effect="plain">近期异常</el-tag>
          </div>
          <div class="weak-bar" aria-hidden="true">
            <span
              :style="{
                width: `${Math.max(4, percentOf(group))}%`,
                background: subjectColor(group.subject),
              }"
            />
          </div>
          <p class="weak-meta">
            掌握 {{ percentOf(group) }}% · 独立样本 {{ group.samples }} · 正确 {{ group.correct }} ·
            辅助 {{ group.assisted }}
          </p>
        </div>
        <button
          type="button"
          class="weak-action"
          :aria-label="`分析知识点 ${group.knowledgePoint}`"
          @click="$emit('analyze', group.knowledgePoint)"
        >
          分析
        </button>
      </li>
    </ol>
    <template v-if="pending.length > 0">
      <h4 class="weak-subhead">待验证（样本不足）</h4>
      <ul class="pending-list">
        <li v-for="group in pending" :key="group.knowledgePointId + group.difficulty">
          <span class="pending-name">{{ group.knowledgePoint }}</span>
          <span class="pending-meta">
            {{ group.subject }} · n={{ group.samples }} ·
            {{ group.samples === 0 ? '未诊断' : '样本不足' }}
          </span>
          <button
            type="button"
            class="weak-action"
            :aria-label="`补充知识点 ${group.knowledgePoint} 的诊断`"
            @click="$emit('analyze', group.knowledgePoint)"
          >
            分析
          </button>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { LearningGroup } from '@/api/learning'
import {
  difficultyLabel,
  masteryBand,
  masteryPercent,
  pendingPoints,
  subjectColor,
  topWeakPoints,
} from './profile-data'

const props = defineProps<{ groups: LearningGroup[] }>()
defineEmits<{ analyze: [point: string] }>()

const allSufficient = computed(() => topWeakPoints(props.groups, 100))
const weak = computed(() => allSufficient.value.filter(group => masteryBand(group) !== 'strong').slice(0, 6))
const pending = computed(() => pendingPoints(props.groups, 4))

function percentOf(group: LearningGroup): number {
  return masteryPercent(group) ?? 0
}
</script>

<style scoped>
.weak-panel {
  padding: 16px;
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  background: var(--c-surface);
}
.weak-head h4,
.weak-subhead {
  margin: 0;
  font-size: 15px;
}
.weak-head p {
  margin: 4px 0 0;
  color: var(--c-ink-2);
  font-size: 12px;
  line-height: 1.5;
}
.weak-list {
  display: grid;
  gap: 10px;
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
}
.weak-list li {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: start;
  padding: 8px 0;
  border-top: 1px solid var(--c-line);
}
.weak-list li:first-child {
  border-top: 0;
  padding-top: 0;
}
.rank {
  display: inline-flex;
  width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--c-primary-light);
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
}
.weak-title {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  font-size: 13px;
}
.weak-bar {
  overflow: hidden;
  height: 6px;
  margin: 7px 0 5px;
  border-radius: 999px;
  background: var(--c-line);
}
.weak-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
}
.weak-meta {
  margin: 0;
  color: var(--c-ink-2);
  font-size: 12px;
  line-height: 1.5;
}
.weak-action {
  padding: 2px 0;
  border: 0;
  background: transparent;
  color: var(--c-primary);
  cursor: pointer;
  font-size: 12px;
}
.weak-action:hover {
  text-decoration: underline;
}
.weak-empty {
  margin: 12px 0 0;
  color: var(--c-ink-3);
  font-size: 13px;
  line-height: 1.6;
}
.weak-subhead {
  margin-top: 18px;
  color: var(--c-ink-2);
  font-size: 13px;
}
.pending-list {
  display: grid;
  gap: 6px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}
.pending-list li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) auto;
  gap: 8px;
  align-items: center;
  padding: 6px 0;
  border-top: 1px solid var(--c-line);
  font-size: 12px;
}
.pending-name {
  overflow: hidden;
  color: var(--c-ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pending-meta {
  color: var(--c-ink-2);
}
@media (max-width: 560px) {
  .pending-list li {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .pending-meta {
    grid-column: 1 / -1;
    grid-row: 2;
  }
}
</style>
