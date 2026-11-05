<template>
  <div class="page">
    <DiagnosticEntry compact />
    <div class="page-head">
      <h2 class="page-title">开始刷题</h2>
      <p class="page-sub">选择题型、难度和题量，开始一次新的练习</p>
      <p v-if="cfg.subject === '计算机组成原理' || linkedQuestion?.subject === '计算机组成原理'" class="page-sub">
        2026-10-29新增40道Chris Terman课程习题中文改编，非408统考真题。
        <a href="/licenses/computation-structures-mit.txt" target="_blank" rel="noopener noreferrer">完整MIT许可</a> ·
        <a href="/question-sources/co-20261029.json" target="_blank" rel="noopener noreferrer">逐题出处与改编说明</a>
      </p>
    </div>

    <el-dialog v-model="questionPreview" title="题目（未作答不展示答案）" width="min(800px,94vw)"><p>此处展示当前可练习版本；历史作答以助手列出的版本及原练习回顾为准。</p><p>{{ linkedQuestion?.content }}</p><p v-for="key in ['A','B','C','D'] as const" :key="key">{{ key }}. {{ linkedQuestion?.[('option' + key) as 'optionA'] }}</p></el-dialog>
    <!-- 各组都是原生单选框：Tab 进入一组，方向键切换，读屏能读出组名与选中状态 -->
    <section class="card config" aria-label="练习设置">
      <div class="cfg-row" role="radiogroup" aria-labelledby="cfg-source">
        <div id="cfg-source" class="cfg-label">范围</div>
        <div class="opts">
          <label v-for="s in sources" :key="s.v" class="pill" :class="{ on: cfg.source === s.v }">
            <input v-model="cfg.source" class="sr-only" type="radio" name="cfg-source" :value="s.v">{{ s.label }}
          </label>
        </div>
      </div>
      <div class="cfg-row" role="radiogroup" aria-labelledby="cfg-subject">
        <div id="cfg-subject" class="cfg-label">科目</div>
        <div class="opts">
          <label v-for="s in subjects" :key="s" class="pill" :class="{ on: cfg.subject === s }">
            <input v-model="cfg.subject" class="sr-only" type="radio" name="cfg-subject" :value="s">{{ s }}
          </label>
        </div>
      </div>
      <div class="cfg-row" role="radiogroup" aria-labelledby="cfg-difficulty">
        <div id="cfg-difficulty" class="cfg-label">难度</div>
        <div class="opts">
          <label v-for="d in difficulties" :key="d.v" class="pill" :class="{ on: cfg.difficulty === d.v }">
            <input v-model="cfg.difficulty" class="sr-only" type="radio" name="cfg-difficulty" :value="d.v">{{ d.label }}
          </label>
        </div>
      </div>
      <div class="cfg-row" role="radiogroup" aria-labelledby="cfg-count">
        <div id="cfg-count" class="cfg-label">题量</div>
        <div class="opts">
          <label v-for="n in counts" :key="n" class="pill" :class="{ on: !customActive && cfg.count === n }">
            <input class="sr-only" type="radio" name="cfg-count" :checked="!customActive && cfg.count === n" @change="onPill(n)">{{ n }} 题
          </label>
          <label class="pill" :class="{ on: customActive }">
            <input class="sr-only" type="radio" name="cfg-count" :checked="customActive" @change="useCustom">自定义
          </label>
          <label v-if="customActive" class="custom-field">
            <span>自定义题量</span>
            <el-input
              ref="customRef"
              v-model.number="customCount"
              type="number" min="1" max="50" placeholder="1–50"
              class="custom-input"
              @input="onCustom"
            />
          </label>
        </div>
      </div>
      <div class="cfg-foot">
        <p class="cfg-summary">将从 <b>{{ summary }}</b> 中抽题</p>
        <el-button type="primary" size="large" class="start" :loading="loading" @click="start">
          开始刷题
        </el-button>
      </div>
    </section>

    <h3 class="sec-title">做题记录</h3>
    <div class="card" v-loading="historyLoading" style="padding: 8px 0">
      <el-empty v-if="!records.length" description="还没有做题记录" :image-size="80" />
      <el-table v-else :data="records" stripe style="border: none; width: 100%">
        <el-table-column label="完成时间" min-width="180">
          <template #default="scope">{{ fmt(scope.row.finishedAt) }}</template>
        </el-table-column>
        <el-table-column prop="total" label="题量" min-width="80" />
        <el-table-column prop="answered" label="已答" min-width="80" />
        <el-table-column prop="correct" label="正确" min-width="80" />
        <el-table-column label="正确率" min-width="160">
          <template #default="scope">
            <el-progress :percentage="scope.row.accuracy" :stroke-width="10" :show-text="true" />
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="120" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="openRow(scope.row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <div v-if="records.length < total" class="more">
      <el-button size="large" :loading="historyLoading" @click="loadMore">加载更多</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import DiagnosticEntry from '@/components/DiagnosticEntry.vue'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useAssistantPage } from '@/composables/assistant-page'
import { getQuestionDetail } from '@/api/question'
import type { StudentQuestion } from '@/types/api'
import { ElMessage } from 'element-plus'
import type { InputInstance } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { startSession, getSessionPage, type SessionSummary } from '@/api/practice'

const router = useRouter(), route = useRoute()
const linkedQuestion = ref<StudentQuestion>(), questionPreview = ref(false)
let questionLoad = 0
async function openLinkedQuestion() { const stamp = ++questionLoad, id = String(route.query.questionId || ''); linkedQuestion.value = undefined; questionPreview.value = false; if (!/^\d+$/.test(id)) return; const data = await getQuestionDetail(Number(id)); if (stamp === questionLoad && String(route.query.questionId) === id) { linkedQuestion.value = data; questionPreview.value = true } }
const subjects = ['数据结构', '操作系统', '计算机网络', '计算机组成原理']
const difficulties = [
  { v: 'EASY', label: '简单' },
  { v: 'MEDIUM', label: '中等' },
  { v: 'HARD', label: '困难' }
]
const sources = [
  { v: 'NORMAL', label: '普通练习' },
  { v: 'WRONG', label: '我的错题' },
  { v: 'FAVORITE', label: '我的收藏' }
] as const
const counts = [5, 10, 20, 50]
const cfg = reactive({ subject: '数据结构', difficulty: 'MEDIUM', count: 5, source: 'NORMAL' as 'NORMAL' | 'WRONG' | 'FAVORITE' })
const customCount = ref<number | undefined>(undefined)
const customActive = ref(false)
const customRef = ref<InputInstance>()
const onPill = (n: number) => { customActive.value = false; customCount.value = undefined; cfg.count = n }
const useCustom = async () => { customActive.value = true; await nextTick(); customRef.value?.focus() }
const summary = computed(() => {
  const source = sources.find(s => s.v === cfg.source)?.label
  const difficulty = difficulties.find(d => d.v === cfg.difficulty)?.label
  const count = customActive.value
    ? (Number.isInteger(customCount.value) ? `${customCount.value} 题` : '自定义题量（待填写）')
    : `${cfg.count} 题`
  return [source, cfg.subject, difficulty, count].join(' · ')
})
const onCustom = () => {
  const v = Number(customCount.value)
  if (Number.isFinite(v) && v >= 1 && v <= 50) cfg.count = Math.floor(v)
}
const loading = ref(false)
const historyLoading = ref(false)
const records = ref<SessionSummary[]>([])
const total = ref(0)
const page = ref(1)
const size = 10

const start = async () => {
  if (customActive.value && (!Number.isInteger(customCount.value) || Number(customCount.value) < 1 || Number(customCount.value) > 50)) { ElMessage.warning('题量须为1至50的整数'); return }
  loading.value = true
  try {
    const r: any = await startSession({ ...cfg })
    router.push(`/practice/session/${r.sessionId}`)
  } finally {
    loading.value = false
  }
}

const openRow = (row: SessionSummary) => router.push(`/practice/session/${row.sessionId}`)

const fmt = (dt?: string) => dt ? dt.slice(0, 16).replace('T', ' ') : '—'

const loadHistory = async (append = false) => {
  historyLoading.value = true
  try {
    const r = await getSessionPage({ pageNum: page.value, pageSize: size })
    total.value = r.total
    records.value = append ? [...records.value, ...r.list] : r.list
  } finally {
    historyLoading.value = false
  }
}
const loadMore = () => { page.value++; loadHistory(true) }

useAssistantPage(() => ({ page: 'practice', subject: questionPreview.value ? linkedQuestion.value?.subject : cfg.subject, selectedQuestionIds: questionPreview.value && linkedQuestion.value ? [linkedQuestion.value.id] : [], visibleQuestionIds: questionPreview.value && linkedQuestion.value ? [linkedQuestion.value.id] : [] }), loadHistory)
watch(() => route.query.questionId, openLinkedQuestion)
onMounted(() => { void loadHistory(); void openLinkedQuestion() })
</script>

<style scoped lang="scss">
.config {
  padding: 24px 28px; margin-bottom: 24px; border-radius: var(--r-lg);
  box-shadow: var(--fx-shadow-card);
}
.cfg-row { display: flex; align-items: flex-start; gap: 10px 16px; margin-bottom: 18px; }
.cfg-label { width: 56px; color: var(--c-ink-2); font-weight: 600; line-height: 40px; flex-shrink: 0; }
.opts { flex: 1; min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.pill {
  position: relative; display: inline-flex; align-items: center;
  min-height: 40px; padding: 0 18px; box-sizing: border-box;
  border-radius: 999px; cursor: pointer; font-size: 14px;
  border: 1.5px solid #d5d9e0; background: var(--c-surface); color: var(--c-ink);
  transition: border-color .15s ease, background-color .15s ease, color .15s ease;
}
.pill:hover { border-color: var(--c-primary-strong); }
.pill.on {
  border-color: var(--c-primary-strong); background: var(--c-primary-light);
  color: var(--c-primary-deep); font-weight: 600;
}
.pill:has(input:focus-visible) { outline: 3px solid var(--c-primary-strong); outline-offset: 2px; }
.custom-field { display: inline-flex; align-items: center; gap: 8px; color: var(--c-ink-2); }
.custom-input { width: 96px; }
.custom-input :deep(.el-input__wrapper) { min-height: 38px; }
.cfg-foot {
  display: flex; flex-wrap: wrap; align-items: center; gap: 12px 20px;
  border-top: 1px solid #eef0f3; padding-top: 20px; margin-top: 4px;
}
.cfg-summary { flex: 1 1 280px; margin: 0; color: var(--c-ink-2); line-height: 1.6; }
.cfg-summary b { color: var(--c-ink); }
.start { min-width: 140px; }
@media (prefers-reduced-motion: reduce) { .pill { transition: none; } }
@media (max-width: 640px) {
  .config { padding: 18px 16px; }
  .cfg-row { flex-direction: column; gap: 6px; }
  .cfg-label { line-height: 1.6; }
  .pill { min-height: 44px; }
  .start { width: 100%; }
}
.sec-title { font-size: 15px; font-weight: 600; margin: 0 0 12px; }
.more { text-align: center; margin: 16px 0; }
</style>
