<template>
  <div class="page question-admin">
    <div class="page-head heading">
      <div><h2 class="page-title">题目录入与审核</h2><p class="page-sub">核对题目、来源与使用权限后，再发布给学生练习。</p></div>
      <el-button type="primary" :disabled="editingOpen || reviewing || detailLoading" @click="startEntry()">录入题目</el-button>
    </div>

    <QuestionEntryForm v-if="editingOpen" :key="editing?.id ?? 'new'" :initial="editing" @saved="onSaved" @cancel="editingOpen = false" />
    <p v-if="savedNotice" class="notice" role="status">{{ savedNotice }}</p>

    <form class="lookup" @submit.prevent="lookup">
      <label for="question-lookup">按题目ID查看</label>
      <el-input id="question-lookup" v-model="lookupId" inputmode="numeric" placeholder="查看已保存题目及审核结果" />
      <el-button native-type="submit" :loading="detailLoading" :disabled="editingOpen || reviewing">查看题目</el-button>
    </form>
    <p v-if="detailError" class="error" role="alert">{{ detailError }}</p>

    <section v-if="selected && !editingOpen" class="card detail" aria-label="题目详情">
      <div class="heading"><h3>题目 #{{ selected.id }} · 版本 {{ selected.version }}</h3>
        <el-tag :type="selected.reviewStatus === 'APPROVED' ? 'success' : selected.reviewStatus === 'REJECTED' ? 'danger' : 'warning'">{{ statusName(selected.reviewStatus) }}</el-tag></div>
      <p>启用状态：{{ selected.active === 1 ? '已启用' : '已停用' }}</p>
      <p>{{ selected.subject }} · {{ selected.knowledgePoint }} · {{ selected.difficulty }}</p>
      <h4 class="question-content">{{ selected.content }}</h4>
      <p v-for="key in optionKeys" :key="key" class="option-text">{{ key }}. {{ selected[optionField(key)] || '未填写' }}</p>
      <p><b>标准答案：</b>{{ selected.answer }}</p>
      <p class="pre-wrap"><b>解析：</b>{{ selected.analysis || '未填写' }}</p>
      <div class="source">
        <h4>来源与使用权限</h4>
        <p>来源类别：{{ sourceName(selected.sourceType) }}</p>
        <p>来源名称：{{ selected.sourceName || '待补充' }}</p>
        <p>来源定位：{{ selected.sourceLocator || '待补充' }}</p>
        <p>年份：{{ selected.sourceYear ?? '未登记' }}　原题号：{{ selected.sourceQuestionNo || '未登记' }}</p>
        <p class="pre-wrap">使用权限说明：{{ selected.permissionNote || '待补充' }}</p>
      </div>
      <p v-if="selected.reviewedAt">审核时间：{{ selected.reviewedAt }} · 审核人ID：{{ selected.reviewerUserId }}</p>
      <p v-if="selected.reviewComment" class="pre-wrap">审核意见：{{ selected.reviewComment }}</p>
      <div v-if="selected.reviewStatus === 'PENDING_REVIEW'" class="review-actions">
        <label for="question-review-comment">审核意见（驳回必填）</label>
        <el-input id="question-review-comment" v-model="comment" type="textarea" :rows="2" maxlength="2000" />
        <p class="hint">通过前请核对题干、四个选项、答案、解析和使用权限。</p>
        <div class="buttons">
          <el-button :disabled="reviewing" @click="startEntry(selected)">补充／修改</el-button>
          <el-button type="danger" :loading="reviewing" @click="review('REJECTED')">驳回题目</el-button>
          <el-button type="success" :loading="reviewing" @click="review('APPROVED')">审核通过</el-button>
        </div>
      </div>
      <el-button v-else-if="selected.reviewStatus === 'REJECTED'" @click="startEntry(selected)">修改后重新送审</el-button>
      <div v-else>
        <p class="hint">已发布题目暂不支持原地修改；修订需后续版本发布流程。</p>
        <p v-if="legacySource(selected)" class="hint">旧题来源待补充：六项来源字段均为空，允许依据原审核结果恢复；这不代表来源或使用权限已经核验。</p>
        <el-button :type="selected.active === 1 ? 'danger' : 'success'" :disabled="reviewing || detailLoading" @click="toggleActive">
          {{ selected.active === 1 ? '停用题目' : '重新启用' }}
        </el-button>
      </div>
      <p v-if="reviewError" class="error" role="alert">{{ reviewError }}</p>
      <el-button :disabled="reviewing || detailLoading" @click="showDetail(selected.id)">刷新详情</el-button>
    </section>

    <section class="card queue" aria-label="待审核列表" v-loading="loading">
      <div class="heading"><h3>待审核题目（{{ total }}）</h3><el-button :disabled="loading" @click="load">刷新列表</el-button></div>
      <div v-if="listError" role="alert" class="error">{{ listError }} <el-button @click="load">重试加载</el-button></div>
      <template v-else>
        <el-empty v-if="!loading && !rows.length" description="没有待审核题目" />
        <article v-for="row in rows" :key="row.id" class="queue-item">
          <div><b>#{{ row.id }} · {{ row.subject }}</b><p>{{ row.content }}</p>
            <small>{{ sourceName(row.sourceType) }} · {{ row.sourceName || '来源待补充' }}</small></div>
          <el-button :disabled="reviewing || detailLoading || editingOpen" @click="showDetail(row.id)">查看并审核</el-button>
        </article>
        <div class="pager">
          <el-button :disabled="pageNum <= 1 || loading" @click="changePage(-1)">上一页</el-button>
          <span>第 {{ pageNum }} 页</span>
          <el-button :disabled="pageNum * pageSize >= total || loading" @click="changePage(1)">下一页</el-button>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { getAdminPending, getAdminQuestion, reviewQuestion, changeQuestionActive } from '@/api/question'
import type { AdminQuestion } from '@/types/question-entry'
import QuestionEntryForm from '@/components/QuestionEntryForm.vue'

const rows = ref<AdminQuestion[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = 10
const loading = ref(false)
const listError = ref('')
const selected = ref<AdminQuestion>()
const detailLoading = ref(false)
const detailError = ref('')
const lookupId = ref('')
const editingOpen = ref(false)
const editing = ref<AdminQuestion>()
const savedNotice = ref('')
const comment = ref('')
const reviewing = ref(false)
const reviewError = ref('')
const legacySource = (q: AdminQuestion) => [q.sourceType, q.sourceName, q.sourceLocator,
  q.sourceYear, q.sourceQuestionNo, q.permissionNote].every(value => value == null)
const optionKeys = ['A', 'B', 'C', 'D'] as const
const optionField = (key: typeof optionKeys[number]) => `option${key}` as 'optionA' | 'optionB' | 'optionC' | 'optionD'
const statusName = (status: string) => ({ PENDING_REVIEW: '待审核', APPROVED: '审核通过', REJECTED: '已驳回' }[status] || status)
const sourceName = (type?: string | null) => ({ REAL_EXAM: '真题', MOCK: '模拟题', ORIGINAL: '自编题' }[type || ''] || '待补充')

async function load() {
  loading.value = true; listError.value = ''
  try {
    let result = await getAdminPending({ pageNum: pageNum.value, pageSize })
    if (!result.list.length && pageNum.value > 1 && result.total < (pageNum.value - 1) * pageSize + 1) {
      pageNum.value = Math.max(1, Math.ceil(result.total / pageSize))
      result = await getAdminPending({ pageNum: pageNum.value, pageSize })
    }
    rows.value = result.list; total.value = result.total
  } catch { listError.value = '待审核列表加载失败，请重试。' }
  finally { loading.value = false }
}
async function changePage(delta: number) { pageNum.value += delta; await load() }
function startEntry(question?: AdminQuestion) {
  editing.value = question; editingOpen.value = true; savedNotice.value = ''; reviewError.value = ''
}
async function onSaved(question: AdminQuestion) {
  editingOpen.value = false; selected.value = question; comment.value = ''; reviewError.value = ''
  savedNotice.value = `题目 #${question.id} 已保存，等待审核。`
  pageNum.value = 1
  await load()
}
async function showDetail(id: number) {
  if (detailLoading.value || reviewing.value) return
  selected.value = undefined; detailLoading.value = true; detailError.value = ''; reviewError.value = ''; comment.value = ''
  try { selected.value = await getAdminQuestion(id) }
  catch { detailError.value = '题目详情读取失败，请核对ID或重试。' }
  finally { detailLoading.value = false }
}
async function lookup() {
  if (editingOpen.value || reviewing.value) return
  const id = Number(lookupId.value)
  if (!/^\d+$/.test(lookupId.value) || !Number.isSafeInteger(id) || id < 1) { detailError.value = '请输入有效的正整数题目ID。'; return }
  await showDetail(id)
}
async function review(status: 'APPROVED' | 'REJECTED') {
  if (!selected.value || reviewing.value) return
  if (status === 'REJECTED' && !comment.value.trim()) { reviewError.value = '驳回请填写审核意见。'; return }
  const id = selected.value.id
  reviewing.value = true; reviewError.value = ''
  try {
    await reviewQuestion(id, { status, comment: comment.value.trim(), version: selected.value.version })
    // Do not synthesize an audit record if a follow-up read fails.
    selected.value = undefined
    savedNotice.value = status === 'APPROVED' ? `题目 #${id} 审核通过。` : `题目 #${id} 已驳回。`
    await load()
    try { selected.value = await getAdminQuestion(id) }
    catch { detailError.value = '审核已保存，详情读取失败；可按题目ID重新查看。' }
  } catch { reviewError.value = '审核未成功，请查看错误信息并刷新详情后重试。' }
  finally { reviewing.value = false }
}
async function toggleActive() {
  if (!selected.value || reviewing.value || detailLoading.value || editingOpen.value) return
  const { id, version } = selected.value
  const active = selected.value.active === 1 ? 0 : 1
  const action = active === 0 ? '停用' : '重新启用'
  // Guard before opening the confirmation so detail selection cannot change underneath it.
  reviewing.value = true; reviewError.value = ''
  try {
    await ElMessageBox.confirm(active === 0
      ? '停用后学生不能抽取或继续作答，题目和历史记录保留。确认停用？'
      : '将按当前审核状态及题目信息重新启用。确认恢复学生练习？', `确认${action}`, { type: 'warning' })
  } catch { reviewing.value = false; return }
  try {
    const saved = await changeQuestionActive(id, { active, version })
    selected.value = saved
    savedNotice.value = `题目 #${id} 已${action}。`
    try { selected.value = await getAdminQuestion(id) }
    catch { detailError.value = '状态已保存，详情刷新失败；请刷新详情核对。' }
  } catch { reviewError.value = '状态切换未成功，请核对错误信息并刷新详情后重试。' }
  finally { reviewing.value = false }
}
onMounted(load)
</script>

<style scoped>
.heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.heading h3 { margin: 0; }
.queue, .detail { padding: 20px; margin: 18px 0; }
.lookup { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 20px; }
.lookup .el-input { flex: 1; min-width: 120px; max-width: 330px; }
.detail, .queue-item, .notice { overflow-wrap: anywhere; }
.question-content, .pre-wrap { white-space: pre-wrap; line-height: 1.7; }
.option-text { white-space: pre-wrap; }
.source { background: var(--c-bg); border-radius: 8px; padding: 12px; margin: 16px 0; }
.source h4 { margin-top: 0; }
.source p { line-height: 1.7; }
.review-actions { margin: 18px 0; }
.review-actions label { display: block; margin-bottom: 8px; }
.buttons { display: flex; flex-wrap: wrap; gap: 10px; }
.buttons .el-button { margin-left: 0; }
.hint { color: var(--c-ink-2); line-height: 1.6; }
.notice { color: var(--c-success); }
.error { color: var(--c-danger); line-height: 1.6; }
.queue-item { display: flex; gap: 12px; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--c-line); padding: 16px 0; }
.queue-item > div { min-width: 0; }
.queue-item small { color: var(--c-ink-2); }
.pager { display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 20px; }
@media (max-width: 600px) {
  .page { padding: 16px; }
  .queue, .detail { padding: 16px; }
  .queue-item { align-items: flex-start; flex-direction: column; }
  .lookup .el-input { min-width: 0; max-width: none; flex-basis: 100%; }
  .pager { gap: 6px; font-size: 12px; }
}
</style>
