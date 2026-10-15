<template>
  <div class="page">
    <el-page-header @back="router.push('/practice')" title="返回刷题" :icon="ArrowLeft" />

    <!-- 回顾模式（分页） -->
    <template v-if="reviewMode">
      <div class="card summary">
        <div class="sum-item"><div class="sum-num">{{ reviewTotal }}</div><div class="sum-lbl">总题数</div></div>
        <div class="sum-item"><div class="sum-num" style="color:var(--c-success)">{{ correctCount }}</div><div class="sum-lbl">答对</div></div>
        <div class="sum-item"><div class="sum-num" style="color:var(--c-danger)">{{ reviewTotal - correctCount }}</div><div class="sum-lbl">答错</div></div>
        <div class="sum-item"><div class="sum-num" style="color:var(--c-primary)">{{ accuracy }}%</div><div class="sum-lbl">正确率</div></div>
      </div>

      <div v-for="(rec, i) in reviewItems" :key="rec.questionId" class="card q-card">
        <div class="q-head">
          <span class="q-no">{{ (reviewPage - 1) * reviewSize + i + 1 }}</span>
          <span class="q-content">{{ rec.content }}</span>
          <el-tag v-if="rec.isCorrect === 1" type="success" effect="dark" size="small">答对</el-tag>
          <el-tag v-else type="danger" effect="dark" size="small">答错</el-tag>
        </div>
        <div class="opts">
          <div
            v-for="opt in optionsFor(rec)"
            :key="opt.key"
            class="opt"
            :class="optClass(rec, opt.key)"
          >
            <span class="opt-key">{{ opt.key }}</span>
            <span class="opt-text">{{ opt.text }}</span>
            <span v-if="opt.key === rec.answer" class="opt-mark">✓ 正确答案</span>
            <span v-else-if="opt.key === rec.userAnswer" class="opt-mark">你的选择</span>
          </div>
        </div>
        <div v-if="rec.analysis" class="analysis">
          <b>解析：</b>{{ rec.analysis }}
        </div>
      </div>
      <div v-if="reviewItems.length < reviewTotal" class="more">
        <el-button size="large" :loading="reviewLoading" @click="loadReviewMore">加载更多</el-button>
      </div>
    </template>

    <!-- 答题模式 -->
    <template v-else>
      <div v-if="!finished" class="card q-card" v-loading="loading">
        <div class="progress-row">
          <span class="p-text">第 {{ idx + 1 }} / {{ records.length }} 题</span>
          <el-progress :percentage="percent" :stroke-width="6" style="flex:1; margin-left:16px" />
        </div>
        <h3 class="q-title">{{ cur?.content }}</h3>
        <div class="opts">
          <div
            v-for="opt in optionsFor(cur)"
            :key="opt.key"
            class="opt"
            :class="{ picked: answer === opt.key }"
            @click="answer = opt.key"
          >
            <span class="opt-key">{{ opt.key }}</span>
            <span class="opt-text">{{ opt.text }}</span>
          </div>
        </div>
        <div v-if="revealed" class="feedback" :class="lastCorrect ? 'ok' : 'bad'">
          {{ lastCorrect ? '回答正确' : `回答错误，正确答案：${cur?.answer}` }}
          <p v-if="cur?.analysis">解析：{{ cur.analysis }}</p>
        </div>
        <div class="actions">
          <el-button type="primary" size="large" :disabled="!answer" :loading="answering" @click="submit">
            {{ !revealed ? '提交答案' : (idx === records.length - 1 ? '完成，查看结果' : '下一题') }}
          </el-button>
        </div>
      </div>

      <div v-else class="card q-card">
        <el-result icon="success" title="本次练习完成">
          <template #extra>
            <el-button type="primary" @click="enterReview">查看回顾</el-button>
            <el-button :loading="aiLoading" @click="doAiSummary">生成 AI 总结</el-button>
          </template>
        </el-result>
        <el-alert v-if="aiResult" :title="aiResult" :closable="false" type="success"
          style="margin-top:12px; white-space:pre-wrap; line-height:1.7" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSessionDetail, answerQuestion, getReviewPage, triggerAiSummary, type ReviewRecord } from '@/api/practice'
import { getQuestionDetail } from '@/api/question'
import type { Question } from '@/types/api'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.sessionId as string

const loading = ref(false)
const answering = ref(false)
const records = ref<any[]>([])
const qMap = ref<Record<number, Question>>({})

const idx = ref(0)
const answer = ref('')
const revealed = ref(false)
const lastCorrect = ref(false)
const finished = ref(false)
const reviewMode = ref(false)

// 回顾分页
const reviewItems = ref<ReviewRecord[]>([])
const reviewTotal = ref(0)
const reviewPage = ref(1)
const reviewSize = 10
const reviewLoading = ref(false)
const aiLoading = ref(false)
const aiResult = ref('')

const cur = computed<Question | undefined>(() => {
  const rec = records.value[idx.value]
  return rec ? qMap.value[rec.questionId] : undefined
})
const optionsFor = (q?: Question | ReviewRecord) => [
  { key: 'A', text: q?.optionA },
  { key: 'B', text: q?.optionB },
  { key: 'C', text: q?.optionC },
  { key: 'D', text: q?.optionD }
]
const percent = computed(() => Math.round((idx.value / (records.value.length || 1)) * 100))
const correctCount = computed(() => {
  if (reviewItems.value.length && !records.value.length) {
    return reviewItems.value.filter((r) => r.isCorrect === 1).length
  }
  return records.value.filter((r) => r.isCorrect === 1).length
})
const accuracy = computed(() =>
  reviewTotal.value ? Math.round((correctCount.value / reviewTotal.value) * 100) : 0)

function optClass(rec: any, key: string) {
  const correct = rec.answer
  return {
    'opt-correct': key === correct,
    'opt-wrong': key === rec.userAnswer && key !== correct
  }
}

const submit = async () => {
  if (!revealed.value) {
    const rec = records.value[idx.value]
    answering.value = true
    try {
      await answerQuestion(sessionId, { questionId: rec.questionId, answer: answer.value })
      rec.isCorrect = answer.value === cur.value?.answer ? 1 : 0
      rec.userAnswer = answer.value
      lastCorrect.value = answer.value === cur.value?.answer
      revealed.value = true
    } finally {
      answering.value = false
    }
  } else {
    answer.value = ''
    revealed.value = false
    if (idx.value + 1 >= records.value.length) {
      finished.value = true
    } else {
      idx.value++
      prefetch(idx.value)
    }
  }
}

const prefetch = async (i: number) => {
  const rec = records.value[i]
  if (rec && !qMap.value[rec.questionId]) {
    qMap.value[rec.questionId] = await getQuestionDetail(rec.questionId)
  }
}

const enterReview = async () => {
  reviewMode.value = true
  reviewPage.value = 1
  const r = await getReviewPage(sessionId, { pageNum: 1, pageSize: reviewSize })
  reviewTotal.value = r.total
  reviewItems.value = r.list
}

const loadReviewMore = async () => {
  reviewLoading.value = true
  try {
    reviewPage.value++
    const r = await getReviewPage(sessionId, { pageNum: reviewPage.value, pageSize: reviewSize })
    reviewItems.value = [...reviewItems.value, ...r.list]
  } finally { reviewLoading.value = false }
}

const doAiSummary = async () => {
  aiLoading.value = true
  aiResult.value = ''
  try {
    const t: any = await triggerAiSummary(sessionId)
    if (t.status === 'SUCCESS' && t.resultPayload) {
      const r = t.resultPayload
      aiResult.value = `${r.answer || '无总结内容'}\n${r.weakPoints?.length ? '本次错题涉及：' + r.weakPoints.join('、') : ''}\n${r.explanationMode === 'ai' ? 'AI解释' : '规则总结'} · ${r.releaseId || ''}`
    } else {
      aiResult.value = 'AI 总结失败：' + (t.errorMessage || '未知错误')
    }
  } catch {
    // The shared request wrapper displays the server's error, including missing snapshots.
  } finally { aiLoading.value = false }
}

onMounted(async () => {
  loading.value = true
  try {
    const list: any = await getSessionDetail(sessionId)
    records.value = (list || []).sort((a: any, b: any) => (a.orderIndex || 0) - (b.orderIndex || 0))
    // 已答过的批次直接进回顾模式
    if (records.value.length && records.value.every((r: any) => r.isCorrect != null)) {
      reviewMode.value = true
      const r = await getReviewPage(sessionId, { pageNum: 1, pageSize: reviewSize })
      reviewTotal.value = r.total
      reviewItems.value = r.list
    } else {
      await prefetch(0)
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped lang="scss">
.summary {
  display: grid; grid-template-columns: repeat(4, 1fr);
  padding: 20px; margin-bottom: 20px;
}
.sum-item { text-align: center; }
.sum-num { font-size: 26px; font-weight: 700; }
.sum-lbl { color: var(--c-ink-2); font-size: 13px; margin-top: 4px; }

.q-card { padding: 24px; margin-bottom: 16px; }
.progress-row { display: flex; align-items: center; margin-bottom: 20px; }
.p-text { color: var(--c-ink-2); font-size: 13px; white-space: nowrap; }
.q-title { font-size: 17px; margin: 0 0 20px; line-height: 1.6; }
.q-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 16px; }
.q-no {
  width: 24px; height: 24px; border-radius: 6px; background: var(--c-primary-light);
  color: var(--c-primary); display: grid; place-items: center; font-size: 13px;
  font-weight: 600; flex-shrink: 0;
}
.q-content { flex: 1; font-weight: 600; line-height: 1.6; }

.opts { display: flex; flex-direction: column; gap: 10px; }
.opt {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; border: 1px solid var(--c-line);
  border-radius: var(--r-sm); cursor: pointer; transition: all .15s;
}
.opt:hover { border-color: var(--c-primary); background: var(--c-primary-light); }
.opt.picked { border-color: var(--c-primary); background: var(--c-primary-light); }
.opt-key {
  width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--c-line);
  display: grid; place-items: center; font-size: 12px; font-weight: 600;
  flex-shrink: 0;
}
.opt-text { flex: 1; }
.opt-mark { font-size: 12px; font-weight: 600; }
.opt-correct { background: var(--c-success-light); border-color: var(--c-success); }
.opt-correct .opt-key { background: var(--c-success); color: #fff; border-color: var(--c-success); }
.opt-correct .opt-mark { color: var(--c-success); }
.opt-wrong { background: var(--c-danger-light); border-color: var(--c-danger); }
.opt-wrong .opt-key { background: var(--c-danger); color: #fff; border-color: var(--c-danger); }
.opt-wrong .opt-mark { color: var(--c-danger); }

.feedback { margin-top: 16px; padding: 14px; border-radius: var(--r-sm); font-weight: 500; }
.feedback.ok { background: var(--c-success-light); color: var(--c-success); }
.feedback.bad { background: var(--c-danger-light); color: var(--c-danger); }
.feedback p { margin: 8px 0 0; font-weight: 400; }
.actions { margin-top: 20px; text-align: right; }
.analysis {
  margin-top: 14px; padding: 12px; background: var(--c-bg);
  border-radius: var(--r-sm); color: var(--c-ink-2); font-size: 13px; line-height: 1.6;
}
.more { text-align: center; margin: 16px 0; }
</style>
