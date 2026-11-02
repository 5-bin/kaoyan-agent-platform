<template>
  <section v-if="enabled" class="card panel" v-loading="busy">
    <h3>随学情更新院校推荐</h3>
    <p>保存报考条件后，规则流程会在首次建立画像或出现明显变化时更新推荐，并计入现有任务额度。<router-link to="/profile">报考年份在个人档案中维护</router-link>。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-form label-position="top" :disabled="busy">
      <el-form-item label="自动更新"><el-switch v-model="form.enabled" /></el-form-item>
      <div class="grid">
        <el-form-item label="专业代码"><el-input v-model="form.majors" placeholder="081200，多个代码用逗号分隔" /></el-form-item>
        <el-form-item label="学位"><el-select v-model="form.degree"><el-option label="学硕" value="academic" /><el-option label="专硕" value="professional" /></el-select></el-form-item>
        <el-form-item label="地区"><el-input v-model="form.regions" placeholder="可留空，多个地区用逗号分隔" /></el-form-item>
        <el-form-item label="地区要求"><el-select v-model="form.constraint"><el-option label="优先考虑" value="preferred" /><el-option label="必须满足" value="required" /></el-select></el-form-item>
        <el-form-item label="学习方式"><el-select v-model="form.studyMode"><el-option label="全日制" value="full_time" /><el-option label="非全日制" value="part_time" /></el-select></el-form-item>
      </div>
      <el-button type="primary" @click="save">保存推荐设置</el-button><el-button @click="load">刷新状态</el-button>
    </el-form>
    <p v-if="settings">状态：{{ !settings.enabled ? '未启用' : settings.status === 'PENDING' ? '待更新（额度或失败重试时保留原推荐）' : settings.status === 'FAILED' ? '更新失败，可重新保存设置重试' : '已更新' }} · 画像版本 {{ settings.profileRevision ?? '暂无' }} · {{ settings.updatedAt || '尚未生成' }}</p>
    <TaskResultView v-if="task" :task="task" />
  </section>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { learningStatus, recommendationSettings, saveRecommendationSettings, type RecommendationSettings } from '@/api/learning'
import { getTaskDetail } from '@/api/task'
import TaskResultView from './TaskResultView.vue'
import type { Task } from '@/types/api'
const enabled = ref(false), busy = ref(false), error = ref(''), settings = ref<RecommendationSettings>(), task = ref<Task>()
const form = reactive({ enabled: false, majors: '081200', degree: 'academic', regions: '', constraint: 'preferred', studyMode: 'full_time' })
const split = (v: string) => v.split(/[,，]/).map(s => s.trim()).filter(Boolean)
async function load() {
  busy.value = true; error.value = ''
  try {
    settings.value = await recommendationSettings(); const p = settings.value.preferences
    form.enabled = settings.value.enabled; form.majors = (p.majorCodes as string[] || []).join(',') || '081200'
    form.degree = String(p.degreeType || 'academic'); form.regions = (p.regions as string[] || []).join(',')
    form.constraint = String(p.regionConstraint || 'preferred'); form.studyMode = String(p.studyMode || 'full_time')
    task.value = settings.value.lastTaskId ? await getTaskDetail(settings.value.lastTaskId) : undefined
  } catch { error.value = '推荐设置或结果读取失败，请刷新重试。' }
  finally { busy.value = false }
}
async function save() {
  if (!settings.value) return
  busy.value = true; error.value = ''
  try {
    settings.value = await saveRecommendationSettings({ revision: settings.value.revision, enabled: form.enabled, preferences: {
      majorCodes: split(form.majors), degreeType: form.degree, regions: split(form.regions), regionConstraint: form.constraint,
      studyMode: form.studyMode, examSubjects: ['408'], explainWithAi: false
    } })
  } catch { error.value = '保存失败或设置版本冲突，请刷新后再试。' }
  finally { busy.value = false }
}
onMounted(async () => { enabled.value = (await learningStatus()).enabled; if (enabled.value) await load() })
</script>
<style scoped>.panel { padding: 20px; margin: 20px 0; } .grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(200px,1fr)); gap: 0 16px; }</style>
