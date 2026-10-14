<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">早上好，{{ userStore.userInfo?.username }} 👋</h2>
      <p class="page-sub">今天也要加油上岸</p>
    </div>

    <div class="stats">
      <div class="card stat">
        <div class="stat-icon blue">✍️</div>
        <div>
          <div class="num">{{ today.questionCount || 0 }}</div>
          <div class="lbl">今日做题</div>
        </div>
      </div>
      <div class="card stat">
        <div class="stat-icon green">✓</div>
        <div>
          <div class="num">{{ today.correctCount || 0 }}</div>
          <div class="lbl">今日答对</div>
        </div>
      </div>
      <div class="card stat">
        <div class="stat-icon orange">⏱</div>
        <div>
          <div class="num">{{ today.studyMinutes || 0 }}<span class="unit">分钟</span></div>
          <div class="lbl">今日学习</div>
        </div>
      </div>
    </div>

    <div class="section">
      <h3 class="sec-title">快捷入口</h3>
      <div class="grid">
        <div v-for="q in quick" :key="q.path" class="card quick" @click="router.push(q.path)">
          <div class="q-icon" :style="{ background: q.bg }">{{ q.icon }}</div>
          <div class="q-title">{{ q.title }}</div>
          <div class="q-desc">{{ q.desc }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { getTodayStat } from '@/api/stat'

const router = useRouter()
const userStore = useUserStore()
const today = reactive({ questionCount: 0, correctCount: 0, studyMinutes: 0 })

const quick = [
  { title: '开始刷题', desc: '智能组卷练习', icon: '✍️', path: '/practice', bg: '#eef3ff' },
  { title: '错题本', desc: '攻克薄弱点', icon: '📕', path: '/wrong', bg: '#fdeeee' },
  { title: '收藏题目', desc: '重点题目回看', icon: '⭐', path: '/favorite', bg: '#fff7e6' },
  { title: '学习统计', desc: '趋势一目了然', icon: '📊', path: '/stat', bg: '#eaf7ee' },
  { title: '院校查询', desc: '择校信息查询', icon: '🏫', path: '/schools', bg: '#f0eaff' },
  { title: '备考资料', desc: '复习资料下载', icon: '📚', path: '/documents', bg: '#e6f6ff' }
]

onMounted(async () => {
  try { Object.assign(today, await getTodayStat()) } catch { /* ignore */ }
})
</script>

<style scoped lang="scss">
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 28px; }
.stat { display: flex; align-items: center; gap: 14px; padding: 18px 20px; }
.stat-icon {
  width: 44px; height: 44px; border-radius: 10px;
  display: grid; place-items: center; font-size: 20px;
}
.stat-icon.blue { background: #eef3ff; }
.stat-icon.green { background: #eaf7ee; color: var(--c-success); }
.stat-icon.orange { background: #fff7e6; color: var(--c-warning); }
.stat .num { font-size: 26px; font-weight: 700; }
.stat .num .unit { font-size: 13px; color: var(--c-ink-2); margin-left: 4px; font-weight: 400; }
.stat .lbl { color: var(--c-ink-2); font-size: 13px; margin-top: 2px; }

.section { margin-top: 8px; }
.sec-title { font-size: 15px; font-weight: 600; margin: 0 0 12px; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.quick { cursor: pointer; padding: 18px; transition: all .15s; }
.quick:hover { border-color: var(--c-primary); transform: translateY(-2px); box-shadow: var(--shadow-md); }
.q-icon { width: 40px; height: 40px; border-radius: 10px; display: grid; place-items: center; font-size: 18px; margin-bottom: 10px; }
.q-title { font-weight: 600; }
.q-desc { color: var(--c-ink-2); font-size: 12px; margin-top: 4px; }
</style>
