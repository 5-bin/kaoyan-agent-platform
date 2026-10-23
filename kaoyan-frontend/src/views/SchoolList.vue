<template>
  <div class="page schools-page">
    <div class="hero">
      <h1>院校与专业</h1><p>按明确条件比较候选，逐条核对官方依据</p>
      <div class="search-bar">
        <el-input v-model="q.province" placeholder="省份" clearable />
        <el-select v-model="q.level" placeholder="层次" clearable><el-option v-for="level in ['985','211','双一流']" :key="level" :label="level" :value="level" /></el-select>
        <el-input v-model="q.majorName" placeholder="专业名" clearable />
        <el-button @click="load">搜索院校库</el-button>
        <el-button type="primary" @click="openRecommendation">条件推荐</el-button>
      </div>
    </div>
    <el-alert title="请核对专业详情中的招生年份、来源与适用条件。历史演示或估计数据不能作为报考依据；条件推荐使用独立核验资料。" type="warning" :closable="false" />
    <div class="rows" v-loading="loading">
      <router-link v-for="school in list" :key="school.id" :to="`/schools/${school.id}`" class="school-row">
        <strong>{{ school.name }}</strong><span>{{ school.province }} · {{ school.level || '层次未登记' }}</span>
      </router-link>
      <el-empty v-if="!loading && !list.length" description="没有匹配的院校" />
    </div>
    <section class="card history">
      <h2>我的推荐历史（最近100条） <el-button size="small" @click="loadHistory">刷新</el-button></h2>
      <el-empty v-if="!history.length" description="还没有推荐记录" :image-size="60" />
      <div v-for="task in history" :key="task.id" class="history-row">
        <span>{{ task.createdAt }} · {{ task.status }}</span>
        <el-button size="small" @click="showHistory(task)">查看</el-button>
      </div>
    </section>
    <el-dialog v-model="dialog" title="2027年院校专业推荐" width="min(760px, 94vw)" top="5vh" class="recommendation-dialog" destroy-on-close>
      <p>档案报考年份：<strong>{{ profile?.examYear || '未填写' }}</strong> · <router-link to="/profile">编辑档案</router-link></p>
      <p class="muted">按当前已核验资料筛选081200、085404项目；实际覆盖范围见推荐结果，临时偏好不会修改档案。</p>
      <el-form label-position="top" :disabled="submitting">
        <div class="form-grid">
          <el-form-item label="目标专业"><el-select v-model="form.majorCode"><el-option label="081200 计算机科学与技术" value="081200" /><el-option label="085404 计算机技术" value="085404" /></el-select></el-form-item>
          <el-form-item label="学位类型"><el-select v-model="form.degreeType"><el-option label="学硕" value="academic" /><el-option label="专硕" value="professional" /></el-select></el-form-item>
          <el-form-item label="地区"><el-select v-model="form.regions" multiple filterable allow-create placeholder="不限制地区"><el-option label="北京" value="北京" /><el-option label="江苏" value="江苏" /></el-select></el-form-item>
          <el-form-item label="地区约束"><el-select v-model="form.regionConstraint"><el-option label="优先考虑" value="preferred" /><el-option label="必须满足" value="required" /></el-select></el-form-item>
          <el-form-item label="学习方式"><el-select v-model="form.studyMode"><el-option label="全日制" value="full_time" /><el-option label="非全日制" value="part_time" /></el-select></el-form-item>
        </div>
        <el-form-item label="希望比较的问题"><el-input v-model="query" type="textarea" :rows="2" maxlength="8000" /></el-form-item>
        <el-checkbox v-model="form.explainWithAi">请求AI解释（未启用模型时使用规则说明）</el-checkbox>
      </el-form>
      <TaskResultView v-if="result" :task="result" />
      <template #footer><el-button @click="dialog = false">关闭</el-button><el-button type="primary" :loading="submitting" :disabled="!query.trim()" @click="ask">生成推荐</el-button></template>
    </el-dialog>
    <el-dialog :model-value="!!historyTask" title="历史推荐与依据" width="min(760px, 94vw)" top="5vh" class="recommendation-dialog" @close="historyTask = null">
      <TaskResultView v-if="historyTask" :task="historyTask" />
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { searchSchools } from '@/api/school'
import { generateRecommend, getRecommendList } from '@/api/recommend'
import { getCurrentUser } from '@/api/user'
import { useUserStore } from '@/stores/user'
import TaskResultView from '@/components/TaskResultView.vue'
import type { School, Task, User } from '@/types/api'
const user = useUserStore()
const q = reactive({ province: '', level: '', majorName: '' })
const list = ref<School[]>([]), history = ref<Task[]>([])
const loading = ref(false), submitting = ref(false), dialog = ref(false)
const profile = ref<User | null>(null), result = ref<Task | null>(null)
const historyTask = ref<Task | null>(null)
const query = ref('请比较符合条件的专业，并说明考试科目及需要核对的事项。')
const form = reactive({ majorCode: '081200', degreeType: 'academic', regions: [] as string[], regionConstraint: 'preferred', studyMode: 'full_time', explainWithAi: true })
let searchVersion = 0, historyVersion = 0
async function load() {
  const version = ++searchVersion
  loading.value = true
  try { const data = await searchSchools(q); if (version === searchVersion) list.value = data } finally { if (version === searchVersion) loading.value = false }
}
async function loadHistory() {
  const version = ++historyVersion
  const data = await getRecommendList()
  if (version === historyVersion) history.value = data
}
async function openRecommendation() {
  result.value = null
  profile.value = await getCurrentUser()
  if (profile.value.targetMajor === '085404' || profile.value.targetMajor === '计算机技术') { form.majorCode = '085404'; form.degreeType = 'professional' }
  dialog.value = true
}
function showHistory(task: Task) { historyTask.value = task }
async function ask() {
  if (submitting.value || !query.value.trim()) return
  const token = user.token
  submitting.value = true
  try {
    const task = await generateRecommend({ query: query.value, preferences: { majorCodes: [form.majorCode], degreeType: form.degreeType,
      regions: form.regions, regionConstraint: form.regionConstraint, studyMode: form.studyMode, explainWithAi: form.explainWithAi } })
    if (token !== user.token) return
    result.value = task
    await loadHistory()
  } catch { /* The request wrapper displays errors and discards stale account responses. */ }
  finally { submitting.value = false }
}
onMounted(() => { void load(); void loadHistory() })
</script>
<style scoped>
.schools-page { max-width: 1000px; }
.hero { background: linear-gradient(135deg,#3b6cff,#6d5cff); border-radius: 16px; padding: 28px; color: white; margin-bottom: 18px; }
.hero h1 { margin: 0; }
.search-bar, .form-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }
.search-bar .el-input, .search-bar .el-select { width: 100%; }
.rows { margin: 20px 0; }
.school-row { display: flex; justify-content: space-between; padding: 18px; margin: 10px 0; background: var(--c-surface); border: 1px solid var(--c-line); border-radius: 12px; color: var(--c-ink); text-decoration: none; }
.history { padding: 20px; }
.history h2 { font-size: 18px; }
.history-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--c-line); }
.muted { color: var(--c-ink-2); font-size: 13px; }
.recommendation-dialog { max-height: 90vh; display: flex; flex-direction: column; }
.recommendation-dialog :deep(.el-dialog__body) { min-height: 0; overflow-y: auto; }
@media(max-width:600px) { .form-grid,.search-bar { grid-template-columns: 1fr; } .school-row { flex-direction: column; gap: 8px; } }
</style>
