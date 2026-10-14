<template>
  <div class="page" v-loading="loading">
    <el-page-header @back="router.back()" title="返回院校库" />
    <div class="card hero">
      <div class="hero-icon">{{ detail.school?.name?.[0] }}</div>
      <div>
        <h2 class="hero-name">{{ detail.school?.name }}</h2>
        <p class="hero-meta">{{ detail.school?.province }} · {{ detail.school?.level }}</p>
      </div>
    </div>

    <h3 class="sec-title">专业录取信息</h3>
    <div class="card">
      <el-table :data="detail.details || []" stripe>
        <el-table-column prop="majorName" label="专业" />
        <el-table-column prop="majorCode" label="专业代码" width="120" />
        <el-table-column prop="year" label="年份" width="100" />
        <el-table-column prop="enrollmentCount" label="招生人数" width="100" />
        <el-table-column prop="scoreLine" label="复试线" width="100" />
        <el-table-column prop="remark" label="备注" />
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSchoolDetail } from '@/api/school'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const detail = ref<any>({ school: {}, details: [] })

onMounted(async () => {
  loading.value = true
  try { detail.value = await getSchoolDetail(Number(route.params.id)) }
  finally { loading.value = false }
})
</script>

<style scoped>
.hero { display: flex; align-items: center; gap: 16px; padding: 24px; margin: 16px 0; }
.hero-icon {
  width: 56px; height: 56px; border-radius: 12px;
  background: var(--c-primary-light); color: var(--c-primary);
  display: grid; place-items: center; font-weight: 700; font-size: 22px;
}
.hero-name { margin: 0; font-size: 20px; }
.hero-meta { margin: 4px 0 0; color: var(--c-ink-2); }
.sec-title { font-size: 15px; font-weight: 600; margin: 0 0 12px; }
</style>
