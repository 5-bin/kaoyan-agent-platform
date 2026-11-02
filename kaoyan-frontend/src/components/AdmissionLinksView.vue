<template>
  <section class="admission-links" aria-label="招生官网链接">
    <h3>招生官网链接 · {{ links.schoolName }}</h3>
    <p>登记年份：{{ links.registeredYear }}（{{ ADMISSION_YEAR_NOTE }}）</p>
    <ul>
      <li v-for="url in links.entryUrls" :key="url">
        <a v-if="safeRegisteredUrl(links, url)" :href="safeRegisteredUrl(links, url)" target="_blank" rel="noopener noreferrer">{{ url }}</a>
        <span v-else>{{ url }}</span>
      </li>
    </ul>
    <p>{{ ADMISSION_CONFIRM_TEXT }}</p>
    <p>如进入学校主页，请从研究生招生栏目继续查阅。</p>
  </section>
</template>

<script setup lang="ts">
import type { AdmissionLinks } from '@/types/api'
import { ADMISSION_CONFIRM_TEXT, ADMISSION_YEAR_NOTE, safeRegisteredUrl } from '@/utils/admission-links'

defineProps<{ links: AdmissionLinks }>()
</script>

<style scoped>
.admission-links { margin: 1rem 0; padding: 1rem; border: 1px solid var(--el-border-color); border-radius: 8px; overflow-wrap: anywhere; }
.admission-links h3 { margin: 0 0 .5rem; }
.admission-links ul { margin: .5rem 0; padding-left: 1.2rem; }
.admission-links li { margin: .35rem 0; }
.admission-links a { color: var(--el-color-primary); }
</style>
