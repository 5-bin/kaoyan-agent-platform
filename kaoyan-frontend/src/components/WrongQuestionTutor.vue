<template>
  <section class="tutor" aria-label="错题 AI 辅导">
    <el-button v-if="!opened" type="primary" plain @click="opened = true">AI 解释与追问</el-button>
    <template v-else>
      <h4>错题 AI 辅导</h4>
      <p class="hint">围绕这次作答提问，标准答案和判分不变。每轮保存在“Agent 助手”的任务历史，可在那里继续追问。</p>
      <div v-for="(message, index) in messages" :key="index" class="message">
        <b>{{ message.role === 'user' ? '你的问题' : '历史解释' }}：</b>{{ message.content }}
      </div>
      <p v-if="lastTask" class="message"><b>你的问题：</b>{{ lastTask.inputPayload?.query }}</p>
      <TaskResultView v-if="lastTask" :task="lastTask" />
      <p v-if="error" role="alert">{{ error }}</p>
      <el-input v-model="query" type="textarea" :rows="3" :maxlength="2000" show-word-limit
        :disabled="pending" aria-label="错题追问" placeholder="例如：我的选项错在哪里？能举个例子吗？" />
      <div class="actions">
        <el-button type="primary" :loading="pending" :disabled="pending || !query.trim()" @click="send">
          {{ lastTask?.status === 'SUCCESS' ? '发送追问' : '生成解释' }}
        </el-button>
        <span class="hint">{{ pending ? '正在生成，可继续浏览其他题目。' : '模型未启用时会显示原题解析。' }}</span>
      </div>
    </template>
  </section>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { submitTask } from '@/api/task'
import type { Task } from '@/types/api'
import TaskResultView from './TaskResultView.vue'

const props = defineProps<{ recordId: number; initialTask?: Task }>()
type Message = { role: 'user' | 'assistant'; content: string }
const opened = ref(false), pending = ref(false), query = ref(''), error = ref('')
const messages = ref<Message[]>([])
const lastTask = ref<Task>()
let parentTaskId: string | undefined
let generation = 0

watch(() => [props.recordId, props.initialTask] as const, () => {
  generation++
  pending.value = false
  opened.value = !!props.initialTask
  lastTask.value = props.initialTask
  error.value = ''
  query.value = '请解释这道错题，指出我的选择错在哪里，并给出复习建议。'
  const task = props.initialTask
  parentTaskId = task?.status === 'SUCCESS' ? task.id :
    typeof task?.inputPayload?.parentTaskId === 'string' ? task.inputPayload.parentTaskId : undefined
  const history = task?.inputPayload?.messages
  messages.value = Array.isArray(history) ? history.filter((m): m is Message =>
    m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string').slice(-6) : []
  if (task?.status === 'SUCCESS') query.value = ''
  else if (typeof task?.inputPayload?.query === 'string') query.value = task.inputPayload.query
}, { immediate: true })

async function send() {
  if (pending.value || !query.value.trim()) return
  const revision = generation, text = query.value.trim()
  pending.value = true
  error.value = ''
  try {
    const task = await submitTask({ taskType: 'WRONG_QUESTION_TUTOR', input: {
      recordId: props.recordId, query: text, ...(parentTaskId ? { parentTaskId } : {})
    } })
    if (revision !== generation) return
    if (lastTask.value?.status === 'SUCCESS' && lastTask.value.resultPayload) {
      messages.value = [...messages.value,
        { role: 'user' as const, content: String(lastTask.value.inputPayload?.query || '') },
        { role: 'assistant' as const, content: lastTask.value.resultPayload.answer }].slice(-6)
    }
    lastTask.value = task
    if (task.status === 'SUCCESS') {
      parentTaskId = task.id
      query.value = ''
    }
  } catch {
    if (revision === generation) error.value = '暂时无法生成，请核对错误提示后重试。原作答和解析已保留。'
  } finally { if (revision === generation) pending.value = false }
}
onBeforeUnmount(() => { generation++ })
</script>
<style scoped>
.tutor { margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--c-line); overflow-wrap: anywhere; }
h4 { margin: 0 0 8px; }
.hint { color: var(--c-ink-2); font-size: 13px; line-height: 1.7; }
.message { white-space: pre-wrap; line-height: 1.8; margin: 12px 0; }
.actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
</style>
