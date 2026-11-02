<template>
  <section
    v-if="enabled"
    class="card learning-profile"
    data-testid="learning-profile"
    v-loading="busy"
  >
    <header class="profile-head">
      <div>
        <h3>学情画像</h3>
        <p v-if="profile">
          {{ profileStatusLabel(profile) }} · 画像版本 v{{ profile.revision }} ·
          {{ formatDateTime(profile.updatedAt) }}
        </p>
      </div>
      <el-button size="small" @click="load">刷新</el-button>
    </header>
    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <template v-if="profile">
      <ProfileKpi :profile="profile" />
      <ul v-if="notices.length" class="profile-notices">
        <li v-for="notice in notices" :key="notice">{{ notice }}</li>
      </ul>
      <template v-if="groups.length">
        <div class="profile-charts">
          <MasteryHeatmap :groups="groups" />
          <EvidenceScatter :groups="groups" />
        </div>
        <div class="profile-lower">
          <WeakPointRanking :groups="groups" @analyze="analyzePoint" />
          <SubjectCards :groups="groups" />
        </div>
        <ProfileHistory v-if="history.length > 1" :history="history" />
      </template>
      <el-empty v-else description="尚未建立知识点画像；完成一次诊断或练习后生成。" />
      <details class="profile-table">
        <summary>查看完整数据表</summary>
        <div class="table-wrap">
          <el-table :data="groups" max-height="440">
            <el-table-column prop="subject" label="科目" min-width="130" />
            <el-table-column prop="knowledgePoint" label="知识点" min-width="140" />
            <el-table-column label="难度" width="100">
              <template #default="{ row }">{{ difficultyLabel(row.difficulty) }}</template>
            </el-table-column>
            <el-table-column prop="samples" label="独立样本" width="100" />
            <el-table-column prop="correct" label="正确" width="80" />
            <el-table-column prop="assisted" label="辅助" width="80" />
            <el-table-column prop="unknown" label="未知" width="80" />
            <el-table-column label="掌握指数" min-width="130">
              <template #default="{ row }">{{ masteryText(row) }}</template>
            </el-table-column>
            <el-table-column label="复习建议" min-width="180">
              <template #default="{ row }">{{ advice(row) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </details>
      <div class="profile-actions">
        <el-button type="primary" @click="openAnalysis()">让学情助手分析</el-button>
        <span>图表只展示规则画像；不改变判分、权重或参考分。</span>
      </div>
    </template>
    <el-empty v-else-if="!busy" description="尚未建立画像，可先完成一次诊断。" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  learningHistory,
  learningProfile,
  learningStatus,
  type LearningGroup,
  type LearningProfile,
} from '@/api/learning'
import ProfileKpi from './learning-profile/ProfileKpi.vue'
import MasteryHeatmap from './learning-profile/MasteryHeatmap.vue'
import EvidenceScatter from './learning-profile/EvidenceScatter.vue'
import WeakPointRanking from './learning-profile/WeakPointRanking.vue'
import SubjectCards from './learning-profile/SubjectCards.vue'
import ProfileHistory from './learning-profile/ProfileHistory.vue'
import {
  difficultyLabel,
  formatDateTime,
  masteryPercent,
  profileStatusLabel,
  SAMPLE_THRESHOLD,
} from './learning-profile/profile-data'

const router = useRouter()
const enabled = ref(false)
const busy = ref(false)
const error = ref('')
const profile = ref<LearningProfile>()
const history = ref<LearningProfile[]>([])

const groups = computed(() => profile.value?.groups ?? [])
const notices = computed(() => profile.value?.notices ?? [])

async function load() {
  busy.value = true
  error.value = ''
  try {
    profile.value = await learningProfile()
    try {
      history.value = (await learningHistory()).list ?? []
    } catch {
      // The current profile remains useful even when the history endpoint fails.
      history.value = []
    }
  } catch {
    error.value = '学情读取失败，可点击刷新重试。'
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  try {
    enabled.value = (await learningStatus()).enabled
  } catch {
    error.value = '诊断状态读取失败，请稍后重试。'
    return
  }
  if (enabled.value) await load()
})

function masteryText(row: LearningGroup): string {
  const percent = masteryPercent(row)
  if (percent == null) return '待诊断'
  return `${percent}%${row.samples < SAMPLE_THRESHOLD ? '（样本不足）' : ''}`
}

function advice(row: LearningGroup): string {
  if (row.anomaly) return '近期表现异常，建议复测并分析错因'
  if (row.samples < SAMPLE_THRESHOLD) return '补充独立诊断样本'
  return (masteryPercent(row) ?? 0) < 60 ? '优先巩固' : '尝试进阶题'
}

function analyzePoint(point: string) {
  openAnalysis(
    `请根据我的学情画像分析「${point}」这个知识点：结合独立样本、正确率和近期异常，说明可能错因，并给出补强练习建议。`,
  )
}

function openAnalysis(prompt?: string) {
  const query =
    prompt ??
    '请根据我的学情画像分析薄弱知识点，异常时向我追问原因，并给出补强建议'
  void router.push({ path: '/tasks', query: { query } })
}
</script>

<style scoped>
.learning-profile {
  min-width: 0;
  padding: 16px;
  margin: 16px 0;
}
.profile-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px 16px;
  margin-bottom: 12px;
}
.profile-head > div {
  min-width: 0;
}
.profile-head h3 {
  margin: 0;
  font-size: 18px;
}
.profile-head p {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
  color: var(--c-ink-2);
  font-size: 12px;
  line-height: 1.5;
}
.profile-notices {
  margin: 12px 0 0;
  padding: 10px 12px 10px 28px;
  border-radius: var(--r-sm);
  background: var(--c-primary-light);
  color: var(--c-ink-2);
  font-size: 12px;
  line-height: 1.7;
}
.profile-charts {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  align-items: start;
  gap: 16px;
  margin-top: 16px;
}
.profile-lower {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  align-items: start;
  gap: 16px;
  margin-top: 16px;
}
.profile-charts > *,
.profile-lower > * {
  min-width: 0;
}
.profile-table {
  margin-top: 16px;
}
.profile-table summary {
  cursor: pointer;
  color: var(--c-ink-2);
  font-size: 12px;
}
.table-wrap {
  overflow-x: auto;
  margin-top: 8px;
}
.profile-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-top: 16px;
}
.profile-actions span {
  color: var(--c-ink-3);
  font-size: 12px;
  line-height: 1.5;
}
@media (max-width: 1000px) {
  .profile-charts,
  .profile-lower {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 560px) {
  .learning-profile {
    padding: 14px;
  }
  .profile-head {
    align-items: center;
  }
  .profile-kpi {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .kpi-card.profile .kpi-value {
    font-size: 20px;
  }
}
@media (max-width: 360px) {
  .profile-kpi {
    grid-template-columns: 1fr;
  }
}
</style>
