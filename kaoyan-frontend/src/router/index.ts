import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  { path: '/login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  { path: '/register', component: () => import('@/views/Register.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      { path: '', name: 'dashboard', component: () => import('@/views/Dashboard.vue') },
      { path: 'practice', name: 'practice', component: () => import('@/views/PracticeHome.vue') },
      { path: 'practice/session/:sessionId', name: 'session', component: () => import('@/views/PracticeSession.vue') },
      { path: 'wrong', name: 'wrong', component: () => import('@/views/WrongBook.vue') },
      { path: 'favorite', name: 'favorite', component: () => import('@/views/Favorite.vue') },
      { path: 'stat', name: 'stat', component: () => import('@/views/Statistics.vue') },
      { path: 'schools', name: 'schools', component: () => import('@/views/SchoolList.vue') },
      { path: 'tasks', name: 'tasks', component: () => import('@/views/TaskList.vue') },
      { path: 'schools/:id', name: 'school-detail', component: () => import('@/views/SchoolDetail.vue') },
      { path: 'documents', name: 'documents', component: () => import('@/views/DocumentList.vue') },
      { path: 'profile', name: 'profile', component: () => import('@/views/Profile.vue') },
      { path: 'admin/documents', name: 'admin-documents', component: () => import('@/views/admin/AdminDocuments.vue'), meta: { admin: true } },
      { path: 'admin/questions', name: 'admin-questions', component: () => import('@/views/admin/AdminQuestions.vue'), meta: { admin: true } }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const userStore = useUserStore()
  if (!to.meta.public && !userStore.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin && !userStore.isAdmin) {
    return { path: '/' }
  }
})

export default router
