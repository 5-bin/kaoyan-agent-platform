<template>
  <div class="page">
    <h2>任务历史</h2><p>可回顾历史结果或继续错题追问；独立任务不会自动转换为会话。</p>
    <router-link to="/tasks">返回 Agent 助手</router-link>
    <el-table :data="rows" v-loading="loading">
      <el-table-column prop="taskType" label="类型" />
      <el-table-column prop="status" label="状态" />
      <el-table-column prop="createdAt" label="时间" />
      <el-table-column label="结果"><template #default="{ row }"><el-button @click="selected = row">查看</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="prev, pager, next" @current-change="load" />
    <el-dialog :model-value="!!selected" title="历史结果" width="min(760px,94vw)" @close="selected = null">
      <WrongQuestionTutor v-if="selected?.taskType === 'WRONG_QUESTION_TUTOR' && selected.tutoring"
        :key="selected.id" :record-id="selected.tutoring.recordId" :initial-task="selected" />
      <TaskResultView v-else-if="selected" :task="selected" />
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getTaskList } from '@/api/task'
import type { Task } from '@/types/api'
import TaskResultView from '@/components/TaskResultView.vue'
import WrongQuestionTutor from '@/components/WrongQuestionTutor.vue'
const rows = ref<Task[]>([]), selected = ref<Task | null>(null), page = ref(1), total = ref(0), loading = ref(false)
async function load() { loading.value = true; try { const result = await getTaskList({ pageNum: page.value, pageSize: 20 }); rows.value = result.list; total.value = result.total } finally { loading.value = false } }
onMounted(load)
</script>
