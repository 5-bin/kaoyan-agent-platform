<template>
  <div class="page">
    <h2 class="page-title">资料审核</h2>
    <p class="page-sub">后台管理资料</p>
    <div class="ka-card" v-loading="loading">
      <el-table :data="rows" stripe>
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="subject" label="科目" width="120" />
        <el-table-column prop="status" label="状态" width="140" />
        <el-table-column prop="createdAt" label="创建时间" width="200" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="review(row, 'PUBLISHED')">通过</el-button>
            <el-button size="small" type="danger" @click="review(row, 'REJECTED')">拒绝</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getAdminDocumentList, reviewDocument } from '@/api/document'
import type { Document } from '@/types/api'

const loading = ref(false)
const rows = ref<Document[]>([])
const load = async () => {
  loading.value = true
  try {
    const r = await getAdminDocumentList({ pageNum: 1, pageSize: 50 })
    rows.value = r.list
  } finally { loading.value = false }
}
const review = async (row: Document, status: string) => {
  await reviewDocument(row.id, { status })
  load()
}
onMounted(load)
</script>
