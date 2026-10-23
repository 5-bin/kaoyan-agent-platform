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
        <el-button link type="primary" @click="openDocument(d)">阅读正文</el-button>
        <a v-if="safeSourceUrl(d.sourceUrl)" :href="safeSourceUrl(d.sourceUrl)" target="_blank" rel="noopener noreferrer" class="item-link">查看来源 →</a>
      </div>
    </div>
    <el-dialog v-model="reading" :title="selectedDocument?.title || '备考资料'" width="min(860px,96vw)" @close="closeDocument"><p>平台已发布资料 · {{ selectedDocument?.subject }} · 版本及原文位置以已登记来源为准</p><SafeMarkdown :content="selectedDocument?.content || ''" :allowed-urls="selectedDocument?.sourceUrl ? [selectedDocument.sourceUrl] : []" /><p v-if="!selectedDocument?.sourceUrl">来源链接未登记，请核对原始出处。</p></el-dialog>
    <el-empty v-if="!loading && !list.length" description="暂无资料" style="margin-top:40px" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAssistantPage } from '@/composables/assistant-page'
import { safeSourceUrl } from '@/utils/assistant-resource'
import SafeMarkdown from '@/components/SafeMarkdown.vue'
import { getPublishedDocuments } from '@/api/document'
import type { Document } from '@/types/api'

const route = useRoute(), router = useRouter()
const reading = ref(false), selectedDocument = ref<Document>()
function openDocument(document: Document) { selectedDocument.value = document; reading.value = true; void router.replace({ query: { ...route.query, documentId: String(document.id) } }) }
function closeDocument() { if (route.query.documentId) { const { documentId: _documentId, ...query } = route.query; void router.replace({ query }) } }
function openLinkedDocument() { const document = list.value.find(item => String(item.id) === route.query.documentId); if (document) { selectedDocument.value = document; reading.value = true } }
const subject = ref('')
const list = ref<Document[]>([])
const loading = ref(false)
const load = async () => {
  loading.value = true
  try { list.value = await getPublishedDocuments({ subject: subject.value || undefined }); openLinkedDocument() }
  finally { loading.value = false }
}
watch(() => route.query.documentId, openLinkedDocument)
useAssistantPage(() => ({ page: 'documents', subject: subject.value || undefined, documentId: selectedDocument.value?.id }), load)
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
