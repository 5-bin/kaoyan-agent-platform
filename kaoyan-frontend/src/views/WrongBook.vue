<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">错题本</h2>
      <p class="page-sub">共 {{ total }} 道错题，坚持复习</p>
    </div>
    <p v-if="items.length > 50" class="page-sub">助手按前50题识别列表序号；可勾选具体题目（最多50题）后操作。</p>
    <div v-loading="loading">
      <el-empty v-if="!items.length && !loading" description="暂时没有错题" :image-size="100" />
      <div v-for="it in items" :key="it.questionId" class="card item">
        <div class="item-head">
          <el-checkbox :model-value="selected.includes(it.questionId)" :aria-label="'选择题目 ' + it.questionId" @change="toggle(it.questionId)" />
          <el-tag size="large" type="danger" effect="dark">错</el-tag>
          <el-tag v-if="it.isFavorite === 1" size="large" type="warning" effect="plain">已收藏</el-tag>
          <span class="q">{{ it.content || `[题目 #${it.questionId} 内容不可用]` }}</span>
        </div>
        <div class="body">
          <p v-if="it.answer"><b>正确答案：</b><span class="right-ans">{{ it.answer }}</span></p>
          <p v-if="historyNotice(it.snapshotStatus)">{{ historyNotice(it.snapshotStatus) }}</p>
          <p v-if="it.analysis"><b>解析：</b>{{ it.analysis }}</p>
        </div>
        <div class="foot">
          <el-button size="large" v-if="it.isFavorite !== 1" type="primary" plain @click="fav(it.questionId)">收藏</el-button>
          <el-button size="large" type="danger" plain @click="remove(it.questionId)">移出错题</el-button>
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
import { useAssistantPage } from '@/composables/assistant-page'
import { historyNotice } from '@/utils/question-history'
import { getWrongPage, removeWrong, addFavorite, type MarkItem } from '@/api/mark'

const loading = ref(false)
const items = ref<MarkItem[]>([])
const total = ref(0)
const page = ref(1)
const size = 20
const selected = ref<number[]>([])
const toggle = (id: number) => { selected.value = selected.value.includes(id) ? selected.value.filter(value => value !== id) : [...selected.value, id].slice(0,50) }

const load = async (append = false) => {
  loading.value = true
  try {
    const r = await getWrongPage({ pageNum: page.value, pageSize: size })
    total.value = r.total
    items.value = append ? [...items.value, ...r.list] : r.list
  } finally { loading.value = false }
}
const loadMore = () => { page.value++; load(true) }
const remove = async (id: number) => { await removeWrong(id); page.value = 1; load() }
const fav = async (id: number) => { await addFavorite(id); load() }
useAssistantPage(() => ({ page: 'wrong', selectedQuestionIds: selected.value, visibleQuestionIds: items.value.slice(0,50).map(item => item.questionId) }), () => { selected.value = []; page.value = 1; return load() })
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
