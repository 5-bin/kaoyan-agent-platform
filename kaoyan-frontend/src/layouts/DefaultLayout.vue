<template>
  <div class="layout">
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
          <el-menu-item index="/"><el-icon><HomeFilled /></el-icon><span>首页</span></el-menu-item>
          <el-menu-item index="/practice"><el-icon><EditPen /></el-icon><span>刷题</span></el-menu-item>
          <el-menu-item index="/tasks"><el-icon><Notebook /></el-icon><span>Agent 任务</span></el-menu-item>
        </div>
        <div class="menu-group">
          <div class="group-label">复习</div>
          <el-menu-item index="/wrong"><el-icon><Notebook /></el-icon><span>错题本</span></el-menu-item>
          <el-menu-item index="/favorite"><el-icon><Star /></el-icon><span>我的收藏</span></el-menu-item>
          <el-menu-item index="/stat"><el-icon><TrendCharts /></el-icon><span>学习统计</span></el-menu-item>
        </div>
        <div class="menu-group">
          <div class="group-label">资源</div>
          <el-menu-item index="/schools"><el-icon><School /></el-icon><span>院校库</span></el-menu-item>
          <el-menu-item index="/documents"><el-icon><Folder /></el-icon><span>备考资料</span></el-menu-item>
        </div>
        <div v-if="userStore.isAdmin" class="menu-group">
          <div class="group-label">管理</div>
          <el-menu-item index="/admin/documents"><el-icon><Setting /></el-icon><span>管理后台</span></el-menu-item>
          <el-menu-item index="/admin/questions"><el-icon><EditPen /></el-icon><span>题目录入与审核</span></el-menu-item>
        </div>
      </el-menu>
    </aside>

    <section class="main">
      <header class="topbar">
        <div class="crumb">{{ crumbName }}</div>
        <el-dropdown trigger="click">
          <div class="user">
            <el-avatar :size="32" :src="userStore.userInfo?.avatarUrl" class="avatar">
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
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import {
  HomeFilled, EditPen, Notebook, Star, TrendCharts,
  School, Folder, Setting
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const activeMenu = computed(() => route.path.startsWith('/admin/')
  ? '/' + route.path.split('/').slice(1, 3).join('/')
  : '/' + (route.path.split('/')[1] || ''))
const crumbMap: Record<string, string> = {
  '': '首页', practice: '刷题', wrong: '错题本', favorite: '收藏',
  stat: '学习统计', schools: '院校库', documents: '备考资料',
  profile: '个人中心', tasks: 'Agent 任务',
  'admin/questions': '题目录入与审核', 'admin/documents': '资料管理'
}
const crumbName = computed(() => crumbMap[activeMenu.value.slice(1)] || '首页')

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
.layout { display: flex; height: 100vh; overflow: hidden; }

.sidebar {
  width: 220px; flex-shrink: 0;
  height: 100vh; overflow-y: auto;
  background: var(--c-surface);
  border-right: 1px solid var(--c-line);
  padding: 20px 12px;
  display: flex; flex-direction: column;
  position: sticky; top: 0;
}
.logo { display: flex; align-items: center; gap: 10px; padding: 4px 8px 24px; }
.logo-mark {
  width: 36px; height: 36px; border-radius: 10px;
  background: var(--c-primary); color: #fff;
  display: grid; place-items: center; font-weight: 700;
}
.logo-name { font-weight: 700; font-size: 15px; }
.logo-slogan { font-size: 11px; color: var(--c-ink-3); margin-top: 2px; }

.menu { background: transparent; flex: 1; padding: 0 4px; }
.menu-group { margin-bottom: 8px; }
.group-label {
  font-size: 11px; color: var(--c-ink-3); padding: 12px 12px 6px;
  letter-spacing: 1px;
}
:deep(.el-menu-item) {
  border-radius: var(--r-sm);
  margin: 2px 0;
  height: 44px; line-height: 44px;
  color: var(--c-ink-2);
  font-size: 14px;
  display: flex; align-items: center;
}
:deep(.el-menu-item:hover) { background: var(--c-bg); color: var(--c-ink); }
:deep(.el-menu-item.is-active) {
  background: var(--c-primary-light) !important;
  color: var(--c-primary) !important;
  font-weight: 600;
}
:deep(.el-menu-item .el-icon) { margin-right: 12px; font-size: 18px; flex-shrink: 0; }
:deep(.el-menu-item span) { line-height: 1; }

.main { flex: 1; display: flex; flex-direction: column; min-width: 0; height: 100vh; overflow: hidden; }
.topbar {
  height: 56px; flex-shrink: 0; background: var(--c-surface);
  border-bottom: 1px solid var(--c-line);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px;
}
.crumb { font-weight: 600; font-size: 15px; }
.user { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.avatar { background: var(--c-primary); color: #fff; }
.uname { font-weight: 600; font-size: 14px; }
.content { flex: 1; overflow-y: auto; padding-bottom: 40px; }
@media(max-width:640px) {
  .sidebar { width: 64px; padding: 12px 6px; }
  .logo { padding: 0 0 12px; justify-content: center; }
  .logo > div, .group-label { display: none; }
  :deep(.el-menu-item) { padding: 0 !important; justify-content: center; }
  :deep(.el-menu-item > span) { position: absolute; width: 1px; height: 1px; clip-path: inset(50%); overflow: hidden; }
  :deep(.el-menu-item .el-icon) { margin: 0; }
  .topbar { padding: 0 12px; }
  .user .el-tag { display: none; }
  .uname { max-width: 80px; overflow: hidden; text-overflow: ellipsis; }
}
</style>
