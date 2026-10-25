<template>
  <div class="page">
    <el-page-header @back="router.push('/practice')" title="返回刷题" :icon="ArrowLeft" />
    <el-alert v-if="skippedIds.size" class="notice" type="warning" :closable="false"
      :title="`题目已不可用，已跳过 ${skippedIds.size} 题；跳过不会提交答案或修改作答统计。`" />
    <div v-if="loadError" class="notice" role="alert">
      <el-alert :title="loadError" type="error" :closable="false" />
      <el-button :loading="loading" :disabled="answering || reviewLoading" @click="navigate(true)">重试加载</el-button>
    </div>

    <!-- 回顾模式（分页） -->
    <template v-if="reviewMode">
      <div v-if="hasPending" class="actions">
        <el-button type="primary" :loading="loading" :disabled="answering || reviewLoading" @click="navigate(true)">继续作答</el-button>
      </div>
      <div class="card summary">
        <div class="sum-item"><div class="sum-num">{{ reviewTotal }}</div><div class="sum-lbl">总题数</div></div>
        <div class="sum-item"><div class="sum-num" style="color:var(--c-success)">{{ correctCount }}</div><div class="sum-lbl">答对</div></div>
        <div class="sum-item"><div class="sum-num" style="color:var(--c-danger)">{{ wrongCount }}</div><div class="sum-lbl">答错</div></div>
        <div class="sum-item"><div class="sum-num">{{ unansweredCount }}</div><div class="sum-lbl">未作答</div></div>
        <div class="sum-item"><div class="sum-num" style="color:var(--c-primary)">{{ accuracy }}%</div><div class="sum-lbl">正确率</div></div>
      </div>

      <div v-for="(rec, i) in reviewItems" :key="rec.questionId" class="card q-card">
        <div class="q-head">
          <span class="q-no">{{ i + 1 }}</span>
          <span class="q-content">{{ rec.content || '历史题目内容不可用' }}</span>
          <el-tag v-if="rec.isCorrect === 1" type="success" effect="dark" size="small">答对</el-tag>
          <el-tag v-else-if="rec.isCorrect === 0" type="danger" effect="dark" size="small">答错</el-tag>
          <el-tag v-else type="info" size="small">未作答</el-tag>
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
            <span v-if="canShowAnswer(rec) && opt.key === rec.answer" class="opt-mark">✓ 正确答案</span>
            <span v-else-if="opt.key === rec.userAnswer" class="opt-mark">你的选择</span>
          </div>
        </div>
        <div v-if="canShowAnswer(rec)" class="saved-answer">
          <p>正确答案：{{ rec.answer }}</p>
          <p v-if="rec.userAnswer">你的选择：{{ rec.userAnswer }}</p>
        </div>
        <div v-if="canShowAnswer(rec) && rec.analysis" class="analysis">
          <b>解析：</b>{{ rec.analysis }}
        </div>
        <p v-if="historyNotice(rec.snapshotStatus)" class="analysis">{{ historyNotice(rec.snapshotStatus) }}</p>
        <WrongQuestionTutor v-if="rec.isCorrect === 0 && rec.recordId && rec.snapshotStatus === 'AVAILABLE'"
          :record-id="rec.recordId" />
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
            @click="!revealed && !busy && !loadError && (answer = opt.key)"
          >
            <span class="opt-key">{{ opt.key }}</span>
            <span class="opt-text">{{ opt.text }}</span>
          </div>
        </div>
        <div v-if="revealed" class="feedback" :class="lastCorrect ? 'ok' : 'bad'">
          {{ lastCorrect ? '回答正确' : `回答错误，正确答案：${feedback?.answer}` }}
          <p v-if="feedback?.analysis">解析：{{ feedback.analysis }}</p>
        </div>
        <WrongQuestionTutor v-if="revealed && feedback?.isCorrect === 0 && feedback.recordId"
          :key="feedback.recordId" :record-id="feedback.recordId" />
        <div class="actions">
          <el-button type="primary" size="large" :disabled="!answer || busy || !cur || !!loadError" :loading="answering" @click="submit">
            {{ !revealed ? '提交答案' : (idx === records.length - 1 ? '完成，查看结果' : '下一题') }}
          </el-button>
          <el-button :disabled="busy" @click="enterReview">查看已保存作答</el-button>
        </div>
      </div>

      <div v-else class="card q-card">
        <el-result :icon="canSummarize ? 'success' : 'info'" :title="canSummarize ? '本次练习完成' : '暂无可继续作答的题目'"
          :sub-title="canSummarize ? undefined : '不可用题目未提交，不计为答错。可查看已保存作答或重新检查题目。'">
          <template #extra>
            <el-button type="primary" :disabled="busy" @click="enterReview">查看回顾</el-button>
            <el-button v-if="!canSummarize" :loading="loading" :disabled="answering || reviewLoading" @click="navigate(true)">重新检查题目</el-button>
            <el-button :loading="aiLoading" :disabled="busy || !canSummarize" @click="doAiSummary">生成 AI 总结</el-button>
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
import { useAssistantPage } from '@/composables/assistant-page'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { getSessionDetail, answerQuestion, getReviewPage, triggerAiSummary, type ReviewRecord, type AnswerResult } from '@/api/practice'
import { getQuestionDetail } from '@/api/question'
import type { StudentQuestion, PracticeRecord } from '@/types/api'
import { historyNotice } from '@/utils/question-history'
import { ArrowLeft } from '@element-plus/icons-vue'
import WrongQuestionTutor from '@/components/WrongQuestionTutor.vue'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.sessionId as string

const loading = ref(false)
const answering = ref(false)
const records = ref<PracticeRecord[]>([])
const qMap = ref<Record<number, StudentQuestion>>({})
const feedback = ref<AnswerResult | null>(null)
const skippedIds = ref(new Set<number>())
const loadError = ref('')

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
const busy = computed(() => loading.value || answering.value || reviewLoading.value || aiLoading.value)
const valid = (record: PracticeRecord) => record.gradingStatus == null || record.gradingStatus === 'valid'
const hasPending = computed(() => records.value.some(r => valid(r) && r.isCorrect == null))
const canSummarize = computed(() => records.value.some(valid) && !hasPending.value)

const cur = computed<StudentQuestion | undefined>(() => {
  const rec = records.value[idx.value]
  return rec ? qMap.value[rec.questionId] : undefined
})
const optionsFor = (q?: StudentQuestion | ReviewRecord) => [
  { key: 'A', text: q?.optionA },
  { key: 'B', text: q?.optionB },
  { key: 'C', text: q?.optionC },
  { key: 'D', text: q?.optionD }
].filter(opt => opt.text != null)
const percent = computed(() => Math.round((idx.value / (records.value.length || 1)) * 100))
const correctCount = computed(() => records.value.filter(r => r.isCorrect === 1).length)
const wrongCount = computed(() => records.value.filter(r => r.isCorrect === 0).length)
const unansweredCount = computed(() => records.value.filter(r => r.isCorrect == null).length)
const accuracy = computed(() =>
  correctCount.value + wrongCount.value ? Math.round(correctCount.value / (correctCount.value + wrongCount.value) * 100) : 0)

function optClass(rec: ReviewRecord, key: string) {
  const correct = canShowAnswer(rec) ? rec.answer : undefined
  return {
    'opt-correct': key === correct,
    'opt-wrong': Boolean(correct) && key === rec.userAnswer && key !== correct
  }
}

const canShowAnswer = (rec: ReviewRecord) => rec.isCorrect != null &&
  (rec.snapshotStatus === 'AVAILABLE' || rec.snapshotStatus === 'PARTIAL') && Boolean(rec.answer)

const readRecords = async () => (await getSessionDetail(sessionId))
  .slice().sort((a, b) => (a.orderIndex || 0) - (b.orderIndex || 0))

// Only explicit unavailability permits skipping. Transport failures keep a retry path.
async function findNext(list: PracticeRecord[], skipped: Set<number>) {
  for (let index = 0; index < list.length; index++) {
    const rec = list[index]
    if (rec.isCorrect != null) continue
    if (!valid(rec)) skipped.add(rec.questionId)
    if (skipped.has(rec.questionId)) continue
    try {
      return { index, question: await getQuestionDetail(rec.questionId), skipped }
    } catch (error) {
      if (!axios.isAxiosError(error) || error.response?.status !== 404) throw error
      skipped.add(rec.questionId)
    }
  }
  return { index: -1, question: undefined, skipped }
}

function showNext(list: PracticeRecord[], next: Awaited<ReturnType<typeof findNext>>) {
  records.value = list
  skippedIds.value = next.skipped
  if (next.question) {
    idx.value = next.index
    qMap.value[list[next.index].questionId] = next.question
  }
  answer.value = ''
  revealed.value = false
  feedback.value = null
  finished.value = next.index < 0
  reviewMode.value = false
}

async function showReview(list: PracticeRecord[]) {
  const result = await getReviewPage(sessionId, { pageNum: 1, pageSize: reviewSize })
  records.value = list
  reviewPage.value = 1
  reviewTotal.value = result.total
  reviewItems.value = result.list
  reviewMode.value = true
}

async function navigate(refresh = false, initial = false) {
  if (busy.value) return
  loading.value = true
  loadError.value = ''
  try {
    const list = refresh ? await readRecords() : records.value
    if (initial && list.length && list.every(r => r.isCorrect != null)) {
      await showReview(list)
    } else {
      const next = await findNext(list, refresh ? new Set<number>() : new Set(skippedIds.value))
      showNext(list, next)
    }
  } catch (error) {
    if (!axios.isCancel(error)) loadError.value = '加载题目失败，请重试。已保存的作答不会改变。'
  } finally { loading.value = false }
}

async function recoverSubmission(questionId: number) {
  const list = await readRecords()
  const record = list.find(r => r.questionId === questionId)
  if (!record) throw new Error('作答记录已不可用')
  if (record.isCorrect != null) {
    await showReview(list)
    ElMessage.info('该题已提交，已同步服务端保存的作答。')
    return
  }
  const skipped = new Set(skippedIds.value)
  let unavailable = !valid(record)
  if (!unavailable) {
    try {
      // Recheck even if a question was previously loaded: it may have been withdrawn.
      qMap.value[questionId] = await getQuestionDetail(questionId)
    } catch (error) {
      if (!axios.isAxiosError(error) || error.response?.status !== 404) throw error
      unavailable = true
    }
  }
  if (unavailable) {
    skipped.add(questionId)
    showNext(list, await findNext(list, skipped))
  } else {
    records.value = list
    // A configuration conflict is not a withdrawal and must not silently skip a valid item.
    loadError.value = '提交未成功，请核对错误提示后重试加载。'
  }
}

const submit = async () => {
  if (busy.value || loadError.value || !cur.value) return
  if (!revealed.value) {
    const rec = records.value[idx.value]
    answering.value = true
    try {
      const result = await answerQuestion(sessionId, { questionId: rec.questionId, answer: answer.value })
      feedback.value = result
      rec.isCorrect = result.isCorrect
      rec.userAnswer = result.userAnswer
      lastCorrect.value = result.isCorrect === 1
      revealed.value = true
    } catch (error) {
      if (axios.isCancel(error)) return
      if (axios.isAxiosError(error) && [404, 409].includes(error.response?.status || 0)) {
        try { await recoverSubmission(rec.questionId) } catch (recoveryError) {
          if (!axios.isCancel(recoveryError)) loadError.value = '同步作答失败，请重试加载以确认服务端记录。'
        }
      }
    } finally {
      answering.value = false
    }
  } else {
    await navigate()
  }
}

const enterReview = async () => {
  if (busy.value) return
  loading.value = true
  try {
    await showReview(await readRecords())
    loadError.value = ''
  } catch {
    // Keep the current view; the request wrapper displays the error.
  } finally { loading.value = false }
}

const loadReviewMore = async () => {
  if (busy.value) return
  reviewLoading.value = true
  try {
    const r = await getReviewPage(sessionId, { pageNum: reviewPage.value + 1, pageSize: reviewSize })
    reviewPage.value++
    reviewItems.value = [...reviewItems.value, ...r.list]
  } catch {
    // Keep the current page and allow retrying the same next page.
  } finally { reviewLoading.value = false }
}

const doAiSummary = async () => {
  if (busy.value || !canSummarize.value) return
  aiLoading.value = true
  aiResult.value = ''
  try {
    const t: any = await triggerAiSummary(sessionId)
    if (t.status === 'SUCCESS' && t.resultPayload) {
      const r = t.resultPayload
      aiResult.value = `${r.answer || '无总结内容'}\n${r.weakPoints?.length ? '本次错题涉及：' + r.weakPoints.join('、') : ''}\n${r.explanationMode === 'ai' ? 'AI解释' : '规则总结'}`
    } else {
      aiResult.value = 'AI 总结失败：' + (t.errorMessage || '未知错误')
    }
  } catch {
    // The shared request wrapper displays the server's error, including missing snapshots.
  } finally { aiLoading.value = false }
}

useAssistantPage(() => ({ page: 'practice', sessionId, selectedQuestionIds: !reviewMode.value && cur.value ? [cur.value.id] : [], visibleQuestionIds: reviewMode.value ? reviewItems.value.map(item => item.questionId) : (cur.value ? [cur.value.id] : []) }))
onMounted(() => navigate(true, true))
</script>

<style scoped lang="scss">
.notice { margin: 16px 0; }
.notice .el-button { margin-top: 10px; }
.saved-answer { margin-top: 14px; font-size: 14px; }
.summary {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
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
.q-head .el-tag { flex-shrink: 0; }
.q-no {
  width: 24px; height: 24px; border-radius: 6px; background: var(--c-primary-light);
  color: var(--c-primary); display: grid; place-items: center; font-size: 13px;
  font-weight: 600; flex-shrink: 0;
}
.q-content { flex: 1; min-width: 0; overflow-wrap: anywhere; font-weight: 600; line-height: 1.6; }

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
.actions { margin-top: 20px; display: flex; flex-wrap: wrap; gap: 12px; justify-content: flex-end; }
.actions .el-button + .el-button { margin-left: 0; }
.analysis {
  margin-top: 14px; padding: 12px; background: var(--c-bg);
  border-radius: var(--r-sm); color: var(--c-ink-2); font-size: 13px; line-height: 1.6;
}
.more { text-align: center; margin: 16px 0; }
</style>
