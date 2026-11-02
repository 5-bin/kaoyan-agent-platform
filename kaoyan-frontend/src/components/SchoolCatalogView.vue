<template>
  <section v-if="catalog.school" class="school-catalog" aria-label="库内院校信息">
    <h3>{{ catalog.school.name }} · 库内信息</h3>
    <p>{{ catalog.school.province || '地区未登记' }} · {{ catalog.school.level || '层次未登记' }}</p>
    <p>查询年份：{{ catalog.targetYear ?? '未指定' }}；已有年份：{{ catalog.availableYears.join('、') || '暂无' }}</p>
    <p>符合条件 {{ catalog.total }} 条，当前展示 {{ catalog.details.length }} 条。采集待核实资料不代表已完成官方核验。</p>
    <p v-if="!catalog.details.length">库内暂无符合本次条件的专业记录，未使用其他年份替代。</p>
    <p v-for="(warning, index) in catalog.warnings" :key="index" class="warning">{{ warning.message }}</p>
    <article v-for="row in catalog.details" :key="row.id" class="program">
      <h4>{{ row.year }}年 · {{ row.majorName }}（{{ row.majorCode || '代码未登记' }}）</h4>
      <p v-if="row.admissionMetrics">{{ row.admissionMetrics.college || '学院未登记' }} · {{ row.admissionMetrics.track || '方向未登记' }}</p>
      <SchoolMetric :metric="row.admissionMetrics?.enrollment" kind="enrollment" :legacy-value="row.enrollmentCount" :legacy-year="row.year" />
      <SchoolMetric :metric="row.admissionMetrics?.cutoffReference" kind="cutoff" :legacy-value="row.scoreLine" :legacy-year="row.year" />
      <p v-if="row.remark" class="remark">原登记备注：{{ row.remark }}</p>
    </article>
    <router-link :to="`/schools/${catalog.school.id}`">查看完整院校详情</router-link>
  </section>
</template>

<script setup lang="ts">
import type { SchoolCatalog } from '@/types/api'
import SchoolMetric from './SchoolMetric.vue'

defineProps<{ catalog: SchoolCatalog }>()
</script>

<style scoped>
.school-catalog { margin: 1rem 0; overflow-wrap: anywhere; }
.program { border: 1px solid var(--el-border-color); border-radius: 8px; padding: 16px; margin: 12px 0; }
.program h4 { margin: 0 0 12px; }
.program :deep(.school-metric) { margin: 10px 0; }
.warning { color: var(--el-color-warning-dark-2); }
.remark { white-space: pre-wrap; }
</style>
