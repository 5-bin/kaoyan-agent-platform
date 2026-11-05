<template>
  <div class="page home">
    <section class="hero">
      <svg class="hero-art" viewBox="0 0 420 420" aria-hidden="true">
        <g fill="none" stroke="#2b5ae6" stroke-opacity=".22">
          <circle cx="210" cy="210" r="60" />
          <circle cx="210" cy="210" r="100" />
          <circle cx="210" cy="210" r="140" stroke-dasharray="4 8" />
          <circle cx="210" cy="210" r="180" />
        </g>
        <g fill="#2b5ae6">
          <circle cx="310" cy="210" r="5" fill-opacity=".55" />
          <circle cx="140" cy="111" r="4" fill-opacity=".4" />
          <circle cx="250" cy="383" r="3.5" fill-opacity=".35" />
          <circle cx="70" cy="250" r="3" fill-opacity=".3" />
        </g>
        <circle cx="210" cy="210" r="22" fill="#6d5cff" fill-opacity=".14" />
      </svg>
      <div class="hero-head">
        <h2 class="page-title hero-title">{{ greeting }}，{{ userStore.userInfo?.username }}</h2>
        <p class="page-sub">今天也要加油上岸</p>
      </div>
      <DiagnosticEntry embedded />
    </section>

    <section class="panel" aria-labelledby="today-title">
      <h3 id="today-title" class="sec-title">今日</h3>
      <div class="stats">
        <div v-for="s in stats" :key="s.label" class="stat">
          <el-icon class="stat-deco" :class="s.tone" :size="120" aria-hidden="true"><component :is="s.icon" /></el-icon>
          <span class="stat-icon" :class="s.tone" aria-hidden="true"><el-icon :size="20"><component :is="s.icon" /></el-icon></span>
          <div>
            <div class="num" :class="{ muted: s.value === '未记录' }">
              {{ s.value }}<span v-if="s.unit" class="unit">{{ s.unit }}</span>
            </div>
            <div class="lbl">{{ s.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="panel" aria-labelledby="quick-title">
      <h3 id="quick-title" class="sec-title">快捷入口</h3>
      <div class="grid">
        <router-link v-for="q in quick" :key="q.path" :to="q.path" class="quick">
          <span class="q-icon" aria-hidden="true"><el-icon :size="20"><component :is="q.icon" /></el-icon></span>
          <span class="q-text">
            <span class="q-title">{{ q.title }}</span>
            <span class="q-desc">{{ q.desc }}</span>
          </span>
          <el-icon class="q-arrow" aria-hidden="true"><ArrowRight /></el-icon>
        </router-link>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import DiagnosticEntry from '@/components/DiagnosticEntry.vue'
import { computed, onMounted, reactive } from 'vue'
import { useUserStore } from '@/stores/user'
import { getTodayStat } from '@/api/stat'
import {
  ArrowRight, CircleCheck, EditPen, Folder, Notebook, School, Star, Timer, TrendCharts
} from '@element-plus/icons-vue'

const userStore = useUserStore()
const today = reactive({ questionCount: 0, correctCount: 0, studyMinutes: null as number | null })

// 按本地时间切换问候语
const hour = new Date().getHours()
const greeting = hour >= 5 && hour < 11 ? '早上好' : hour >= 11 && hour < 13 ? '中午好' : hour >= 13 && hour < 18 ? '下午好' : '晚上好'

const stats = computed(() => [
  { label: '今日做题', value: String(today.questionCount || 0), icon: EditPen, tone: 'blue' },
  { label: '今日答对', value: String(today.correctCount || 0), icon: CircleCheck, tone: 'green' },
  {
    label: '今日学习',
    value: today.studyMinutes == null ? '未记录' : String(today.studyMinutes),
    unit: today.studyMinutes == null ? undefined : '分钟',
    icon: Timer,
    tone: 'gray'
  }
])

const quick = [
  { title: '开始刷题', desc: '按科目和难度抽题', icon: EditPen, path: '/practice' },
  { title: '错题本', desc: '回看已判错的题目', icon: Notebook, path: '/wrong' },
  { title: '收藏题目', desc: '重点题目回看', icon: Star, path: '/favorite' },
  { title: '学习统计', desc: '近 30 天作答趋势', icon: TrendCharts, path: '/stat' },
  { title: '院校查询', desc: '院校信息与招生链接', icon: School, path: '/schools' },
  { title: '备考资料', desc: '浏览已发布的资料', icon: Folder, path: '/documents' }
]

onMounted(async () => {
  try { Object.assign(today, await getTodayStat()) } catch { /* ignore */ }
})
</script>

<style scoped lang="scss">
.home { display: flex; flex-direction: column; gap: 24px; }

/* 顶部大卡片：问候语 + 诊断入口 */
.hero {
  position: relative; overflow: hidden;
  display: flex; flex-direction: column; gap: 20px;
  padding: 28px; border-radius: 20px;
  background: linear-gradient(120deg, #ffffff 0%, #f5f7ff 52%, #f2f0ff 100%);
  border: 1px solid #dde5ff;
  box-shadow: 0 1px 2px rgba(31, 35, 41, .04), 0 18px 40px -28px rgba(43, 90, 230, .45);
}
.hero-art {
  position: absolute; right: -70px; top: -90px; width: 420px; height: 420px; pointer-events: none;
  mask-image: radial-gradient(closest-side, #000 35%, transparent 100%);
}
.hero-head, .hero :deep(.diagnosis) { position: relative; }
.hero-title { font-size: 24px; }

/* 半透明分区面板，背后的布局光晕可以透出 */
.panel {
  padding: 20px; border-radius: 20px;
  background: var(--fx-panel);
  border: 1px solid rgba(255, 255, 255, .85);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .9), 0 16px 40px -32px rgba(43, 90, 230, .45);
}
.sec-title { font-size: 15px; font-weight: 600; margin: 0 0 12px; }

.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
.stat {
  position: relative; overflow: hidden;
  display: flex; align-items: center; gap: 14px; padding: 18px 20px;
  background: var(--c-surface); border: 1px solid var(--c-line); border-radius: 14px;
  box-shadow: var(--fx-shadow-card);
}
.stat-deco {
  position: absolute; right: -18px; bottom: -26px; opacity: .09; pointer-events: none;
  mask-image: linear-gradient(135deg, transparent 15%, #000 75%);
}
.stat-icon {
  width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
  display: grid; place-items: center;
}
.blue { color: var(--c-primary-strong); }
.green { color: #15803d; }
.gray { color: var(--c-ink-2); }
.stat-icon.blue { background: linear-gradient(145deg, #f1f5ff, #dde6ff); box-shadow: inset 0 0 0 1px rgba(43, 90, 230, .12); }
.stat-icon.green { background: linear-gradient(145deg, #eff9f2, #d8efe0); box-shadow: inset 0 0 0 1px rgba(21, 128, 61, .12); }
.stat-icon.gray { background: linear-gradient(145deg, #f5f6f8, #e6e9ee); box-shadow: inset 0 0 0 1px rgba(31, 35, 41, .06); }
.stat .num { font-size: 28px; font-weight: 700; line-height: 1.2; font-variant-numeric: tabular-nums; }
.stat .num.muted { font-size: 18px; font-weight: 600; color: var(--c-ink-2); padding-top: 4px; }
.stat .num .unit { font-size: 13px; color: var(--c-ink-2); margin-left: 4px; font-weight: 400; }
.stat .lbl { color: var(--c-ink-2); font-size: 13px; margin-top: 2px; }

.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
.quick {
  display: flex; align-items: center; gap: 14px; padding: 18px;
  color: var(--c-ink); background: var(--c-surface);
  border: 1px solid var(--c-line); border-radius: 14px;
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
.quick:hover {
  color: var(--c-ink);
  transform: translateY(-2px);
  border-color: transparent;
  background: linear-gradient(#fff, #fff) padding-box, linear-gradient(135deg, #7f9cff, #b3a6ff) border-box;
  box-shadow: 0 14px 30px -18px rgba(43, 90, 230, .55);
}
.quick:focus-visible { outline: 3px solid var(--c-primary-strong); outline-offset: 2px; }
.q-icon {
  width: 40px; height: 40px; border-radius: 10px; flex-shrink: 0;
  display: grid; place-items: center; color: var(--c-primary-strong);
  background: linear-gradient(145deg, #f1f5ff, #dde6ff); box-shadow: inset 0 0 0 1px rgba(43, 90, 230, .12);
}
.q-text { flex: 1; min-width: 0; }
.q-title { display: block; font-weight: 600; }
.q-desc { display: block; color: var(--c-ink-2); font-size: 12px; margin-top: 4px; }
.q-arrow {
  color: var(--c-primary-strong); opacity: 0; transform: translateX(-4px);
  transition: opacity .18s ease, transform .18s ease;
}
.quick:hover .q-arrow, .quick:focus-visible .q-arrow { opacity: 1; transform: none; }

@media (prefers-reduced-motion: reduce) {
  .quick, .q-arrow { transition: none; }
  .quick:hover { transform: none; }
}

/* 平板及以下：统计合并为一张三栏卡片，避免 2+1 留空 */
@media (max-width: 900px) {
  .stats {
    grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0;
    background: var(--c-surface); border: 1px solid var(--c-line); border-radius: 14px;
    box-shadow: var(--fx-shadow-card);
  }
  .stat {
    flex-direction: column; justify-content: center; text-align: center; gap: 0;
    padding: 14px 8px; border: 0; border-radius: 0; box-shadow: none; background: transparent;
  }
  .stat + .stat { border-left: 1px solid #eef0f3; }
  .stat-icon, .stat-deco { display: none; }
  .stat .num { font-size: 22px; }
  .stat .num.muted { font-size: 15px; }
  .stat .num .unit { display: block; margin: 0; font-size: 12px; }
  .stat .lbl { font-size: 12px; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

/* 手机宽度：收紧间距，快捷入口两列 */
@media (max-width: 640px) {
  .page.home { padding: 16px; gap: 16px; }
  .hero { padding: 16px; border-radius: 16px; gap: 12px; }
  .hero-art { width: 220px; height: 220px; right: -110px; top: -90px; }
  .hero-title { font-size: 20px; }
  .hero :deep(.diag-icon) { display: none; }
  .panel { padding: 12px; border-radius: 18px; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .quick { padding: 12px; gap: 10px; min-height: 56px; box-sizing: border-box; }
  .q-icon { width: 32px; height: 32px; border-radius: 8px; }
  .q-desc, .q-arrow { display: none; }
}
</style>
