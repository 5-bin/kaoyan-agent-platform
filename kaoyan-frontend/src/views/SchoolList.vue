<template>
  <div class="page schools-page">
    <div class="hero">
      <h1 class="hero-title">院校库</h1>
      <p class="hero-sub">查找目标院校，了解层次与地区分布</p>
      <div class="search-bar">
        <el-input v-model="q.province" placeholder="省份" clearable size="large" />
        <el-select v-model="q.level" placeholder="层次" clearable size="large" style="width:140px">
          <el-option label="985" value="985" />
          <el-option label="211" value="211" />
          <el-option label="双一流" value="双一流" />
        </el-select>
        <el-input v-model="q.majorName" placeholder="专业名" clearable size="large" style="width:220px" />
        <el-button type="primary" size="large" @click="load">搜索</el-button>
        <el-button size="large" class="ai-btn" @click="dialog = true">
          <el-icon><MagicStick /></el-icon>&nbsp;AI 择校
        </el-button>
      </div>
    </div>

    <div class="result" v-loading="loading">
      <div v-for="s in list" :key="s.id" class="row" @click="router.push(`/schools/${s.id}`)">
        <div class="row-icon">{{ s.name?.[0] }}</div>
        <div class="row-main">
          <div class="row-name">{{ s.name }}</div>
          <div class="row-meta">{{ s.province }}</div>
        </div>
        <div class="row-tags">
          <el-tag v-if="s.level" effect="dark" size="small">{{ s.level }}</el-tag>
        </div>
        <el-icon class="row-arrow"><ArrowRight /></el-icon>
      </div>
      <el-empty v-if="!loading && !list.length" description="没有匹配的院校" style="margin:40px 0" />
    </div>

    <el-dialog v-model="dialog" title="AI 择校推荐" width="680px">
      <el-input
        v-model="query" type="textarea" :rows="3"
        placeholder="描述你的情况，比如：本科双非计算机，想考福建的学硕，数学一般，求推荐"
      />
      <div v-if="result" class="result-block">
        <h4>{{ result.summary }}</h4>
        <template v-for="(group, key) in ['rush','stable','safe']" :key="key">
          <div v-if="result[group]?.length" class="group">
            <div class="group-title">{{ groupLabel[key] }}</div>
            <div v-for="r in result[group]" :key="r.school" class="school">
              <b>{{ r.school }}</b> · {{ r.major }}
              <span class="muted">（分数线 {{ r.score_line || '—' }}）</span>
              <p>{{ r.reason }}</p>
              <p v-if="r.risk" class="muted">风险：{{ r.risk }}</p>
            </div>
          </div>
        </template>
        <p v-if="result.tips" class="tips">{{ result.tips }}</p>
      </div>
      <el-empty v-else-if="done" description="AI 暂无返回" :image-size="60" />
      <template #footer>
        <el-button @click="dialog = false">关闭</el-button>
        <el-button type="primary" :loading="loading" @click="ask">问 AI</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { searchSchools } from '@/api/school'
import { submitTask } from '@/api/task'
import type { School } from '@/types/api'
import { ArrowRight, MagicStick } from '@element-plus/icons-vue'

const router = useRouter()
const q = reactive({ province: '', level: '', majorName: '' })
const list = ref<School[]>([])
const loading = ref(false)
const load = async () => {
  loading.value = true
  try { list.value = await searchSchools(q) } finally { loading.value = false }
}
onMounted(load)

const dialog = ref(false)
const query = ref('')
const result = ref<any>(null)
const done = ref(false)
const groupLabel: Record<string, string> = { rush: '冲刺', stable: '稳妥', safe: '保底' }

const ask = async () => {
  if (!query.value.trim()) return
  loading.value = true
  done.value = false
  result.value = null
  try {
    const t: any = await submitTask({ taskType: 'SCHOOL_RECOMMEND', input: { query: query.value } })
    if (t.status === 'SUCCESS') result.value = t.resultPayload
    done.value = true
  } finally { loading.value = false }
}
</script>

<style scoped>
.schools-page { max-width: 900px; }
.hero {
  background: linear-gradient(135deg, #3b6cff 0%, #6d5cff 100%);
  border-radius: var(--r-lg);
  padding: 36px; color: #fff; margin-bottom: 20px;
}
.hero-title { font-size: 26px; font-weight: 700; margin: 0 0 6px; }
.hero-sub { opacity: .85; margin: 0 0 22px; font-size: 14px; }
.search-bar { display: flex; gap: 10px; flex-wrap: wrap; }
.search-bar :deep(.el-input__wrapper),
.search-bar :deep(.el-select__wrapper) {
  box-shadow: 0 0 0 1px rgba(255,255,255,.3) inset;
  background: rgba(255,255,255,.95);
}
.ai-btn { background: rgba(255,255,255,.2); color: #fff; border-color: rgba(255,255,255,.4); }
.ai-btn:hover { background: rgba(255,255,255,.3); color: #fff; }

.result { display: flex; flex-direction: column; gap: 10px; }
.row {
  background: var(--c-surface); border: 1px solid var(--c-line);
  border-radius: var(--r-md); padding: 16px 20px;
  display: flex; align-items: center; gap: 16px;
  cursor: pointer; transition: all .15s;
}
.row:hover { border-color: var(--c-primary); box-shadow: var(--shadow-md); }
.row-icon {
  width: 48px; height: 48px; border-radius: 10px; flex-shrink: 0;
  background: var(--c-primary-light); color: var(--c-primary);
  display: grid; place-items: center; font-weight: 700; font-size: 19px;
}
.row-main { flex: 1; min-width: 0; }
.row-name { font-weight: 600; font-size: 16px; }
.row-meta { color: var(--c-ink-2); font-size: 12px; margin-top: 4px; }
.row-tags { display: flex; gap: 6px; }
.row-arrow { color: var(--c-ink-3); }
.row:hover .row-arrow { color: var(--c-primary); }

.result-block { margin-top: 16px; }
.group { margin-top: 12px; }
.group-title { font-weight: 600; margin-bottom: 6px; }
.school { padding: 8px 0; border-bottom: 1px dashed var(--c-line); }
.school p { margin: 4px 0 0; color: var(--c-ink-2); font-size: 13px; }
.muted { color: var(--c-ink-3); font-size: 12px; }
.tips { margin-top: 12px; color: var(--c-ink-2); font-size: 13px; }
</style>
