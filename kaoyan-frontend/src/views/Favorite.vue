<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">我的收藏</h2>
      <p class="page-sub">共 {{ total }} 道收藏题目</p>
    </div>
    <div v-loading="loading">
      <el-empty v-if="!items.length && !loading" description="还没有收藏题目" :image-size="100" />
      <div v-for="it in items" :key="it.questionId" class="card item">
        <div class="item-head">
          <el-tag size="large" type="warning" effect="dark">藏</el-tag>
          <span class="q">{{ it.content || `[题目 #${it.questionId} 已删除]` }}</span>
        </div>
        <div class="body">
          <p><b>正确答案：</b><span class="right-ans">{{ it.answer }}</span></p>
          <p v-if="it.analysis"><b>解析：</b>{{ it.analysis }}</p>
        </div>
        <div class="foot">
          <el-button size="large" type="danger" plain @click="unfav(it.questionId)">取消收藏</el-button>
        </div>
      </div>
    </div>
    <div v-if="items.length < total" class="more">
      <el-button size="large" :loading="loading" @click="loadMore">加载更多</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getFavoritePage, removeFavorite, type MarkItem } from '@/api/mark'

const loading = ref(false)
const items = ref<MarkItem[]>([])
const total = ref(0)
const page = ref(1)
const size = 20

const load = async (append = false) => {
  loading.value = true
  try {
    const r = await getFavoritePage({ pageNum: page.value, pageSize: size })
    total.value = r.total
    items.value = append ? [...items.value, ...r.list] : r.list
  } finally { loading.value = false }
}
const loadMore = () => { page.value++; load(true) }
const unfav = async (id: number) => { await removeFavorite(id); page.value = 1; load() }
onMounted(() => load())
</script>

<style scoped>
.item { padding: 20px 22px; margin-bottom: 14px; }
.item-head { display: flex; gap: 10px; align-items: flex-start; }
.q { flex: 1; font-weight: 600; line-height: 1.7; font-size: 15px; }
.body { margin: 14px 0 0 36px; color: var(--c-ink-2); font-size: 14px; line-height: 1.9; }
.body p { margin: 4px 0; }
.right-ans { color: var(--c-success); font-weight: 600; }
.foot { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--c-line); display: flex; justify-content: center; gap: 12px; }
.more { text-align: center; margin: 20px 0; }
</style>
