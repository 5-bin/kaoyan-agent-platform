<template>
  <div class="page">
    <div class="page-head">
      <div style="display:flex; justify-content:space-between; align-items:center">
        <div>
          <h2 class="page-title">Agent 助手</h2>
          <p class="page-sub">向智能 Agent 提问或请求择校推荐</p>
        </div>
        <el-button type="primary" @click="dialog = true">提交任务</el-button>
      </div>
    </div>

    <div class="card" v-loading="loading" style="padding: 8px 0">
      <el-empty v-if="!rows.length" description="还没有任务" :image-size="80" />
      <el-table v-else :data="rows" stripe>
        <el-table-column prop="taskType" label="类型" width="180">
          <template #default="{ row }">
            <el-tag effect="plain">{{ typeLabels[row.taskType as Task['taskType']] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'SUCCESS' ? 'success' : row.status === 'FAILED' ? 'danger' : 'info'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="200" />
        <el-table-column label="结果">
          <template #default="{ row }">
            <el-button size="small" @click="selected = row">查看结果与来源</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="prev, pager, next, total" @current-change="load" />
    </div>

    <el-dialog v-model="dialog" title="提交任务" width="480px">
      <el-form label-width="70px">
        <el-form-item label="类型">
          <el-select v-model="form.taskType" style="width:100%">
            <el-option label="知识问答" value="KNOWLEDGE_QA" />
            <el-option label="择校推荐" value="SCHOOL_RECOMMEND" />
            <el-option label="自动识别" value="CHAT" />
          </el-select>
        </el-form-item>
        <el-form-item label="输入">
          <el-input v-model="form.input" :maxlength="8000" show-word-limit type="textarea" :rows="4" placeholder="描述你的问题" />
        </el-form-item>
        <p v-if="form.taskType === 'SCHOOL_RECOMMEND'"><router-link to="/schools">前往院校页面设置专业、学位等推荐条件</router-link></p>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!form.input.trim()" @click="submit">提交</el-button>
      </template>
    </el-dialog>
    <el-dialog :model-value="!!selected" title="任务结果" width="min(760px, 94vw)" @close="selected = null">
      <WrongQuestionTutor v-if="selected?.taskType === 'WRONG_QUESTION_TUTOR' && typeof selected.inputPayload?.recordId === 'number'"
        :key="selected.id" :record-id="selected.inputPayload.recordId" :initial-task="selected" />
      <TaskResultView v-else-if="selected" :task="selected" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getTaskList, submitTask } from '@/api/task'
import type { Task } from '@/types/api'
import TaskResultView from '@/components/TaskResultView.vue'
import WrongQuestionTutor from '@/components/WrongQuestionTutor.vue'

const dialog = ref(false)
const submitting = ref(false)
const loading = ref(false)
const rows = ref<Task[]>([])
const selected = ref<Task | null>(null)
const page = ref(1), total = ref(0)
const typeLabels: Record<Task['taskType'], string> = { KNOWLEDGE_QA: '知识问答', SCHOOL_RECOMMEND: '院校推荐', PRACTICE_SUMMARY: '练习总结', CHAT: '自动识别', WRONG_QUESTION_TUTOR: '错题 AI 辅导' }
const form = reactive({ taskType: 'KNOWLEDGE_QA', input: '' })

const load = async () => {
  loading.value = true
  try {
    const r = await getTaskList({ pageNum: page.value, pageSize: 20 })
    rows.value = r.list
    total.value = r.total
  } finally { loading.value = false }
}
const submit = async () => {
  if (submitting.value || !form.input.trim()) return
  submitting.value = true
  try {
    await submitTask({ taskType: form.taskType, input: { query: form.input } })
    dialog.value = false
    form.input = ''
    page.value = 1
    await load()
  } finally { submitting.value = false }
}
onMounted(load)
</script>
