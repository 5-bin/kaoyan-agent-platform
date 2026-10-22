<template>
  <form class="card entry-form" @submit.prevent="save">
    <h3>{{ initial ? `修改未发布题目 #${initial.id}` : '录入单选题' }}</h3>
    <p class="hint">保存后进入待审核；审核通过后才会进入学生题池。请核对内容来源与使用权限。</p>
    <div class="fields">
      <label>科目<select v-model="form.subject" aria-label="科目">
        <option v-for="s in subjects" :key="s">{{ s }}</option>
      </select></label>
      <label>难度<select v-model="form.difficulty" aria-label="难度">
        <option value="EASY">简单</option><option value="MEDIUM">中等</option><option value="HARD">困难</option>
      </select></label>
      <label class="wide" for="entry-point">知识点</label>
      <el-input id="entry-point" v-model="form.knowledgePoint" class="wide" maxlength="255" />
      <label class="wide" for="entry-content">题干</label>
      <el-input id="entry-content" v-model="form.content" class="wide" type="textarea" :rows="3" maxlength="10000" />
      <div v-for="key in optionKeys" :key="key" class="field">
        <label :for="'entry-' + key">选项{{ key }}</label>
        <el-input :id="'entry-' + key" v-model="form[optionField(key)]" maxlength="2000" />
      </div>
      <label>标准答案<select v-model="form.answer" aria-label="标准答案"><option v-for="key in optionKeys" :key="key">{{ key }}</option></select></label>
      <label>来源类别<select v-model="form.sourceType" aria-label="来源类别">
        <option value="ORIGINAL">自编题</option><option value="MOCK">模拟题</option><option value="REAL_EXAM">真题</option>
      </select></label>
      <label class="wide" for="entry-analysis">解析</label>
      <el-input id="entry-analysis" v-model="form.analysis" class="wide" type="textarea" :rows="3" maxlength="10000" />
      <label class="wide" for="entry-source">来源名称／试卷名称</label>
      <el-input id="entry-source" v-model="form.sourceName" class="wide" maxlength="255" placeholder="填写真实试卷、出版物或自编记录名称" />
      <label class="wide" for="entry-locator">来源定位</label>
      <el-input id="entry-locator" v-model="form.sourceLocator" class="wide" maxlength="1000" placeholder="原文地址、页码、章节或自编记录位置" />
      <div class="field"><label for="entry-year">年份{{ form.sourceType === 'REAL_EXAM' ? '（必填）' : '（可选）' }}</label>
        <el-input-number id="entry-year" v-model="form.sourceYear" :min="1900" :max="2100" :controls="false" /></div>
      <div class="field"><label for="entry-number">原题号{{ form.sourceType === 'REAL_EXAM' ? '（必填）' : '（可选）' }}</label>
        <el-input id="entry-number" v-model="form.sourceQuestionNo" maxlength="64" /></div>
      <label class="wide" for="entry-permission">使用权限说明</label>
      <el-input id="entry-permission" v-model="form.permissionNote" class="wide" type="textarea" :rows="2" maxlength="2000" placeholder="填写授权依据或自编署名；公开可读不等于允许复制发布" />
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="actions">
      <el-button :disabled="saving" @click="emit('cancel')">取消录入</el-button>
      <el-button type="primary" native-type="submit" :loading="saving">保存并送审</el-button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { createQuestion, updateQuestion } from '@/api/question'
import type { AdminQuestion, QuestionEntry } from '@/types/question-entry'

const props = defineProps<{ initial?: AdminQuestion }>()
const emit = defineEmits<{ saved: [question: AdminQuestion]; cancel: [] }>()
const subjects = ['数据结构', '操作系统', '计算机组成原理', '计算机网络']
const optionKeys = ['A', 'B', 'C', 'D'] as const
const optionField = (key: typeof optionKeys[number]) => `option${key}` as 'optionA' | 'optionB' | 'optionC' | 'optionD'
const form = reactive<QuestionEntry>({ subject: '数据结构', knowledgePoint: '', difficulty: 'MEDIUM',
  content: '', optionA: '', optionB: '', optionC: '', optionD: '', answer: 'A', analysis: '',
  sourceType: 'ORIGINAL', sourceName: '', sourceLocator: '', sourceYear: undefined, sourceQuestionNo: '', permissionNote: '' })
if (props.initial) {
  // Copy only entry fields; never send server-owned review or publication fields.
  for (const key of Object.keys(form) as (keyof QuestionEntry)[]) {
    const value = props.initial[key]
    if (value != null) Object.assign(form, { [key]: value })
  }
}
const saving = ref(false)
const error = ref('')
async function save() {
  if (saving.value) return
  const required: (keyof QuestionEntry)[] = ['knowledgePoint', 'content', 'optionA', 'optionB', 'optionC', 'optionD',
    'analysis', 'sourceName', 'sourceLocator', 'permissionNote']
  if (required.some(k => !String(form[k] ?? '').trim())) { error.value = '请填写题目、全部选项、解析和来源／使用权限信息。'; return }
  if (form.sourceType === 'REAL_EXAM' && (!form.sourceYear || !form.sourceQuestionNo.trim())) {
    error.value = '真题必须填写年份和原题号。'; return
  }
  saving.value = true; error.value = ''
  try {
    if (props.initial) {
      emit('saved', await updateQuestion(props.initial.id, { ...form }))
    } else emit('saved', await createQuestion({ ...form }))
  } catch { error.value = '保存未成功，内容已保留，请核对错误信息后重试。' }
  finally { saving.value = false }
}
</script>

<style scoped>
.entry-form { padding: 20px; margin: 18px 0; }
h3 { margin: 0 0 8px; }
.hint { color: var(--c-ink-2); line-height: 1.6; }
.fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 16px; }
.fields > label, .field label { display: block; font-weight: 500; }
.field label { margin-bottom: 8px; }
.wide { grid-column: 1 / -1; }
select { display: block; width: 100%; margin-top: 8px; min-height: 34px; border: 1px solid var(--c-line); border-radius: 4px; background: white; color: var(--c-ink); padding: 6px; }
.el-input-number { width: 100%; }
.actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.actions .el-button { margin-left: 0; }
.error { color: var(--c-danger); }
@media (max-width: 600px) { .fields { grid-template-columns: minmax(0, 1fr); } .entry-form { padding: 16px; } }
</style>
