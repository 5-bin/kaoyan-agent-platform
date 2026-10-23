<template>
  <div class="page notes-page">
    <div class="page-head"><h2 class="page-title">个人笔记</h2><p class="page-sub">整理复习内容，手动编辑或让助手生成修改建议，确认后保存为新版本。</p></div>
    <div class="note-grid">
      <aside class="card note-list" aria-label="笔记列表">
        <el-button type="primary" @click="newNote">新建笔记</el-button>
        <el-empty v-if="!notes.length && !loading" description="暂无个人笔记" :image-size="60" />
        <button v-for="note in notes" :key="note.id" class="note-item" :class="{ active: original?.id === note.id }" :title="note.title" @click="openNote(note.id)"><strong>{{ note.title }}</strong><small>版本 {{ note.version }}</small></button>
        <el-button v-if="notes.length < total" :loading="loading" @click="loadMore">更多笔记</el-button>
      </aside>
      <section v-if="editing" class="card note-content" aria-label="笔记编辑器">
        <div class="note-toolbar"><strong>{{ original ? '编辑笔记 · v' + original.version : '新建笔记' }}</strong><el-button v-if="original" @click="askAssistant">让助手修改</el-button><el-button v-if="original" @click="loadHistory(true)">历史版本</el-button><el-button type="primary" :loading="saving" :disabled="loading || !title.trim()" @click="save">{{ original ? '保存新版本' : '创建笔记' }}</el-button></div>
        <p v-if="dirty" class="muted" role="status">有尚未保存的修改。</p>
        <el-alert v-if="conflict" title="笔记已有新版本。你的编辑内容已保留，请重新读取并核对后再保存。" type="warning" :closable="false"><el-button @click="reloadNote">重新读取并核对</el-button></el-alert>
        <el-input v-model="title" maxlength="100" show-word-limit placeholder="笔记标题" aria-label="笔记标题" />
        <div class="note-editor"><el-input v-model="content" type="textarea" :rows="18" maxlength="40000" show-word-limit placeholder="使用 Markdown 记录复习内容" aria-label="笔记正文" /><div class="note-preview"><strong>预览</strong><SafeMarkdown :content="content" /></div></div>
        <details v-if="original && dirty"><summary>查看修改差异（基于 v{{ original.version }}）</summary><pre class="diff"><span v-for="(part, index) in differences" :key="index" :class="{ added: part.added, removed: part.removed }">{{ part.value }}</span></pre></details>
      </section>
      <section v-else class="card note-content"><el-empty description="选择一份笔记，或新建笔记" /></section>
    </div>
    <el-dialog v-model="historyOpen" title="笔记历史版本" width="min(760px,94vw)">
      <div v-for="version in versions" :key="version.version" class="version-row"><span>v{{ version.version }} · {{ version.title }}</span><el-button @click="previewVersion(version.version)">查看此版本</el-button></div>
      <el-button v-if="versions.length < versionTotal" @click="loadHistory(false)">更多版本</el-button>
      <el-empty v-if="!versions.length" description="暂无历史版本" />
    </el-dialog>
    <el-dialog v-model="versionOpen" title="历史版本（只读）" width="min(760px,94vw)"><h3>{{ historical?.title }} · v{{ historical?.version }}</h3><SafeMarkdown :content="historical?.content || ''" /></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { diffLines } from 'diff'
import SafeMarkdown from '@/components/SafeMarkdown.vue'
import * as api from '@/api/conversation'
import type { PersonalDocument, DocumentVersion } from '@/api/conversation'
import { useUserStore } from '@/stores/user'
import { useAssistantStore } from '@/stores/assistant'
import { useAssistantPage } from '@/composables/assistant-page'

const user = useUserStore(), assistant = useAssistantStore(), route = useRoute(), router = useRouter()
const notes = ref<PersonalDocument[]>([]), total = ref(0), page = ref(1), loading = ref(false)
const editing = ref(false), original = ref<PersonalDocument>(), title = ref(''), content = ref(''), saving = ref(false), conflict = ref(false)
const versions = ref<DocumentVersion[]>([]), versionPage = ref(1), versionTotal = ref(0), historyOpen = ref(false), versionOpen = ref(false), historical = ref<PersonalDocument>()
let epoch = 0
const guard = (stamp: number) => stamp === epoch && !!user.token
const dirty = computed(() => editing.value && (title.value !== (original.value?.title || '') || content.value !== (original.value?.content || '')))
const differences = computed(() => diffLines(original.value?.content || '', content.value))
async function canLeave() { if (!dirty.value || !user.token) return true; try { await ElMessageBox.confirm('有尚未保存的笔记内容，离开后将丢弃本次编辑。', '未保存的修改', { confirmButtonText: '离开', cancelButtonText: '继续编辑', type: 'warning' }); return true } catch { return false } }
onBeforeRouteLeave(canLeave)
onBeforeRouteUpdate(async (to, from) => to.query.noteId === from.query.noteId || await canLeave())
async function loadList() { const stamp = epoch, data = await api.listPersonalDocuments(); if (guard(stamp)) { notes.value = data.list; total.value = data.total; page.value = 1 } }
async function loadMore() { const stamp = epoch; loading.value = true; try { const data = await api.listPersonalDocuments(page.value + 1); if (guard(stamp)) { notes.value.push(...data.list); total.value = data.total; page.value++ } } finally { if (guard(stamp)) loading.value = false } }
async function openNote(id: string) { if (id !== original.value?.id) await router.push({ path: '/notes', query: { noteId: id } }) }
async function newNote() {
  if (!await canLeave()) return
  editing.value = false; original.value = undefined; title.value = ''; content.value = ''; conflict.value = false
  await router.replace('/notes'); editing.value = true
}
async function reloadNote() {
  if (!original.value || !await canLeave()) return
  const stamp = epoch, data = await api.getPersonalDocument(original.value.id)
  if (guard(stamp)) { original.value = data; title.value = data.title; content.value = data.content; conflict.value = false }
}
async function save() {
  if (saving.value || !title.value.trim()) return
  const stamp = epoch; saving.value = true
  try {
    const data = await api.savePersonalDocument({ title: title.value, content: content.value, baseVersion: original.value?.version }, original.value?.id)
    if (!guard(stamp)) return
    original.value = data; title.value = data.title; content.value = data.content; conflict.value = false
    assistant.notesChanged(); await loadList(); await router.replace({ path: '/notes', query: { noteId: data.id } }); ElMessage.success('笔记已保存')
  } catch (error) { if (guard(stamp) && axios.isAxiosError(error) && error.response?.status === 409) conflict.value = true }
  finally { if (guard(stamp)) saving.value = false }
}
async function askAssistant() {
  if (!original.value) return
  if (dirty.value) { ElMessage.warning('请先保存笔记修改，助手将读取已保存的版本'); return }
  assistant.selectNote(original.value.id)
}
async function loadHistory(first: boolean) {
  if (!original.value) return
  const stamp = epoch, next = first ? 1 : versionPage.value + 1, data = await api.documentVersions(original.value.id, next)
  if (guard(stamp)) { versions.value = first ? data.list : [...versions.value, ...data.list]; versionPage.value = next; versionTotal.value = data.total; historyOpen.value = true }
}
async function previewVersion(version: number) { if (!original.value) return; const stamp = epoch, data = await api.getDocumentVersion(original.value.id, version); if (guard(stamp)) { historical.value = data; versionOpen.value = true } }
useAssistantPage(() => ({ page: 'notes' }), loadList)
watch(() => assistant.noteRevision, async () => {
  if (!user.token) return
  const stamp = epoch, id = original.value?.id
  await loadList()
  if (!id || !guard(stamp)) return
  const data = await api.getPersonalDocument(id)
  if (!guard(stamp)) return
  if (dirty.value) { if (data.version !== original.value?.version) conflict.value = true; return }
  original.value = data; title.value = data.title; content.value = data.content
})
watch([() => user.token, () => route.query.noteId], async ([token, id]) => {
  const stamp = ++epoch; original.value = undefined; title.value = ''; content.value = ''; editing.value = false; conflict.value = false; saving.value = false
  historyOpen.value = false; versionOpen.value = false; versions.value = []; historical.value = undefined; notes.value = []; total.value = 0
  if (!token) return
  loading.value = true
  try {
    await loadList()
    if (typeof id === 'string' && id) { const data = await api.getPersonalDocument(id); if (guard(stamp)) { original.value = data; title.value = data.title; content.value = data.content; editing.value = true } }
  } finally { if (guard(stamp)) loading.value = false }
}, { immediate: true })
onBeforeUnmount(() => { epoch++ })
</script>

<style scoped>
.note-grid { display:grid; grid-template-columns:240px minmax(0,1fr); gap:20px; align-items:start }
.note-list,.note-content { padding:20px; min-width:0 }
.note-item { display:flex; flex-direction:column; text-align:left; gap:6px; width:100%; border:0; border-bottom:1px solid var(--c-line); padding:14px 8px; background:transparent; color:inherit; cursor:pointer }
.note-item strong { width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.note-item.active { background:var(--c-primary-light,#eef4ff) }
.note-toolbar,.version-row { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:16px }.note-toolbar .el-button { margin:0 }
.note-editor { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:16px; margin-top:16px }
.note-preview { max-height:65vh; overflow:auto; padding:12px; border:1px solid var(--c-line); border-radius:8px; overflow-wrap:anywhere }
.diff { white-space:pre-wrap; overflow-wrap:anywhere; padding:12px }.added { background:#ddf5e3 }.removed { background:#ffe1e1; text-decoration:line-through }.muted,small { color:var(--c-ink-2) }
@media(max-width:1000px) { .note-grid,.note-editor { grid-template-columns:minmax(0,1fr) }.note-list { max-height:260px; overflow:auto } }
</style>
