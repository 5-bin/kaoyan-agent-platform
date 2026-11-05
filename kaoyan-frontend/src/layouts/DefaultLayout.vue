<template>
  <div class="layout">
    <!-- 装饰背景（仅柔光）：首页四团光晕，其余页面只保留顶部两团且更淡 -->
    <div class="backdrop" :class="{ home: isHome }" aria-hidden="true">
      <span class="glow glow-bridge" />
      <span class="glow glow-top" />
      <span v-if="isHome" class="glow glow-mid" />
      <span v-if="isHome" class="glow glow-bottom" />
    </div>

    <aside class="sidebar">
      <div class="logo">
        <span class="logo-mark">考</span>
        <div>
          <div class="logo-name">考研 Agent</div>
          <div class="logo-slogan">智能备考平台</div>
        </div>
      </div>

      <el-menu :default-active="activeMenu" router class="menu">
        <div class="menu-group">
          <div class="group-label">学习</div>
          <el-menu-item :index="navigationPath('HOME')"><el-icon><HomeFilled /></el-icon><span>首页</span></el-menu-item>
          <el-menu-item :index="navigationPath('PRACTICE')"><el-icon><EditPen /></el-icon><span>刷题</span></el-menu-item>
          <el-menu-item :index="navigationPath('ASSISTANT')"><el-icon><ChatDotRound /></el-icon><span>Agent 助手</span></el-menu-item>
        </div>
        <div class="menu-group">
          <div class="group-label">复习</div>
          <el-menu-item :index="navigationPath('NOTES')"><el-icon><Document /></el-icon><span>个人笔记</span></el-menu-item>
          <el-menu-item :index="navigationPath('WRONG')"><el-icon><Notebook /></el-icon><span>错题本</span></el-menu-item>
          <el-menu-item :index="navigationPath('FAVORITE')"><el-icon><Star /></el-icon><span>我的收藏</span></el-menu-item>
          <el-menu-item :index="navigationPath('STATS')"><el-icon><TrendCharts /></el-icon><span>学习统计</span></el-menu-item>
        </div>
        <div class="menu-group">
          <div class="group-label">资源</div>
          <el-menu-item :index="navigationPath('SCHOOLS')"><el-icon><School /></el-icon><span>院校库</span></el-menu-item>
          <el-menu-item :index="navigationPath('DOCUMENTS')"><el-icon><Folder /></el-icon><span>备考资料</span></el-menu-item>
        </div>
        <div v-if="userStore.isAdmin" class="menu-group">
          <div class="group-label">管理</div>
          <el-menu-item :index="navigationPath('ADMIN_DOCUMENTS')"><el-icon><Setting /></el-icon><span>管理后台</span></el-menu-item>
          <el-menu-item :index="navigationPath('ADMIN_QUESTIONS')"><el-icon><EditPen /></el-icon><span>题目录入与审核</span></el-menu-item>
        </div>
      </el-menu>
    </aside>

    <section class="main">
      <header class="topbar">
        <div class="crumb">{{ crumbName }}</div>
        <el-dropdown trigger="click">
          <div class="user">
            <el-avatar :size="32" :src="userStore.avatarDisplayUrl" class="avatar">
              {{ userStore.userInfo?.username?.[0]?.toUpperCase() }}
            </el-avatar>
            <span class="uname">{{ userStore.userInfo?.username }}</span>
            <el-tag size="small" :type="userStore.isAdmin ? 'danger' : 'info'" effect="plain">
              {{ userStore.isAdmin ? '管理员' : '考生' }}
            </el-tag>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/profile')">个人中心</el-dropdown-item>
              <el-dropdown-item divided @click="onLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>
      <main class="content">
        <router-view v-if="route.path !== '/tasks'" />
        <ChatAssistant v-if="assistantMounted" v-show="route.path === '/tasks' || assistant.open" :compact="route.path !== '/tasks'" />
        <el-button v-if="assistantEligible && !assistant.open && route.path !== '/tasks'" class="assistant-launch" type="primary" @click="assistant.open = true">考研助手</el-button>
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ChatAssistant from '@/views/ChatAssistant.vue'
import { navigationPath } from '@/utils/assistant-navigation'
import { useAssistantStore } from '@/stores/assistant'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import {
  HomeFilled, EditPen, Notebook, Star, TrendCharts,
  School, Folder, Setting, Document, ChatDotRound
} from '@element-plus/icons-vue'

const assistant = useAssistantStore()
const assistantEligible = computed(() => ['/wrong', '/favorite', '/stat', '/documents', '/practice', '/notes'].some(path => route.path === path || route.path.startsWith(path + '/')))
const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const assistantMounted = ref(false)
const isHome = computed(() => route.path === '/')
watch([() => route.path, () => assistant.open], ([path, open]) => { if (path === '/tasks' || open) assistantMounted.value = true }, { immediate: true })

const activeMenu = computed(() => route.path.startsWith('/admin/')
  ? '/' + route.path.split('/').slice(1, 3).join('/')
  : '/' + (route.path.split('/')[1] || ''))
const crumbMap: Record<string, string> = {
  '': '首页', practice: '刷题', wrong: '错题本', favorite: '收藏',
  stat: '学习统计', schools: '院校库', documents: '备考资料', notes: '个人笔记',
  profile: '个人中心', tasks: 'Agent 助手',
  'admin/questions': '题目录入与审核', 'admin/documents': '资料管理'
}
const crumbName = computed(() => crumbMap[activeMenu.value.slice(1)] || '首页')

watch(() => userStore.token, (token, previous) => { if (token !== previous) { assistant.reset(); assistantMounted.value = route.path === '/tasks' } })
const onLogout = async () => {
  try {
    await userStore.logout()
    ElMessage.success('已退出')
  } finally {
    if (!userStore.isLoggedIn) await router.replace({ path: '/login', query: { redirect: route.fullPath } })
  }
}
</script>

<style scoped lang="scss">
.assistant-launch { position:fixed; right:20px; bottom:24px; z-index:20 }
.layout { display: flex; height: 100vh; overflow: hidden; position: relative; background: var(--c-bg); }

/* 背景层固定在布局内，不随内容滚动；侧栏与主区共用，避免两块区域割裂 */
.backdrop { position: absolute; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
.backdrop > span { position: absolute; }
.glow-bridge {
  left: 40px; top: -160px; width: 560px; height: 440px; opacity: .6;
  background:
    radial-gradient(40% 45% at 45% 50%, var(--fx-glow-blue), transparent 72%),
    radial-gradient(30% 34% at 70% 62%, var(--fx-glow-violet), transparent 72%);
}
.glow-top {
  right: -60px; top: -140px; width: 760px; height: 520px; opacity: .6;
  background:
    radial-gradient(40% 46% at 62% 42%, var(--fx-glow-blue), transparent 72%),
    radial-gradient(34% 40% at 34% 64%, var(--fx-glow-violet), transparent 72%);
}
.home .glow-bridge, .home .glow-top { opacity: 1; }
.glow-mid {
  left: 40px; top: 44%; width: 620px; height: 460px;
  background: radial-gradient(40% 45% at 45% 50%, var(--fx-glow-violet), transparent 72%);
}
.glow-bottom {
  right: -120px; bottom: -160px; width: 700px; height: 480px;
  background:
    radial-gradient(42% 46% at 55% 50%, var(--fx-glow-blue), transparent 72%),
    radial-gradient(30% 34% at 30% 40%, var(--fx-glow-violet), transparent 72%);
}

.sidebar {
  width: 220px; flex-shrink: 0;
  height: 100vh; overflow-y: auto;
  background: var(--fx-glass);
  padding: 0 12px 20px;
  display: flex; flex-direction: column;
  position: relative; z-index: 1;
}
/* 侧栏右侧淡出分隔线，从顶带下方开始 */
.sidebar::after {
  content: ''; position: absolute; top: 57px; bottom: 32px; right: 0; width: 1px; pointer-events: none;
  background: linear-gradient(180deg, rgba(214, 222, 240, .9), rgba(214, 222, 240, .5) 60%, transparent);
}
/* 与顶栏同高、同底线，组成横贯全宽的顶带 */
.logo {
  display: flex; align-items: center; gap: 10px;
  min-height: 56px; margin: 0 -12px 8px; padding: 0 20px;
  border-bottom: 1px solid var(--fx-line);
}
.logo-mark {
  width: 36px; height: 36px; border-radius: 10px; color: #fff;
  display: grid; place-items: center; font-weight: 700; flex-shrink: 0;
  background: linear-gradient(140deg, #4d7bff 0%, var(--c-primary-strong) 55%, #4b46e0 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .35), 0 6px 14px -6px rgba(43, 90, 230, .7);
}
.logo-name { font-weight: 700; font-size: 15px; }
.logo-slogan { font-size: 12px; color: var(--c-ink-2); margin-top: 2px; }

.menu { background: transparent; flex: 1; padding: 0 4px; }
.menu-group { margin-bottom: 8px; }
.group-label {
  font-size: 12px; color: var(--c-ink-2); padding: 12px 12px 6px;
  letter-spacing: 1px;
}
:deep(.el-menu-item) {
  border-radius: var(--r-sm);
  margin: 2px 0;
  height: 44px; line-height: 44px;
  color: var(--c-ink-2);
  font-size: 14px;
  display: flex; align-items: center;
  background: transparent;
  transition: background-color .15s ease, color .15s ease, box-shadow .15s ease;
}
:deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, .75);
  box-shadow: inset 0 0 0 1px #e3e8f4;
  color: var(--c-ink);
}
:deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #eaf0ff, #f3f5ff) !important;
  box-shadow: inset 0 0 0 1px #d6e0ff, 0 6px 16px -12px rgba(43, 90, 230, .55);
  color: var(--c-primary-deep) !important;
  font-weight: 600;
}
:deep(.el-menu-item.is-active .el-icon) { filter: drop-shadow(0 2px 4px rgba(43, 90, 230, .35)); }
:deep(.el-menu-item .el-icon) { margin-right: 12px; font-size: 18px; flex-shrink: 0; }
:deep(.el-menu-item span) { line-height: 1; }

.main { flex: 1; display: flex; flex-direction: column; min-width: 0; height: 100vh; overflow: hidden; position: relative; z-index: 1; }
.topbar {
  height: 56px; flex-shrink: 0;
  background: var(--fx-glass);
  border-bottom: 1px solid var(--fx-line);
  backdrop-filter: saturate(1.6) blur(14px);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px;
}
@supports not (backdrop-filter: blur(1px)) {
  .topbar { background: var(--c-surface); }
}
.crumb { font-weight: 600; font-size: 15px; }
.user { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.avatar { background: var(--c-primary-strong); color: #fff; }
.uname { font-weight: 600; font-size: 14px; }
.content { flex: 1; overflow-y: auto; padding-bottom: 40px; }

@media (prefers-reduced-motion: reduce) {
  :deep(.el-menu-item) { transition: none; }
}
@media(max-width:640px) {
  .sidebar { width: 64px; padding: 0 6px 12px; }
  .sidebar::after { top: 57px; }
  .logo { margin: 0 -6px 8px; padding: 0; justify-content: center; }
  .logo > div, .group-label { display: none; }
  :deep(.el-menu-item) { padding: 0 !important; justify-content: center; }
  :deep(.el-menu-item > span) { position: absolute; width: 1px; height: 1px; clip-path: inset(50%); overflow: hidden; }
  :deep(.el-menu-item .el-icon) { margin: 0; }
  .topbar { padding: 0 12px; }
  .user .el-tag { display: none; }
  .uname { max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
}
</style>
