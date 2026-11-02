<template>
  <div class="profile-kpi" data-testid="profile-kpi">
    <article class="kpi-card score">
      <p class="kpi-label">408 参考分</p>
      <p class="kpi-value">
        <template v-if="score == null">证据不足</template>
        <template v-else>{{ score }}<span class="kpi-unit"> / 150</span></template>
      </p>
      <p class="kpi-hint">{{ score == null ? '需审核蓝图与完整分组证据' : '实验性 · 未经整卷校准' }}</p>
    </article>
    <article class="kpi-card coverage">
      <p class="kpi-label">蓝图覆盖</p>
      <p class="kpi-value">{{ coverage }}<span class="kpi-unit">%</span></p>
      <el-progress :percentage="coverage" :show-text="false" :stroke-width="6" />
      <p class="kpi-hint">按知识点权重，不是学习进度</p>
    </article>
    <article class="kpi-card evidence">
      <p class="kpi-label">独立证据</p>
      <p class="kpi-value">{{ evidence.independent }}<span class="kpi-unit"> 条</span></p>
      <p class="kpi-hint">辅助 {{ evidence.assisted }} · 未知 {{ evidence.unknown }}</p>
    </article>
    <article class="kpi-card profile">
      <p class="kpi-label">画像状态</p>
      <p class="kpi-value">{{ profileStatusLabel(profile) }}</p>
      <p class="kpi-hint">
        版本 v{{ profile.revision }} · {{ profile.sufficient ? '样本充足' : '仍有样本不足' }}
      </p>
    </article>
  </div>
  <div class="evidence-composition">
    <div class="composition-head">
      <span>证据构成</span>
      <span class="composition-total">共 {{ evidence.total }} 条</span>
    </div>
    <div v-if="evidence.total > 0" class="evidence-bar" role="img" :aria-label="evidenceLabel">
      <span
        v-for="segment in segments"
        :key="segment.key"
        class="evidence-segment"
        :class="segment.key"
        :style="{ width: `${segment.percent}%` }"
        :title="`${segment.label} ${segment.value} 条`"
      />
    </div>
    <div v-else class="evidence-empty">暂无学习证据；完成一次诊断或练习后会显示。</div>
    <div class="evidence-legend">
      <span v-for="segment in segments" :key="segment.key">
        <i :class="segment.key" />{{ segment.label }} {{ segment.value }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { LearningProfile } from '@/api/learning'
import { coveragePercent, evidenceComposition, profileStatusLabel } from './profile-data'

const props = defineProps<{ profile: LearningProfile }>()

const score = computed(() => {
  if (props.profile.referenceScore == null || !Number.isFinite(props.profile.referenceScore)) return null
  return Math.round(props.profile.referenceScore * 10) / 10
})
const coverage = computed(() => coveragePercent(props.profile))
const evidence = computed(() => evidenceComposition(props.profile))
const segments = computed(() => {
  const total = evidence.value.total
  const rows = [
    { key: 'independent', label: '独立', value: evidence.value.independent },
    { key: 'assisted', label: '辅助', value: evidence.value.assisted },
    { key: 'unknown', label: '未知', value: evidence.value.unknown },
  ]
  return rows.map(row => ({ ...row, percent: total > 0 ? Math.round((row.value / total) * 100) : 0 }))
})
const evidenceLabel = computed(
  () =>
    `证据构成：独立 ${evidence.value.independent} 条，辅助 ${evidence.value.assisted} 条，未知 ${evidence.value.unknown} 条。`,
)
</script>

<style scoped>
.profile-kpi {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.kpi-card {
  padding: 14px 16px;
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  background: var(--c-surface);
}
.kpi-label {
  margin: 0;
  color: var(--c-ink-2);
  font-size: 12px;
}
.kpi-value {
  margin: 6px 0 4px;
  color: var(--c-ink);
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}
.kpi-unit {
  color: var(--c-ink-2);
  font-size: 13px;
  font-weight: 500;
}
.kpi-hint {
  min-height: 18px;
  margin: 4px 0 0;
  color: var(--c-ink-3);
  font-size: 12px;
  line-height: 1.5;
}
.coverage :deep(.el-progress) {
  margin: 6px 0 2px;
}
.evidence-composition {
  margin-top: 12px;
  padding: 12px 16px;
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  background: var(--c-surface);
}
.composition-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--c-ink-2);
  font-size: 12px;
}
.composition-total {
  color: var(--c-ink-3);
}
.evidence-bar {
  display: flex;
  overflow: hidden;
  height: 10px;
  margin: 8px 0;
  border-radius: 999px;
  background: var(--c-line);
}
.evidence-segment {
  height: 100%;
}
.evidence-segment.independent,
.evidence-legend i.independent {
  background: var(--c-primary);
}
.evidence-segment.assisted,
.evidence-legend i.assisted {
  background: #f6c177;
}
.evidence-segment.unknown,
.evidence-legend i.unknown {
  background: #cbd2dc;
}
.evidence-empty {
  margin: 8px 0;
  color: var(--c-ink-3);
  font-size: 12px;
}
.evidence-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--c-ink-2);
  font-size: 12px;
}
.evidence-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.evidence-legend i {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
}
@media (max-width: 900px) {
  .profile-kpi {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 560px) {
  .profile-kpi {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .kpi-card.profile .kpi-value {
    font-size: 18px;
    white-space: nowrap;
  }
}
@media (max-width: 360px) {
  .profile-kpi {
    grid-template-columns: 1fr;
  }
}
</style>
