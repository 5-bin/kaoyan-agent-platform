<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">备考资料</h2>
      <p class="page-sub">已发布的复习资料</p>
    </div>
    <div class="card filter">
      <el-select v-model="subject" placeholder="全部科目" clearable style="width:200px" @change="load">
        <el-option label="数据结构" value="数据结构" />
        <el-option label="操作系统" value="操作系统" />
        <el-option label="计算机网络" value="计算机网络" />
        <el-option label="计算机组成原理" value="计算机组成原理" />
      </el-select>
    </div>

    <div class="grid" v-loading="loading">
      <div v-for="d in list" :key="d.id" class="card item">
        <div class="item-top">
          <el-tag size="small" effect="plain">{{ d.subject }}</el-tag>
        </div>
        <div class="item-title">{{ d.title }}</div>
        <div class="item-content">{{ d.content?.slice(0, 80) }}{{ d.content?.length > 80 ? '…' : '' }}</div>
        <a v-if="d.sourceUrl" :href="d.sourceUrl" target="_blank" class="item-link">查看来源 →</a>
      </div>
    </div>
    <el-empty v-if="!loading && !list.length" description="暂无资料" style="margin-top:40px" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getPublishedDocuments } from '@/api/document'
import type { Document } from '@/types/api'

const subject = ref('')
const list = ref<Document[]>([])
const loading = ref(false)
const load = async () => {
  loading.value = true
  try { list.value = await getPublishedDocuments({ subject: subject.value || undefined }) }
  finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.filter { padding: 16px; margin-bottom: 16px; }
.grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.item { padding: 20px; }
.item-top { margin-bottom: 10px; }
.item-title { font-weight: 600; font-size: 15px; margin-bottom: 8px; }
.item-content { color: var(--c-ink-2); font-size: 13px; line-height: 1.6; min-height: 42px; }
.item-link { font-size: 13px; margin-top: 10px; display: inline-block; }
</style>
