<template>
  <section class="card batch-import" aria-label="批量导入题目">
    <h3>批量导入题目</h3>
    <p class="hint">每批 1—50 道单选题。先预览核对，再整批送审；审核通过后学生才能练习。</p>
    <div class="actions">
      <el-button :disabled="!!busy" @click="downloadExample">下载自编题 JSON 示例</el-button>
      <label class="file-label" for="question-import-file">选择 JSON 文件（最大 2 MiB）</label>
      <input id="question-import-file" type="file" accept=".json,application/json" :disabled="!!busy" @change="readFile" />
    </div>
    <p class="hint">示例含 408 四科共 8 道自编练习，不是真题。收纳真题时请逐题填写来源、年份、原题号和使用权限。</p>
    <label for="question-import-json">题目 JSON（也可直接粘贴）</label>
    <el-input id="question-import-json" v-model="input" type="textarea" :rows="10" :disabled="!!busy" placeholder='{"questions": [{...题目与来源字段...}]}' />
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="actions">
      <el-button :disabled="!!busy" @click="emit('cancel')">关闭批量导入</el-button>
      <el-button :loading="busy === 'preview'" :disabled="!!busy || !!imported" @click="preview">校验并预览</el-button>
      <el-button type="primary" :loading="busy === 'import'" :disabled="!checked || !!busy || !!imported" @click="submit">确认整批送审</el-button>
    </div>
    <div v-if="imported" class="success" role="status">
      已导入 {{ imported.count }} 道题，全部等待审核。题目ID：{{ imported.questions.map(q => q.id).join('、') }}。
      可关闭此面板，在待审核列表逐题核对并发布。
    </div>
    <div v-if="checked" class="preview" aria-label="导入预览">
      <h4>预览 {{ checked.count }} 道题 · 尚未写入题库</h4>
      <p class="hint">展开每题核对标准答案与解析是否一致，并核对来源权限；导入不会自动审核。</p>
      <details v-for="(q, index) in checked.questions" :key="index">
        <summary>第 {{ index + 1 }} 题 · {{ q.subject }} · {{ q.knowledgePoint }} · {{ q.content }}</summary>
        <p v-for="key in optionKeys" :key="key">{{ key }}. {{ q[optionField(key)] }}</p>
        <p>标准答案：{{ q.answer }}</p><p>解析：{{ q.analysis }}</p>
        <p>难度：{{ q.difficulty }} · 来源类别：{{ q.sourceType }}</p>
        <p>来源名称：{{ q.sourceName }}</p><p>来源定位：{{ q.sourceLocator }}</p>
        <p>年份：{{ q.sourceYear ?? '未登记' }} · 原题号：{{ q.sourceQuestionNo || '未登记' }}</p>
        <p>使用权限说明：{{ q.permissionNote }}</p>
      </details>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import { importQuestions, previewQuestionImport } from '@/api/question'
import type { QuestionEntry, QuestionImportResult, QuestionImportPreview } from '@/types/question-entry'
import example from '@/assets/question-import-example.json'

const emit = defineEmits<{ imported: [result: QuestionImportResult]; cancel: [] }>()
const input = ref('')
const checked = ref<QuestionImportPreview>()
const imported = ref<QuestionImportResult>()
const busy = ref<'' | 'file' | 'preview' | 'import'>('')
const error = ref('')
let payload: { questions: QuestionEntry[] } | undefined
let alive = true
const optionKeys = ['A', 'B', 'C', 'D'] as const
const optionField = (key: typeof optionKeys[number]) => `option${key}` as 'optionA' | 'optionB' | 'optionC' | 'optionD'
watch(input, () => { checked.value = undefined; imported.value = undefined; payload = undefined; error.value = '' }, { flush: 'sync' })
onBeforeUnmount(() => { alive = false })

function downloadExample() {
  const url = URL.createObjectURL(new Blob([JSON.stringify(example, null, 2)], { type: 'application/json;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = 'question-import-example.json'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
async function readFile(event: Event) {
  const element = event.target as HTMLInputElement
  const file = element.files?.[0]
  if (!file || busy.value) return
  checked.value = undefined; payload = undefined; error.value = ''; imported.value = undefined
  if (file.size > 2 * 1024 * 1024) { error.value = '文件超过 2 MiB，请拆分为每批最多50题。'; element.value = ''; return }
  busy.value = 'file'
  try { const text = await file.text(); if (alive) input.value = text.replace(/^\uFEFF/, '') }
  catch { if (alive) error.value = '文件读取失败，请重新选择 UTF-8 JSON 文件。' }
  finally { if (alive) busy.value = ''; element.value = '' }
}
function failureMessage(failure: unknown) {
  return axios.isAxiosError(failure) && typeof failure.response?.data?.message === 'string'
    ? failure.response.data.message : '请求未完成，请检查网络和后端服务。'
}
async function preview() {
  if (busy.value || imported.value) return
  checked.value = undefined; payload = undefined; error.value = ''
  let parsed: unknown
  try { parsed = JSON.parse(input.value.replace(/^\uFEFF/, '')) }
  catch { error.value = 'JSON 格式不正确，请参考下载的示例，检查引号和逗号。'; return }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)
    || !('questions' in parsed) || !Array.isArray(parsed.questions)
    || parsed.questions.length < 1 || parsed.questions.length > 50) {
    error.value = '请输入 {"questions": [...]}，每批1至50道题。'; return
  }
  busy.value = 'preview'
  try {
    // Send the original object: never strip unknown fields and silently accept forged publication data.
    const request = parsed as { questions: QuestionEntry[] }
    const result = await previewQuestionImport(request)
    if (alive) { checked.value = result; payload = request }
  } catch (failure) { if (alive) error.value = `校验未通过：${failureMessage(failure)} 内容已保留。` }
  finally { if (alive) busy.value = '' }
}
async function submit() {
  if (busy.value || !checked.value || !payload || imported.value) return
  busy.value = 'import'; error.value = ''
  try {
    const result = await importQuestions(payload)
    if (alive) { imported.value = result; checked.value = undefined; payload = undefined; emit('imported', result) }
  } catch (failure) {
    if (alive) {
      checked.value = undefined; payload = undefined
      error.value = `导入未确认：${failureMessage(failure)} 内容已保留。若请求超时或中断，请先刷新待审核列表核对是否已保存，再重新校验；不要直接重复导入。`
    }
  } finally { if (alive) busy.value = '' }
}
</script>

<style scoped>
.batch-import { padding: 20px; margin: 18px 0; min-width: 0; }
h3 { margin-top: 0; }
.hint { color: var(--c-ink-2); line-height: 1.7; }
label { display: block; margin: 8px 0; }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 16px 0; }
.actions .el-button { margin-left: 0; }
input[type=file] { max-width: 100%; min-width: 0; }
.error { color: var(--c-danger); }
.success { color: var(--c-success); }
.error, .success, details { overflow-wrap: anywhere; line-height: 1.7; }
details { padding: 12px 0; border-bottom: 1px solid var(--c-line); }
summary { cursor: pointer; }
details p { white-space: pre-wrap; }
@media(max-width: 600px) { .batch-import { padding: 16px; } }
</style>
