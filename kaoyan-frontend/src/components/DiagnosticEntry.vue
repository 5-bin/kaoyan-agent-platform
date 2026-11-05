<template>
  <section v-if="enabled && !hidden && compact" class="diagnosis compact" v-loading="busy">
    <el-icon class="compact-icon" :size="18" aria-hidden="true"><Aim /></el-icon>
    <p class="compact-text">
      <strong>{{ profile?.independentSamples ? '更新你的诊断' : '建立学情画像' }}</strong>
      <span>四科各5道单选，结束后统一判分。</span>
    </p>
    <div class="diag-actions">
      <el-button type="primary" size="small" :disabled="busy" @click="start">开始单选诊断</el-button>
      <el-button size="small" :disabled="busy" @click="hidden = true">暂时跳过</el-button>
    </div>
    <p v-if="error" class="diag-error" role="alert">{{ error }}</p>
  </section>
  <section v-else-if="enabled && !hidden" class="diagnosis" :class="embedded ? 'embedded' : 'card'" v-loading="busy">
    <span v-if="embedded" class="diag-icon" aria-hidden="true"><el-icon :size="24"><Aim /></el-icon></span>
    <div class="diag-body">
      <h3>{{ profile?.independentSamples ? '更新你的诊断' : '建立学情画像' }}</h3>
      <p>默认四科各5道单选题，缺题时进行局部诊断。结束后统一判分，参考分未经完整408考试校准。</p>
    </div>
    <div class="diag-actions">
      <el-button type="primary" :disabled="busy" @click="start">开始单选诊断</el-button>
      <el-button :disabled="busy" @click="hidden = true">暂时跳过</el-button>
    </div>
    <p v-if="error" class="diag-error" role="alert">{{ error }}</p>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Aim } from '@element-plus/icons-vue'
import { learningStatus, learningProfile, startDiagnostic, type LearningProfile } from '@/api/learning'
// embedded：嵌入首页顶部卡片；compact：功能页顶部的一行提示；都不传时保持原卡片样式
withDefaults(defineProps<{ embedded?: boolean; compact?: boolean }>(), { embedded: false, compact: false })
const enabled = ref(false), hidden = ref(false), busy = ref(false), error = ref(''), profile = ref<LearningProfile>()
const router = useRouter()
onMounted(async () => { try { enabled.value = (await learningStatus()).enabled; if (enabled.value) profile.value = await learningProfile() } catch { error.value = '诊断状态读取失败，请稍后重试。' } })
async function start() {
  busy.value = true; error.value = ''
  try { const value = await startDiagnostic(); await router.push(`/practice/session/${value.sessionId}`) }
  catch { error.value = '暂时无法创建诊断，请检查是否有审核通过的可用题目。' }
  finally { busy.value = false }
}
</script>
<style scoped>
.diagnosis { padding: 20px; margin-bottom: 20px; }
.diagnosis p { line-height: 1.7; }
.embedded {
  display: flex; flex-wrap: wrap; align-items: center; gap: 16px 24px;
  margin: 0; padding: 18px 20px; max-width: 860px;
  background: rgba(255, 255, 255, .78); border: 1px solid #e3e9ff; border-radius: 14px;
}
.embedded .diag-body { flex: 1 1 320px; min-width: 0; }
.embedded h3 { margin: 0; font-size: 16px; }
.embedded .diag-body p { margin: 6px 0 0; color: var(--c-ink-2); }
.embedded .diag-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.embedded .diag-actions .el-button { min-height: 44px; margin: 0; }
.embedded .diag-error { flex: 1 1 100%; margin: 0; color: var(--c-danger); }
.compact {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px;
  margin-bottom: 16px; padding: 10px 16px;
  background: var(--c-surface); border: 1px solid var(--c-line); border-radius: 10px;
}
.compact-icon { color: var(--c-primary-strong); flex-shrink: 0; }
.compact-text { flex: 1 1 260px; margin: 0; color: var(--c-ink-2); line-height: 1.6; }
.compact-text strong { color: var(--c-ink); margin-right: 8px; }
.compact .diag-actions { display: flex; gap: 8px; }
.compact .diag-actions .el-button { margin: 0; }
.compact .diag-error { flex: 1 1 100%; margin: 0; color: var(--c-danger); }
@media (max-width: 640px) { .compact-icon { display: none; } }
.diag-icon {
  width: 48px; height: 48px; border-radius: 12px; flex-shrink: 0;
  display: grid; place-items: center; color: var(--c-primary-strong);
  background: linear-gradient(145deg, #f1f5ff, #dde6ff);
  box-shadow: inset 0 0 0 1px rgba(43, 90, 230, .12);
}
</style>
