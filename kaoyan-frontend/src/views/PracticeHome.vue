<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">开始刷题</h2>
      <p class="page-sub">选择题型、难度和题量，开始一次新的练习</p>
    </div>

    <div class="card config">
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
            v-for="n in [5, 10, 20, 50, 100]" :key="n"
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
import { onMounted, reactive, ref } from 'vue'
import type { InputInstance } from 'element-plus'
import { useRouter } from 'vue-router'
import { startSession, getSessionPage, type SessionSummary } from '@/api/practice'

const router = useRouter()
const subjects = ['数据结构', '操作系统', '计算机网络', '计算机组成原理']
const difficulties = [
  { v: 'EASY', label: '简单' },
  { v: 'MEDIUM', label: '中等' },
  { v: 'HARD', label: '困难' }
]
const cfg = reactive({ subject: '数据结构', difficulty: 'MEDIUM', count: 5 })
const customCount = ref<number | undefined>(undefined)
const customActive = ref(false)
const customRef = ref<InputInstance>()
const onPill = (n: number) => { customActive.value = false; customCount.value = undefined; cfg.count = n }
const onCustom = () => {
  const v = Number(customCount.value)
  if (Number.isFinite(v) && v >= 1 && v <= 500) cfg.count = Math.floor(v)
}
const loading = ref(false)
const historyLoading = ref(false)
const records = ref<SessionSummary[]>([])
const total = ref(0)
const page = ref(1)
const size = 10

const start = async () => {
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

onMounted(loadHistory)
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
