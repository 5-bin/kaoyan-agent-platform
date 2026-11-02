<template>
  <section v-if="enabled && !hidden" class="card diagnosis" v-loading="busy">
    <h3>{{ profile?.independentSamples ? '更新你的诊断' : '建立学情画像' }}</h3>
    <p>默认四科各5道单选题，缺题时进行局部诊断。结束后统一判分，参考分未经完整408考试校准。</p>
    <el-button type="primary" :disabled="busy" @click="start">开始单选诊断</el-button>
    <el-button :disabled="busy" @click="hidden = true">暂时跳过</el-button>
    <p v-if="error" role="alert">{{ error }}</p>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { learningStatus, learningProfile, startDiagnostic, type LearningProfile } from '@/api/learning'
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
<style scoped>.diagnosis { padding: 20px; margin-bottom: 20px; } .diagnosis p { line-height: 1.7; }</style>
