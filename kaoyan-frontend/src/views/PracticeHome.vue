<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">开始刷题</h2>
      <p class="page-sub">选择题型、难度和题量，开始一次新的练习</p>
    </div>

    <el-dialog v-model="questionPreview" title="题目（未作答不展示答案）" width="min(800px,94vw)"><p>此处展示当前可练习版本；历史作答以助手列出的版本及原练习回顾为准。</p><p>{{ linkedQuestion?.content }}</p><p v-for="key in ['A','B','C','D'] as const" :key="key">{{ key }}. {{ linkedQuestion?.[('option' + key) as 'optionA'] }}</p></el-dialog>
    <div class="card config">
      <div class="cfg-row"><div class="cfg-label">范围</div><el-select v-model="cfg.source"><el-option label="普通练习" value="NORMAL" /><el-option label="我的错题" value="WRONG" /><el-option label="我的收藏" value="FAVORITE" /></el-select></div>
      <div class="cfg-row">
        <div class="cfg-label">科目</div>
        <div class="opts">
          <div v-for="s in subjects" :key="s" class="pill" :class="{ on: cfg.subject === s }" @click="cfg.subject = s">
            {{ s }}
          </div>
        </div>
      </div>
      <div class="cfg-row">
        <div class="cfg-label">难度</div>
        <div class="opts">
          <div v-for="d in difficulties" :key="d.v" class="pill" :class="{ on: cfg.difficulty === d.v }" @click="cfg.difficulty = d.v">
            {{ d.label }}
          </div>
        </div>
      </div>
      <div class="cfg-row">
        <div class="cfg-label">题量</div>
        <div class="opts">
          <div
            v-for="n in [5, 10, 20, 50]" :key="n"
            class="pill"
            :class="{ on: !customActive && cfg.count === n }"
            @click="onPill(n)"
          >{{ n }} 题</div>
          <div
            class="pill custom" :class="{ on: customActive }"
            @click="customActive = true; customRef?.focus()"
          >
            <span>自定义</span>
            <el-input
              v-model.number="customCount"
              size="small" placeholder="数量"
              class="custom-input"
              ref="customRef"
              @input="onCustom"
              @click.stop
            />
          </div>
        </div>
      </div>
      <el-button type="primary" size="large" class="start" :loading="loading" @click="start">
        开始刷题
      </el-button>
    </div>

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
import { onMounted, reactive, ref, watch } from 'vue'
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
const cfg = reactive({ subject: '数据结构', difficulty: 'MEDIUM', count: 5, source: 'NORMAL' as 'NORMAL' | 'WRONG' | 'FAVORITE' })
const customCount = ref<number | undefined>(undefined)
const customActive = ref(false)
const customRef = ref<InputInstance>()
const onPill = (n: number) => { customActive.value = false; customCount.value = undefined; cfg.count = n }
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
.config { padding: 24px; margin-bottom: 24px; }
.cfg-row { display: flex; align-items: flex-start; margin-bottom: 18px; }
.cfg-label { width: 60px; color: var(--c-ink-2); font-size: 13px; padding-top: 6px; flex-shrink: 0; }
.opts { display: flex; flex-wrap: wrap; gap: 10px; }
.pill {
  padding: 6px 16px; border-radius: 20px; cursor: pointer;
  border: 1px solid var(--c-line); font-size: 13px; background: var(--c-surface);
  transition: all .15s;
}
.pill:hover { border-color: var(--c-primary); color: var(--c-primary); }
.pill.on {
  background: var(--c-primary); color: #fff; border-color: var(--c-primary);
}
.start { margin-left: 60px; }
.pill.custom {
  display: inline-flex; align-items: center; gap: 8px; padding: 4px 12px;
}
.custom-input { width: 80px; }
.custom-input :deep(.el-input__wrapper) {
  padding: 0 8px; box-shadow: none; background: transparent;
}
.custom.on .custom-input :deep(.el-input__wrapper) {
  background: rgba(255,255,255,.2); box-shadow: 0 0 0 1px #fff inset;
}
.custom-input :deep(input) { text-align: center; font-size: 13px; }
.sec-title { font-size: 15px; font-weight: 600; margin: 0 0 12px; }
.more { text-align: center; margin: 16px 0; }
</style>
