<template>
  <div class="page" v-loading="loading">
    <el-page-header title="返回练习" @back="router.push('/practice')" />
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-button v-if="error" @click="load">重新读取服务端进度</el-button>
    <template v-if="state">
      <h2>{{ state.kind === 'DIAGNOSTIC' ? '单选诊断' : '练习' }} · {{ state.state === 'RUNNING' ? '进行中' : '已结束' }}</h2>
      <el-alert v-if="state.kind === 'DIAGNOSTIC'" title="诊断结束后统一展示正误与解析。局部诊断不能估计完整408分数。" :closable="false" />
      <p v-for="m in state.blueprint.missing" :key="m.subject + m.difficulty">缺题：{{ m.subject }} / {{ m.difficulty }}，缺 {{ m.missing }} 题</p>
      <div class="answer-card">
        <el-button v-for="(item, i) in state.items" :key="item.itemId" :type="i === index ? 'primary' : item.submitted ? 'success' : 'default'" @click="move(i)">{{ i + 1 }}{{ item.withdrawn ? '撤回' : item.hintLevelUsed ? '提示' : '' }}</el-button>
      </div>
      <section v-if="current" class="card question">
        <p>{{ index + 1 }} / {{ state.items.length }} · {{ current.subject }} · {{ current.knowledgePoint }} · {{ current.difficulty }}</p>
        <h3>{{ current.content }}</h3>
        <el-alert v-if="current.withdrawn" title="该版本已撤回，不参与作答与有效统计。" type="warning" :closable="false" />
        <el-radio-group v-else v-model="answer" :disabled="current.submitted || state.state !== 'RUNNING' || loading" @change="draft">
          <el-radio v-for="option in options" :key="option.key" :value="option.key">{{ option.key }}. {{ option.text }}</el-radio>
        </el-radio-group>
        <p v-if="saveMessage" role="status">{{ saveMessage }}</p>
        <p v-if="current.submitted">已提交：{{ current.userAnswer }}</p>
        <template v-if="current.isCorrect != null">
          <el-tag :type="current.isCorrect === 1 ? 'success' : 'danger'">{{ current.isCorrect === 1 ? '答对' : '答错' }}</el-tag>
          <p>标准答案：{{ current.answer }}</p><p>{{ current.analysis }}</p>
          <WrongQuestionTutor v-if="current.isCorrect === 0 && !current.withdrawn" :key="current.itemId" :record-id="current.itemId" />
        </template>
        <p v-if="hintText">提示：{{ hintText }}</p>
        <div class="actions" v-if="state.state === 'RUNNING'">
          <el-button type="primary" :disabled="!answer || current.submitted || current.withdrawn || loading || !!error" @click="submit">提交本题</el-button>
          <el-button v-if="state.kind !== 'DIAGNOSTIC' && !current.submitted && !current.withdrawn" :disabled="loading" @click="hint">{{ current.hintLevelUsed >= 1 ? '查看解题方向' : '查看概念提示' }}</el-button>
          <el-button :disabled="loading" @click="finish">结束批次并查看结果</el-button>
        </div>
      </section>
      <section v-if="result && state.state !== 'RUNNING'" class="card question">
        <h3>批次结果</h3>
        <p>有效已答 {{ result.answered }} · 未答 {{ result.unanswered }} · 撤回 {{ result.withdrawn }} · 正确 {{ result.correct }}</p>
        <p>正确率 {{ percent(result.accuracy) }} · 独立正确率 {{ percent(result.independentAccuracy) }} · 提示辅助 {{ result.assisted }}</p>
        <p v-if="result.diagnosticReferenceScore != null">单选诊断参考分：{{ result.diagnosticReferenceScore }} / 150</p>
        <p>{{ result.notice }}</p><p v-if="result.profilePending">学情正在后台更新，可在学习统计中查看。</p>
        <p v-if="result.profileUpdateFailed" role="alert">学情更新失败，已保留判分记录，请联系维护者检查后台事件。</p>
        <el-button @click="router.push('/stat')">查看学情画像</el-button>
      </section>
    </template>
  </div>
</template>
<script setup lang="ts">
import WrongQuestionTutor from '@/components/WrongQuestionTutor.vue'
import { computed, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { managedState, managedResult, saveProgress, submitManaged, finishManaged, managedHint, type ManagedState, type ManagedResult } from '@/api/learning'
const route = useRoute(), router = useRouter(), id = String(route.params.sessionId)
const state = ref<ManagedState>(), result = ref<ManagedResult>(), index = ref(0), answer = ref('')
const loading = ref(false), error = ref(''), saveMessage = ref(''), hintText = ref('')
// Preserve the same request ID and content after an uncertain transport result.
let pending: { itemId: number; answer: string; id: string } | undefined
const current = computed(() => state.value?.items[index.value])
const options = computed(() => ['A', 'B', 'C', 'D'].map(key => ({ key, text: current.value?.[`option${key}` as 'optionA'] })).filter(o => o.text))
const percent = (v: number | null) => v == null ? '暂无数据' : `${Math.round(v * 100)}%`
function show() { answer.value = current.value?.userAnswer || current.value?.draftAnswer || ''; hintText.value = '' }
async function load() {
  loading.value = true; error.value = ''
  try {
    state.value = await managedState(id); index.value = Math.min(state.value.currentIndex, state.value.items.length - 1); show()
    if (state.value.state !== 'RUNNING') result.value = await managedResult(id)
  } catch { error.value = '读取失败，请重试。服务端已保存的进度不会丢失。' }
  finally { loading.value = false }
}
async function draft() {
  if (!state.value || !current.value || loading.value) return
  loading.value = true; saveMessage.value = '正在保存'; error.value = ''
  try { state.value = await saveProgress(id, state.value.revision, index.value, { [current.value.itemId]: answer.value }); saveMessage.value = '已保存到服务端' }
  catch { error.value = '草稿保存失败或版本冲突，请重新读取服务端进度后再操作。'; saveMessage.value = '尚未保存' }
  finally { loading.value = false }
}
async function move(value: number) {
  if (loading.value || error.value) return
  index.value = value; show(); saveMessage.value = ''
  if (state.value?.state === 'RUNNING') {
    loading.value = true
    try { state.value = await saveProgress(id, state.value.revision, index.value, {}) }
    catch { error.value = '位置保存失败，请重新读取。' }
    finally { loading.value = false }
  }
}
async function submit() {
  if (!current.value || loading.value || error.value) return
  if (pending && (pending.itemId !== current.value.itemId || pending.answer !== answer.value)) {
    ElMessage.info('上次提交结果尚未确认，请先重新读取进度。'); return
  }
  pending ??= { itemId: current.value.itemId, answer: answer.value, id: crypto.randomUUID() }
  loading.value = true
  try { await submitManaged(id, current.value, pending.answer, pending.id); pending = undefined; await load() }
  catch { error.value = '提交结果尚未确认，请重新读取进度；相同内容重试不会重复计数。' }
  finally { loading.value = false }
}
async function finish() {
  try { await ElMessageBox.confirm('结束后不能继续作答。未提交选择不计作答，未答不计错题。', '结束批次') } catch { return }
  loading.value = true
  try { result.value = await finishManaged(id); state.value = result.value.session; show() }
  catch { error.value = '结束结果尚未确认，可重新读取或重复结束。' }
  finally { loading.value = false }
}
async function hint() {
  if (!current.value) return
  loading.value = true
  try {
    const response = await managedHint(id, current.value.itemId, Math.min(current.value.hintLevelUsed + 1, 2))
    hintText.value = response.available ? response.text || '' : '该题尚未提供已审核提示'
    current.value.hintLevelUsed = response.hintLevelUsed
  } finally { loading.value = false }
}
onBeforeRouteLeave(() => !loading.value)
onMounted(load)
</script>
<style scoped>
.question { padding: 24px; margin-top: 16px; overflow-wrap: anywhere; }
.answer-card, .actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0; }
.answer-card .el-button + .el-button, .actions .el-button + .el-button { margin-left: 0; }
.el-radio-group { display: flex; flex-direction: column; align-items: flex-start; }
.el-radio { height: auto; white-space: normal; margin: 12px 0; }
:deep(.el-radio__label) { white-space: normal; line-height: 1.6; }
</style>
