<template>
  <div class="page" v-loading="loading">
    <el-page-header @back="router.back()" title="返回院校库" />
    <el-alert title="请核对每条专业记录的年份和来源；未收录的人数或分数线不代表零。历史演示或估计数据不能作为报考依据。" type="warning" :closable="false" />
    <div class="card hero">
      <div class="hero-icon">{{ detail.school?.name?.[0] }}</div>
      <div>
        <h2 class="hero-name">{{ detail.school?.name }}</h2>
        <p class="hero-meta">{{ detail.school?.province }} · {{ detail.school?.level || '层次未登记' }}</p>
      </div>
    </div>

    <h3 class="sec-title">招生专业信息</h3>
    <div class="card">
      <el-table :data="detail.details || []" stripe>
        <el-table-column prop="majorName" label="专业" min-width="180" />
        <el-table-column prop="majorCode" label="专业代码" width="120" />
        <el-table-column prop="year" label="年份" width="100" />
        <el-table-column label="招生人数" width="100"><template #default="scope">{{ scope.row.enrollmentCount ?? '未收录' }}</template></el-table-column>
        <el-table-column label="复试线" width="100"><template #default="scope">{{ scope.row.scoreLine ?? '未收录' }}</template></el-table-column>
        <el-table-column prop="remark" label="备注" min-width="420" />
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
:deep(.el-table__cell) { vertical-align: top; }
:deep(.el-table .cell) { overflow-wrap: anywhere; }
.sec-title { font-size: 15px; font-weight: 600; margin: 0 0 12px; }
</style>
