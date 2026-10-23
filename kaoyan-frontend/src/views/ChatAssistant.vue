<template>
  <div class="assistant" :class="{ compact }">
    <aside class="conversation-list">
      <el-button type="primary" @click="newConversation">新建会话</el-button>
      <ConversationListItem v-for="item in conversations" :key="item.id" :item="item" :active="item.id === conversationId" :busy="!!deletingConversation" @open="openConversation" @delete="removeConversation" />
      <el-button v-if="conversations.length < conversationTotal" @click="moreConversations">更多会话</el-button>
      <router-link to="/tasks/history">任务历史</router-link>
    </aside>
    <section class="chat-main">
      <header class="chat-heading">
        <el-button class="mobile-menu" @click="drawer = true">会话</el-button>
        <h2>考研助手</h2>
        <el-button @click="openPrivacy">隐私</el-button>
        <el-button v-if="compact" @click="assistant.open = false">关闭</el-button>
        <el-button @click="router.push('/notes')">个人笔记</el-button>
      </header>
      <div class="privacy-summary"><span>{{ privacy?.modelAllowed ? '模型已授权 · 外发类别：' + (privacy.scopes.map(scope => scopeLabels[scope]).join('、') || '仅提问与必要历史') : '外部模型未授权 · 使用本地规则' }}</span><small v-if="assistant.pageContext">当前页面：{{ pageLabels[assistant.pageContext.page] }} · {{ ['wrong', 'favorite', 'practice'].includes(assistant.pageContext.page) ? '所选 ' + (assistant.pageContext.selectedQuestionIds?.length || 0) + ' 题' : '' }}</small></div>
      <div v-if="assistant.pageContext && assistant.pageContext.page !== 'notes'" class="quick-prompts"><el-button size="small" @click="input = '分析当前页面的学习情况'">分析学习情况</el-button><el-button size="small" @click="input = '推荐相关复习资料'">推荐资料</el-button><el-button size="small" @click="input = '用这些题目安排练习'">安排练习</el-button></div>
      <div v-if="conditionEntries.length" class="conditions" aria-label="当前会话条件">
        <strong>当前会话条件</strong><el-tag v-for="entry in conditionEntries" :key="entry[0]">{{ entry[0] }}：{{ entry[1] }}</el-tag>
        <small>仅用于本会话，不修改个人档案</small>
      </div>
      <div ref="scrollArea" class="messages" @scroll="trackScroll">
        <el-button v-if="messages.length < messageTotal" @click="olderMessages">加载更早消息</el-button>
        <el-empty v-if="!messages.length" description="可以询问408知识、咨询择校，或创建和修改学习笔记" />
        <article v-for="message in messages" :key="message.id" class="turn">
          <div class="user-message">{{ message.content }}</div>
          <div v-for="attempt in message.attempts" :key="attempt.taskId" class="assistant-message">
            <template v-if="attempt.status === 'RUNNING'">
              <el-tag>生成中</el-tag><small>{{ attempt.stage }}</small>
              <SafeMarkdown :content="draftText(attempt)" />
              <el-button @click="stop(attempt.taskId)">停止生成</el-button>
              <small v-if="connectionNotice" role="status">{{ connectionNotice }}</small>
              <el-button v-if="connectionFailed" @click="connect(attempt)">重新连接</el-button>
            </template>
            <TaskResultView v-else :task="asTask(attempt)" />
            <div v-if="attempt.status === 'SUCCESS'" class="question-actions"><template v-for="item in attempt.result?.evidence" :key="item.ref"><el-button v-if="item.resource?.type === 'question'" size="small" @click="referenceQuestion(attempt, item.ref)">收藏 {{ item.ref }} · {{ item.title }}</el-button></template></div>
            <div v-for="action in attempt.result?.actions" :key="action.id" class="action-card">
              <strong>{{ action.title }}</strong><p>涉及 {{ action.count }} 题 · {{ actionLabels[action.status] }}</p>
              <p v-if="action.requestedCount && action.requestedCount > action.count">请求 {{ action.requestedCount }} 题，当前可用 {{ action.count }} 题。</p>
              <ul v-if="action.targets?.length"><li v-for="(target, index) in action.targets" :key="index"><router-link v-if="resourceRoute(target.resource)" :to="resourceRoute(target.resource)!">{{ target.title }}</router-link><span v-else>{{ target.title }}</span></li></ul>
              <template v-if="action.status === 'PENDING'"><el-button type="primary" :loading="busyAction === action.id" @click="handleAction(action, true)">确认操作</el-button><el-button :disabled="!!busyAction" @click="handleAction(action, false)">放弃</el-button></template>
              <router-link v-if="action.status === 'SUCCESS' && action.result?.sessionId" :to="'/practice/session/' + encodeURIComponent(action.result.sessionId)">打开练习（{{ action.result.actualCount ?? action.count }}题）</router-link>
            </div>
            <el-button v-if="attempt.result?.documentProposal" @click="previewProposal(attempt)">预览笔记建议</el-button>
            <el-button v-if="canRetry(message, attempt)" :disabled="sending" @click="retry(message)">重试此问题</el-button>
          </div>
        </article>
      </div>
      <footer class="composer">
        <div class="document-selection">
          <el-select v-model="selectedDocumentId" clearable placeholder="可选择个人笔记" aria-label="选择个人笔记">
            <el-option v-for="document in selectableDocuments" :key="document.id" :label="document.title" :value="document.id" />
          </el-select>
          <small v-if="selectedDocument">已选 v{{ selectedDocument.version }} · {{ selectedDocument.title }}</small>
          <el-button v-if="personalDocuments.length < documentTotal" size="small" @click="moreDocuments">更多笔记</el-button>
        </div>
        <div v-if="referenceTaskId" class="reference-selection">已引用所选回答中的题目<el-button size="small" @click="referenceTaskId = undefined">取消引用</el-button></div>
        <el-input v-model="input" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" :maxlength="8000" show-word-limit
          placeholder="输入问题，或要求创建笔记、修改选中的笔记" aria-label="聊天输入"
          @keydown="onKeydown" @compositionstart="composing = true" @compositionend="composing = false" />
        <div class="composer-actions"><small>Enter 发送 · Shift+Enter 换行</small><el-button type="primary" :loading="sending" :disabled="!input.trim() || !!activeGeneration || loadingDocument" @click="send">发送</el-button></div>
      </footer>
    </section>
    <el-drawer v-model="drawer" title="会话" direction="ltr" size="min(300px,90vw)">
      <el-button type="primary" @click="newConversation">新建会话</el-button>
      <ConversationListItem v-for="item in conversations" :key="item.id" :item="item" :active="item.id === conversationId" :busy="!!deletingConversation" @open="openConversation" @delete="removeConversation" />
      <el-button v-if="conversations.length < conversationTotal" @click="moreConversations">更多会话</el-button>
      <router-link to="/tasks/history">任务历史</router-link>
    </el-drawer>
    <el-dialog v-model="privacyDialog" title="考研助手隐私设置" width="min(640px,94vw)">
      <p>接收服务：{{ privacy?.provider || '尚未获取，暂不能授权' }}。启用后，本轮提问与必要历史将发送给该服务。下面的私人记录仅在相应类别获准后使用。</p>
      <el-switch v-model="privacyDraft.modelAllowed" active-text="允许调用外部模型" aria-label="允许调用外部模型" />
      <el-checkbox-group v-model="privacyDraft.scopes" class="scope-options"><el-checkbox v-for="(label, key) in scopeLabels" :key="key" :value="key">{{ label }}</el-checkbox></el-checkbox-group>
      <p>个人笔记还需在发送前逐份选择。关闭类别后，不再向模型发送含该类信息的历史；已发送至服务方的数据无法追溯收回。</p>
      <p>助手消息、上下文和操作记录保存30天。清除仅覆盖在线助手记录，原始作答、收藏和已保存个人笔记独立保留。备份和模型服务方的数据按各自保留规则处理。</p>
      <div class="clear-controls"><el-button :disabled="!conversationId || !!deletingConversation" type="danger" plain @click="clearChat(false)">清除当前会话</el-button><el-button :disabled="!!deletingConversation" type="danger" plain @click="clearChat(true)">清除全部助手记录</el-button></div>
      <template #footer><el-button @click="privacyDialog = false">关闭</el-button><el-button type="primary" :disabled="!privacy" :loading="savingPrivacy" @click="savePrivacy">保存隐私设置</el-button></template>
    </el-dialog>
    <el-dialog v-model="editor" :title="proposalTask ? '笔记建议 · 预览后保存' : '编辑个人笔记'" width="min(1000px,96vw)">
      <el-input v-model="editTitle" maxlength="100" placeholder="笔记标题" aria-label="笔记标题" />
      <div class="document-editor"><el-input v-model="editContent" type="textarea" :rows="14" maxlength="40000" aria-label="笔记正文" /><SafeMarkdown :content="editContent" /></div>
      <details v-if="baseDocument"><summary>查看修改差异（基于 v{{ baseDocument.version }}）</summary><pre class="diff"><span v-for="(part,index) in differences" :key="index" :class="{ added: part.added, removed: part.removed }">{{ part.value }}</span></pre></details>
      <template #footer><el-button @click="editor = false">关闭</el-button><el-button type="primary" :loading="saving" :disabled="!editTitle.trim()" @click="saveDocument">{{ proposalTask ? '确认保存建议' : '保存新版本' }}</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAssistantStore } from '@/stores/assistant'
import * as privacyApi from '@/api/privacy'
import type { PrivacySettings, PrivacyScope } from '@/api/privacy'
import type { AssistantAction } from '@/types/api'
import { resourceRoute } from '@/utils/assistant-resource'
import { diffLines } from 'diff'
import { useUserStore } from '@/stores/user'
import type { Task } from '@/types/api'
import * as api from '@/api/conversation'
import type { ChatMessage, Conversation, Generation, PersonalDocument } from '@/api/conversation'
import SafeMarkdown from '@/components/SafeMarkdown.vue'
import ConversationListItem from '@/components/ConversationListItem.vue'
import TaskResultView from '@/components/TaskResultView.vue'

defineProps<{ compact?: boolean }>()
const route = useRoute(), router = useRouter(), user = useUserStore(), assistant = useAssistantStore()
const privacy = ref<PrivacySettings>(), privacyDialog = ref(false), savingPrivacy = ref(false), busyAction = ref('')
const privacyDraft = ref({ modelAllowed: false, scopes: [] as PrivacyScope[] })
const scopeLabels: Record<PrivacyScope, string> = { wrong: '错题', favorite: '收藏', stats: '学习统计', profile: '个人档案', document: '个人笔记' }
const pageLabels = { wrong: '错题本', favorite: '我的收藏', stat: '学习统计', documents: '备考资料', practice: '练习', notes: '个人笔记' }
const actionLabels = { PENDING: '待确认', SUCCESS: '执行成功', DISMISSED: '已放弃', FAILED: '执行失败' }
async function refreshPrivacy(stamp = epoch) { const result = await privacyApi.getPrivacySettings(); if (guard(stamp)) privacy.value = result }
async function openPrivacy() { await refreshPrivacy(); if (!user.token || !privacy.value) return; privacyDraft.value = { modelAllowed: privacy.value.modelAllowed, scopes: [...privacy.value.scopes] }; privacyDialog.value = true }
async function savePrivacy() {
  if (!privacy.value || savingPrivacy.value) return
  const stamp = epoch; savingPrivacy.value = true
  try { const result = await privacyApi.savePrivacySettings({ ...privacyDraft.value, provider: privacy.value.provider }); if (!guard(stamp)) return; privacy.value = result; privacyDialog.value = false; stream?.abort(); await loadMessages(stamp); ElMessage.success('隐私设置已保存') } finally { if (guard(stamp)) savingPrivacy.value = false }
}
async function clearChat(all: boolean) {
  if (deletingConversation.value) return
  if (!all) { await removeConversation(conversationId.value); return }
  const stamp = epoch, id = conversationId.value
  try { await ElMessageBox.confirm(all ? '清除全部在线助手聊天及上下文？原始学习记录和个人笔记独立保留。' : '清除当前在线会话及上下文？原始学习记录和个人笔记独立保留。', '确认清除', { type: 'warning' }) } catch { return }
  if (!guard(stamp)) return
  if (all) await api.clearConversations(); else await api.deleteConversation(id)
  if (!guard(stamp)) return
  stream?.abort(); messages.value = []; current.value = undefined; input.value = ''; editContent.value = ''; editTitle.value = ''; baseDocument.value = undefined; selectedDocument.value = undefined; selectedDocumentId.value = undefined; pending = undefined; retryPending = undefined; assistant.conversationId = ''; privacyDialog.value = false; await refreshConversations();
  if (route.path === '/tasks') await router.replace('/tasks')
}
async function handleAction(action: AssistantAction, confirm: boolean) {
  if (busyAction.value) return
  const stamp = epoch; busyAction.value = action.id
  try { const result = confirm ? await api.confirmAction(conversationId.value, action.id) : await api.dismissAction(conversationId.value, action.id); if (!guard(stamp)) return; Object.assign(action, result); if (result.status === 'SUCCESS') refreshSuccessfulActions() } finally { if (guard(stamp)) busyAction.value = '' }
}
const deletingConversation = ref('')
const deletedConversations = new Set<string>()
let listRevision = 0, listRequest = 0, sessionRevision = 0, unmounted = false
const conversations = ref<Conversation[]>([]), current = ref<Conversation>(), messages = ref<ChatMessage[]>([])
const conversationPage = ref(1), conversationTotal = ref(0), messagePage = ref(1), messageTotal = ref(0)
const documentPage = ref(1), documentTotal = ref(0), personalDocuments = ref<PersonalDocument[]>([])
const input = ref(''), sending = ref(false), composing = ref(false), drawer = ref(false)
const referenceTaskId = ref<string>()
const connectionNotice = ref(''), connectionFailed = ref(false), scrollArea = ref<HTMLElement>(), atBottom = ref(true)
const selectedDocumentId = computed<string | undefined>({ get: () => assistant.selectedNoteId || undefined, set: id => { assistant.selectedNoteId = id || '' } }), selectedDocument = ref<PersonalDocument>(), loadingDocument = ref(false)
const selectableDocuments = computed(() => selectedDocument.value && !personalDocuments.value.some(note => note.id === selectedDocument.value?.id) ? [selectedDocument.value, ...personalDocuments.value] : personalDocuments.value)
const editor = ref(false), editTitle = ref(''), editContent = ref(''), editingId = ref<string>(), baseDocument = ref<PersonalDocument>()
const proposalTask = ref<string>(), proposalConversation = ref<string>(), saving = ref(false)
const observedActions = new Set<string>()
function refreshSuccessfulActions() { let changed = false; for (const action of messages.value.flatMap(message => message.attempts).flatMap(attempt => attempt.result?.actions || [])) { if (action.status === 'SUCCESS' && !observedActions.has(action.id)) { observedActions.add(action.id); changed = true } } if (changed) assistant.changed() }
let epoch = 0, stream: AbortController | undefined, selectionEpoch = 0
let pending: Parameters<typeof api.sendMessage>[1] | undefined
let retryPending: { messageId: string; requestId: string } | undefined
let creatingForSend = false
let messageLoad = 0
const conversationId = computed(() => assistant.conversationId)
const activeGeneration = computed(() => messages.value.flatMap(message => message.attempts).find(attempt => attempt.status === 'RUNNING'))
const conditionLabels: Record<string,string> = { examYear: '年份', majorCodes: '专业', degreeType: '学位', regions: '地区', regionConstraint: '地区要求', studyMode: '学习方式', examSubjects: '考试科目' }
const conditionValues: Record<string,string> = { academic: '学硕', professional: '专硕', required: '必须满足', preferred: '优先考虑', full_time: '全日制', part_time: '非全日制' }
const conditionEntries = computed(() => Object.entries(current.value?.conditions || {}).filter(([key,value]) => key in conditionLabels && value != null && value !== '' && (!Array.isArray(value) || value.length)).map(([key,value]) => [conditionLabels[key]!, conditionValues[String(value)] || (Array.isArray(value) ? value.join('、') : String(value))]))
const differences = computed(() => diffLines(baseDocument.value?.content || '', editContent.value))
const guard = (stamp: number) => stamp === epoch && !!user.token
function trackScroll() { const node = scrollArea.value; if (node) atBottom.value = node.scrollHeight - node.scrollTop - node.clientHeight < 90 }
async function scrollIfNeeded() { if (!atBottom.value) return; await nextTick(); if (scrollArea.value) scrollArea.value.scrollTop = scrollArea.value.scrollHeight }
function draftText(attempt: Generation) { return Object.values(attempt.draft || {}).join('\n\n') }
function asTask(attempt: Generation): Task { return { id: attempt.taskId, userId: 0, taskType: 'CHAT', status: attempt.status, resultPayload: attempt.result, errorMessage: attempt.errorMessage, createdAt: '' } }
function canRetry(message: ChatMessage, attempt: Generation) { return !activeGeneration.value && message.id === messages.value.at(-1)?.id && attempt.taskId === message.attempts.at(-1)?.taskId && ['FAILED','CANCELLED'].includes(attempt.status) }
function referenceQuestion(attempt: Generation, ref: string) { referenceTaskId.value = attempt.taskId; input.value = '收藏 ' + ref }
async function refreshConversations(stamp = epoch) {
  const revision = listRevision, serial = ++listRequest
  const data = await api.listConversations()
  if (guard(stamp) && revision === listRevision && serial === listRequest) {
    conversations.value = (Array.isArray(data?.list) ? data.list : []).filter(item => !deletedConversations.has(item.id))
    conversationTotal.value = Number(data?.total) || 0; conversationPage.value = 1
  }
}
async function refreshDocuments(stamp = epoch) { const data = await api.listPersonalDocuments(); if (guard(stamp)) { personalDocuments.value = Array.isArray(data?.list) ? data.list : []; documentTotal.value = Number(data?.total) || 0; documentPage.value = 1 } }
async function moreConversations() {
  const stamp = epoch, revision = listRevision, serial = ++listRequest, page = conversationPage.value + 1
  const data = await api.listConversations(page)
  if (guard(stamp) && revision === listRevision && serial === listRequest) {
    conversations.value.push(...data.list.filter(item => !deletedConversations.has(item.id) && !conversations.value.some(existing => existing.id === item.id)))
    conversationPage.value = page; conversationTotal.value = data.total
  }
}
async function moreDocuments() { const stamp = epoch, data = await api.listPersonalDocuments(documentPage.value + 1); if (guard(stamp)) { personalDocuments.value.push(...data.list); documentPage.value++; documentTotal.value = data.total } }
async function openConversation(id: string) {
  if (deletedConversations.has(id)) return
  drawer.value = false; assistant.conversationId = id
  if (route.path === '/tasks') { const query = { ...route.query }; if (id) query.conversationId = id; else delete query.conversationId; await router.replace({ path: '/tasks', query }) }
}
async function removeConversation(id: string) {
  if (!id || deletingConversation.value) return
  const token = user.token, session = sessionRevision
  const valid = () => !unmounted && !!token && token === user.token && session === sessionRevision
  deletingConversation.value = id
  try {
    try { await ElMessageBox.confirm('删除此对话？聊天记录将被清除，无法恢复；已保存的个人笔记不受影响。', '删除对话', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }) } catch { return }
    if (!valid()) return
    await api.deleteConversation(id)
    if (!valid()) return
    deletedConversations.add(id); listRevision++; listRequest++
    conversations.value = conversations.value.filter(item => item.id !== id)
    conversationTotal.value = Math.max(0, conversationTotal.value - 1)
    if (conversationId.value === id) {
      ++epoch; ++messageLoad; stream?.abort()
      messages.value = []; current.value = undefined; input.value = ''; referenceTaskId.value = undefined
      pending = undefined; retryPending = undefined; sending.value = false
      connectionNotice.value = ''; connectionFailed.value = false
      editor.value = false; editContent.value = ''; editTitle.value = ''; baseDocument.value = undefined
      proposalTask.value = undefined; proposalConversation.value = undefined; privacyDialog.value = false
      await openConversation(conversations.value[0]?.id || '')
    } else if (proposalConversation.value === id) {
      editor.value = false; proposalTask.value = undefined; proposalConversation.value = undefined
    }
    ElMessage.success('对话已删除')
    // Refresh from page one after removing a row: offset pagination otherwise skips a row.
    try { await refreshConversations() } catch { /* Keep the successful local removal; the request layer reports refresh errors. */ }
    if (valid() && !conversationId.value && conversations.value[0]) await openConversation(conversations.value[0].id)
  } catch { /* The shared request layer reports deletion errors; keep the original conversation. */ }
  finally { if (valid()) deletingConversation.value = '' }
}
async function newConversation() { const stamp = epoch; const created = await api.createConversation(); if (guard(stamp)) await openConversation(created.id) }
async function loadMessages(stamp = epoch) {
  const serial = ++messageLoad
  const id = conversationId.value
  if (!id) return
  const data = await api.listMessages(id)
  if (!guard(stamp) || id !== conversationId.value || serial !== messageLoad) return
  current.value = data.conversation; messages.value = data.list.reverse(); messageTotal.value = data.total; messagePage.value = 1; refreshSuccessfulActions()
  await scrollIfNeeded()
  if (activeGeneration.value) void connect(activeGeneration.value)
}
async function olderMessages() {
  const stamp = epoch, id = conversationId.value, node = scrollArea.value, height = node?.scrollHeight || 0
  const data = await api.listMessages(id, messagePage.value + 1)
  if (!guard(stamp) || id !== conversationId.value) return
  messages.value.unshift(...data.list.reverse()); messagePage.value++
  await nextTick(); if (node) node.scrollTop += node.scrollHeight - height
}
async function connect(attempt: Generation) {
  stream?.abort(); const controller = new AbortController(); stream = controller
  const stamp = epoch, id = conversationId.value
  connectionFailed.value = false
  for (let count = 0; count < 6 && guard(stamp) && !controller.signal.aborted; count++) {
    try {
      connectionNotice.value = count ? '正在重新连接…' : '正在连接…'
      await api.subscribeGeneration(id, attempt.taskId, controller.signal, (event, value) => {
        if (!guard(stamp) || controller.signal.aborted || value.taskId !== attempt.taskId) return
        const version = Number(value.version)
        if (event === 'snapshot') {
          if (version < attempt.version) return
          Object.assign(attempt, value); connectionNotice.value = ''
        } else if (version <= attempt.version) return
        else if (['completed','failed','cancelled'].includes(event)) {
          Object.assign(attempt, value); attempt.draft = {}
          if (attempt.result?.conditions && current.value) current.value.conditions = attempt.result.conditions
          connectionNotice.value = ''; controller.abort(); refreshSuccessfulActions(); void refreshConversations(stamp)
        } else {
          if (version !== attempt.version + 1) throw new Error('消息版本不连续，重新获取快照')
          attempt.version = version
          if (event === 'delta') {
            const slot = String(value.slot), previous = attempt.draft?.[slot] || ''
            if (Array.from(previous).length !== Number(value.offset)) throw new Error('消息位置不连续')
            attempt.draft = { ...attempt.draft, [slot]: previous + String(value.text) }
          } else if (event === 'stage') attempt.stage = String(value.stage)
        }
        if (attempt.status === 'SUCCESS') refreshSuccessfulActions()
        void scrollIfNeeded()
      })
      if (attempt.status !== 'RUNNING') return
    } catch { if (controller.signal.aborted || !guard(stamp)) return }
    if (attempt.status !== 'RUNNING') return
    await new Promise<void>(resolve => { const timeout = setTimeout(resolve, Math.min(500 * 2 ** count, 4000)); controller.signal.addEventListener('abort', () => { clearTimeout(timeout); resolve() }, { once: true }) })
  }
  if (guard(stamp) && !controller.signal.aborted && attempt.status === 'RUNNING') { connectionNotice.value = '连接中断，生成可能仍在继续'; connectionFailed.value = true }
}
function onKeydown(event: KeyboardEvent) { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && !composing.value && event.keyCode !== 229) { event.preventDefault(); void send() } }
async function send() {
  if (sending.value || creatingForSend || activeGeneration.value || !input.value.trim() || loadingDocument.value) return
  const data = { query: input.value.trim(), documentId: selectedDocument.value?.id, documentVersion: selectedDocument.value?.version, referenceTaskId: referenceTaskId.value, pageContext: assistant.pageContext ? JSON.parse(JSON.stringify(assistant.pageContext)) as api.AssistantPageContext : undefined }
  if (!conversationId.value) {
    creatingForSend = true
    const token = user.token
    try { const created = await api.createConversation(); if (token !== user.token) return; await openConversation(created.id); await nextTick() }
    finally { creatingForSend = false }
  }
  const stamp = epoch, id = conversationId.value
  if (!pending || pending.query !== data.query || pending.documentId !== data.documentId || pending.documentVersion !== data.documentVersion || pending.referenceTaskId !== data.referenceTaskId || JSON.stringify(pending.pageContext) !== JSON.stringify(data.pageContext)) pending = { ...data, clientRequestId: crypto.randomUUID() }
  sending.value = true; atBottom.value = true
  try { await api.sendMessage(id, pending); if (guard(stamp)) { input.value = ''; referenceTaskId.value = undefined; pending = undefined; await loadMessages(stamp) } }
  catch { if (guard(stamp)) ElMessage.warning('发送未确认；可再次发送相同内容，或刷新查看记录') }
  finally { if (guard(stamp)) sending.value = false }
}
async function retry(message: ChatMessage) {
  if (sending.value || activeGeneration.value) return
  const stamp = epoch
  if (retryPending?.messageId !== message.id) retryPending = { messageId: message.id, requestId: crypto.randomUUID() }
  sending.value = true
  try { await api.retryMessage(conversationId.value, message.id, retryPending.requestId); if (guard(stamp)) { retryPending = undefined; await loadMessages(stamp) } }
  finally { if (guard(stamp)) sending.value = false }
}
async function stop(taskId: string) { const stamp = epoch; await api.cancelGeneration(conversationId.value, taskId); if (guard(stamp)) { stream?.abort(); await loadMessages(stamp) } }
async function selectDocument() {
  const stamp = epoch, selection = ++selectionEpoch, id = selectedDocumentId.value
  selectedDocument.value = undefined; loadingDocument.value = !!id; if (!id) return
  try { const document = await api.getPersonalDocument(id); if (guard(stamp) && selection === selectionEpoch) selectedDocument.value = document }
  finally { if (guard(stamp) && selection === selectionEpoch) loadingDocument.value = false }
}
async function previewProposal(attempt: Generation) {
  const proposal = attempt.result?.documentProposal; if (!proposal) return
  const stamp = epoch
  let original: PersonalDocument | undefined
  if (proposal.documentId) {
    original = await api.getDocumentVersion(proposal.documentId, proposal.baseVersion!)
  }
  if (!guard(stamp)) return
  baseDocument.value = original; editingId.value = proposal.documentId; proposalTask.value = attempt.taskId; proposalConversation.value = conversationId.value
  editTitle.value = proposal.title; editContent.value = proposal.content; editor.value = true
}
async function saveDocument() {
  if (saving.value) return
  const stamp = epoch; saving.value = true
  try {
    const document = proposalTask.value ? await api.applyDocument(proposalConversation.value!, proposalTask.value, { title: editTitle.value, content: editContent.value })
      : await api.savePersonalDocument({ title: editTitle.value, content: editContent.value, baseVersion: baseDocument.value?.version }, editingId.value)
    if (!guard(stamp)) return
    ElMessage.success('已保存'); editor.value = false; selectedDocumentId.value = document.id; selectedDocument.value = document; assistant.notesChanged(); await refreshDocuments(stamp)
  } finally { if (guard(stamp)) saving.value = false }
}
watch(() => route.path, async path => { drawer.value = false; editor.value = false; privacyDialog.value = false; if (path === '/tasks' && conversationId.value && !route.query.conversationId) await router.replace({ path, query: { conversationId: conversationId.value } }) })
watch(() => route.query.conversationId, value => { if (route.path === '/tasks' && typeof value === 'string' && !deletedConversations.has(value)) assistant.conversationId = value }, { immediate: true })
watch([() => assistant.conversationId, () => user.token], async (values, previous) => {
  const stamp = ++epoch; listRequest++; stream?.abort(); messages.value = []; current.value = undefined; messageTotal.value = 0
  selectedDocument.value = undefined; loadingDocument.value = false; selectionEpoch++; referenceTaskId.value = undefined
  personalDocuments.value = []; conversations.value = []; sending.value = false; saving.value = false
  editor.value = false; busyAction.value = ''; privacyDialog.value = false; pending = undefined; retryPending = undefined; atBottom.value = true
  if (previous.length && values[1] !== previous[1]) { sessionRevision++; deletingConversation.value = ''; deletedConversations.clear(); listRevision++; selectedDocumentId.value = undefined; observedActions.clear(); privacy.value = undefined; privacyDraft.value = { modelAllowed: false, scopes: [] }; input.value = ''; editContent.value = ''; editTitle.value = ''; baseDocument.value = undefined; }
  if (!user.token) { input.value = ''; return }
  try {
    await Promise.all([refreshConversations(stamp), refreshDocuments(stamp), refreshPrivacy(stamp).catch(() => { if (guard(stamp)) privacy.value = undefined })])
    if (!guard(stamp)) return
    if (selectedDocumentId.value) await selectDocument()
    if (!conversationId.value && conversations.value[0]) await openConversation(conversations.value[0].id)
    else await loadMessages(stamp)
  } catch { /* Unified request layer shows authentication and network errors. */ }
}, { immediate: true })
watch([() => assistant.selectedNoteId, () => assistant.noteRevision], async () => { if (!user.token) return; await selectDocument(); await refreshDocuments() }, { immediate: true })
onBeforeUnmount(() => { unmounted = true; epoch++; stream?.abort() })
</script>

<style scoped>
.privacy-summary { display:flex; flex-direction:column; gap:4px; padding:8px 12px; font-size:12px; color:var(--c-ink-2); border-bottom:1px solid var(--c-line) }
.quick-prompts { display:flex; flex-wrap:wrap; gap:6px; padding:8px }.quick-prompts .el-button { margin:0 }
.scope-options { display:flex; flex-wrap:wrap; margin:14px 0 }.clear-controls { display:flex; flex-wrap:wrap; gap:8px }
.action-card { padding:12px; margin:10px 0; border:1px solid var(--c-line); border-radius:8px }
.assistant.compact { position:fixed; top:56px; bottom:0; right:0; width:440px; max-width:100vw; height:auto; z-index:100; box-shadow:-4px 0 20px #0002 }
.compact .conversation-list { display:none }.compact .mobile-menu { display:inline-flex }.compact .chat-heading { flex-wrap:wrap; gap:8px; padding:10px }.compact .messages { padding:10px }.compact .composer { padding:10px }.compact .chat-heading h2 { font-size:16px }
@media(max-width:640px) { .assistant.compact { top:0; width:100vw; height:100dvh } }
.assistant { display:flex; height:calc(100vh - 56px); min-height:400px; background:var(--c-surface) }
.conversation-list { width:210px; flex-shrink:0; padding:18px 12px; border-right:1px solid var(--c-line); overflow:auto; display:flex; flex-direction:column; gap:12px }
.chat-main { min-width:0; flex:1; display:flex; flex-direction:column }
.chat-heading { display:flex; align-items:center; gap:12px; padding:12px 20px; border-bottom:1px solid var(--c-line) }
.chat-heading h2 { flex:1; margin:0; font-size:18px; white-space:nowrap }
.chat-heading .el-button { margin:0 }
.conditions { padding:10px 20px; display:flex; gap:6px; flex-wrap:wrap; font-size:12px; border-bottom:1px solid var(--c-line) }
.conditions small { width:100%; color:var(--c-ink-2) }
.messages { overflow:auto; flex:1; padding:16px 24px; overflow-wrap:anywhere }
.turn { max-width:850px; margin:0 auto 24px }
.user-message { margin:0 0 12px auto; padding:12px 16px; width:fit-content; max-width:95%; background:var(--c-primary-light); border-radius:12px; white-space:pre-wrap }
.assistant-message { margin-bottom:16px; padding:14px; border:1px solid var(--c-line); border-radius:12px }
.assistant-message > small { margin-right:8px; color:var(--c-ink-2) }
.composer { padding:12px 20px; border-top:1px solid var(--c-line) }
.composer-actions { display:flex; justify-content:space-between; align-items:center; margin-top:8px; gap:8px }
.composer-actions small { font-size:11px; color:var(--c-ink-2) }
.document-selection { display:flex; align-items:center; gap:8px; margin-bottom:8px; flex-wrap:wrap }
.document-selection .el-select { width:220px; max-width:100% }
.document-row { display:flex; justify-content:space-between; align-items:center; gap:8px; padding:12px 0; border-bottom:1px solid var(--c-line) }
.document-editor { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:12px; max-height:55vh; overflow:auto }
.diff { white-space:pre-wrap; overflow-wrap:anywhere }.added { background:#ddf5df }.removed { background:#ffe0e0; text-decoration:line-through }
.mobile-menu { display:none }
@media(max-width:900px) { .conversation-list { display:none }.mobile-menu { display:inline-flex }.messages { padding:12px 10px }.composer,.chat-heading { padding:10px }.document-editor { grid-template-columns:1fr }.conditions { padding:8px }.assistant-message { padding:10px } }
</style>
