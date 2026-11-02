<template>
  <el-button :disabled="disabled" @click="open">{{ label || '导出文件' }}</el-button>
  <el-dialog v-model="visible" title="导出预览" width="min(920px,96vw)" append-to-body @closed="reset">
    <el-alert v-if="savedWarning" type="warning" :closable="false" :title="savedWarning">
      <el-button size="small" @click="visible = false; emit('save')">先保存修改</el-button>
    </el-alert>
    <p v-if="loading" role="status">正在读取导出内容…</p>
    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <el-button v-if="error" :loading="loading" @click="open">重新生成预览</el-button>
    <template v-if="preview">
      <p class="export-meta">{{ preview.sourceVersion }} · 预览有效至 {{ preview.expiresAt }}</p>
      <div class="export-content" aria-label="文件内容预览">
        <SafeMarkdown :content="preview.markdown" />
        <figure v-for="chart in preview.charts" :key="chart.title">
          <figcaption>{{ chart.title }}</figcaption>
          <img v-if="/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(chart.png)" :src="chart.png" :alt="chart.title" />
        </figure>
      </div>
    </template>
    <template #footer>
      <div class="export-footer">
        <span>下载不会调用模型或保存笔记。</span>
        <el-select v-model="format" aria-label="文件格式" style="width:160px">
          <el-option label="Word（.docx）" value="docx" /><el-option label="PDF（.pdf）" value="pdf" /><el-option label="Markdown（.md）" value="md" />
        </el-select>
        <el-button @click="visible = false">关闭</el-button>
        <el-button type="primary" :disabled="!preview || loading || !!error" :loading="downloading" @click="download">下载文件</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { downloadExport, previewExport, type ExportFormat, type ExportPreview, type ExportSource } from '@/api/export'
import SafeMarkdown from './SafeMarkdown.vue'

const props = defineProps<{ source: ExportSource; disabled?: boolean; label?: string; savedWarning?: string }>()
const emit = defineEmits<{ save: [] }>()
const user = useUserStore()
const visible = ref(false), loading = ref(false), downloading = ref(false), error = ref('')
const preview = ref<ExportPreview>(), format = ref<ExportFormat>('pdf')
let epoch = 0, controller: AbortController | undefined, objectUrl: string | undefined
function releaseUrl() { if (objectUrl) URL.revokeObjectURL(objectUrl); objectUrl = undefined }
function reset() {
  epoch++; controller?.abort(); controller = undefined; releaseUrl()
  preview.value = undefined; loading.value = false; downloading.value = false; error.value = ''
}
async function open() {
  reset(); visible.value = true; loading.value = true
  const stamp = epoch, token = user.token
  controller = new AbortController()
  try {
    const data = await previewExport(props.source, controller.signal)
    if (stamp === epoch && visible.value && token === user.token) preview.value = data
  } catch (cause) {
    if (stamp === epoch && !axios.isCancel(cause)) error.value = '预览失败，请重试。来源可能已清除或暂不可用。'
  } finally { if (stamp === epoch) loading.value = false }
}
async function download() {
  if (!preview.value || downloading.value) return
  const report = preview.value, selected = format.value, stamp = epoch, token = user.token
  downloading.value = true
  controller = new AbortController()
  try {
    const blob = await downloadExport(report.id, selected, controller.signal)
    if (stamp !== epoch || !visible.value || token !== user.token) return
    const expected = { pdf: 'application/pdf', docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', md: 'text/markdown' }
    if (!blob.size || !blob.type.startsWith(expected[selected])) throw new Error('文件响应格式不正确')
    releaseUrl(); objectUrl = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = objectUrl; anchor.download = `${report.title.replace(/[\u0000-\u001f\\/:*?"<>|]/g, '_').slice(0, 60)}.${selected}`
    document.body.append(anchor); anchor.click(); anchor.remove()
    const downloadedUrl = objectUrl
    window.setTimeout(() => { URL.revokeObjectURL(downloadedUrl); if (objectUrl === downloadedUrl) objectUrl = undefined }, 1000)
    ElMessage.success('文件已开始下载')
  } catch (cause) {
    if (stamp !== epoch || axios.isCancel(cause)) return
    const status = axios.isAxiosError(cause) ? cause.response?.status : undefined
    if (status === 404) { preview.value = undefined; error.value = '预览已过期或来源已清除，请重新生成预览。' }
    else ElMessage.error('下载失败，请重试或选择其他格式。')
  } finally { if (stamp === epoch) downloading.value = false }
}
watch(visible, value => { if (!value) reset() })
watch(() => user.token, () => { visible.value = false; reset() })
watch(() => JSON.stringify(props.source), () => { visible.value = false; reset() })
onBeforeUnmount(reset)
</script>

<style scoped>
.export-meta,.export-footer > span { color:var(--c-ink-2); font-size:13px }
.export-content { max-height:60vh; overflow:auto; padding:12px; border:1px solid var(--c-line); border-radius:8px }
.export-content figure { margin:20px 0 }.export-content img { display:block; width:100%; height:auto }
.export-footer { display:flex; flex-wrap:wrap; justify-content:flex-end; align-items:center; gap:10px }
.export-footer .el-button { margin:0 }.export-footer > span { margin-right:auto }
</style>
