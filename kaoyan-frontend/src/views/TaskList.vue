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
            <el-tag effect="plain">{{ row.taskType === 'KNOWLEDGE_QA' ? '知识问答' : '择校推荐' }}</el-tag>
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
            <span style="color: var(--c-ink-2)">{{ row.resultPayload ? JSON.stringify(row.resultPayload) : '—' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialog" title="提交任务" width="480px">
      <el-form label-width="70px">
        <el-form-item label="类型">
          <el-select v-model="form.taskType" style="width:100%">
            <el-option label="知识问答" value="KNOWLEDGE_QA" />
            <el-option label="择校推荐" value="SCHOOL_RECOMMEND" />
          </el-select>
        </el-form-item>
        <el-form-item label="输入">
          <el-input v-model="form.input" type="textarea" :rows="4" placeholder="描述你的问题" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getTaskList, submitTask } from '@/api/task'
import type { Task } from '@/types/api'

const dialog = ref(false)
const submitting = ref(false)
const loading = ref(false)
const rows = ref<Task[]>([])
const form = reactive({ taskType: 'KNOWLEDGE_QA', input: '' })

const load = async () => {
  loading.value = true
  try {
    const r = await getTaskList({ pageNum: 1, pageSize: 20 })
    rows.value = r.list
  } finally { loading.value = false }
}
const submit = async () => {
  submitting.value = true
  try {
    await submitTask({ taskType: form.taskType, input: { query: form.input } })
    dialog.value = false
    form.input = ''
    load()
  } finally { submitting.value = false }
}
onMounted(load)
</script>
