<template>
  <div class="page">
    <h2 class="page-title">题目审核</h2>
    <p class="page-sub">待审核题目列表</p>
    <div class="ka-card" v-loading="loading">
      <el-empty v-if="!rows.length" description="没有待审核题目" />
      <el-table v-else :data="rows" stripe>
        <el-table-column prop="content" label="题干" show-overflow-tooltip />
        <el-table-column prop="subject" label="科目" width="120" />
        <el-table-column prop="difficulty" label="难度" width="100" />
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { Question } from '@/types/api'

const loading = ref(false)
const rows = ref<Question[]>([])

onMounted(async () => {
  loading.value = true
  try {
    // 后端待审核题目接口预留：GET /api/questions/admin/pending
    const { getAdminPending } = await import('@/api/question')
    rows.value = await getAdminPending({ pageNum: 1, pageSize: 50 })
  } catch { rows.value = [] }
  finally { loading.value = false }
})
</script>
