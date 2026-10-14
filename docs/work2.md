# 考研 Agent 平台 - 前端 Codex 分阶段提示词

> 使用说明：按阶段 0 → 5 依次执行。
> 每阶段完成后手动测试，确认无误再进下一阶段。
> 每阶段结束 `git commit` 存档。

---

## 阶段 0：初始化

### 命令
```bash
npm create vite@latest kaoyan-frontend -- --template vue-ts
cd kaoyan-frontend
codex
```

### 提示词
```
/init
```

> 让它扫描目录生成初版 AGENTS.md，用项目根目录已有的 AGENTS.md 覆盖。

---

## 阶段 1：项目骨架 + 依赖 + 布局

### 提示词
```
# 任务
搭建 Vue 3 + Vite + TS 项目骨架，安装依赖，创建基础布局和路由。

# 上下文
项目根目录：kaoyan-frontend
已有 AGENTS.md，所有规范以 AGENTS.md 为准。

# 需要生成的文件

## 1. 安装依赖
npm install vue-router@4 pinia element-plus axios echarts
npm install -D sass @types/node unplugin-auto-import unplugin-vue-components

## 2. vite.config.ts
- 配置 @ 别名指向 src
- 配置 Element Plus 自动导入（unplugin-auto-import + unplugin-vue-components）
- 配置 dev server 代理：
  /api 代理到 http://localhost:8080

## 3. .env.development
VITE_API_BASE_URL=/api

## 4. .env.production
VITE_API_BASE_URL=/api

## 5. src/main.ts
- 注册 Pinia
- 注册 Vue Router
- 注册 Element Plus
- 引入 element-plus/dist/index.css
- 挂载 App

## 6. src/App.vue
- 只放 <router-view />

## 7. src/router/index.ts
- createRouter + createWebHistory
- 路由表见下方 # 路由表
- 全局前置守卫：未登录访问需认证页面跳 /login

## 8. src/layouts/DefaultLayout.vue
- 顶部导航栏：Logo、菜单（首页、刷题、错题、收藏、统计、院校、资料、任务、个人中心）
- 右上角：头像 + 下拉菜单（个人中心、登出）
- 主体区域：<router-view />
- 用 Element Plus 的 el-menu、el-dropdown、el-avatar

## 9. src/layouts/BlankLayout.vue
- 只有 <router-view />，用于登录页

## 10. src/stores/user.ts
- state：token、refreshToken、userInfo（含 id、username、role、avatarUrl、targetSchool 等）
- actions：login、logout、refreshUserInfo、updateAvatar
- getters：isLoggedIn、isAdmin
- 持久化到 localStorage

## 11. src/types/api.ts
- 定义 Result<T>、PageResult<T>
- 定义 User、Task、Document、School、SchoolDetail、RecommendRecord、
  Question、PracticeRecord、UserQuestionMark、StudyStat 类型

## 12. src/api/request.ts
- 创建 axios 实例，baseURL = import.meta.env.VITE_API_BASE_URL
- 请求拦截器：自动加 Authorization: Bearer {token}
- 响应拦截器：
  - code === 0 → 返回 data
  - code !== 0 → ElMessage.error(message)，Promise.reject
  - HTTP 401 → 清空登录态，跳 /login
  - HTTP 403 → ElMessage.error('无权访问')

# 路由表

/login              → BlankLayout > Login.vue           （免登录）
/register           → BlankLayout > Register.vue        （免登录）
/                   → DefaultLayout > Dashboard.vue     （需登录）
/practice           → DefaultLayout > PracticeHome.vue  （需登录）
/practice/session/:sessionId → DefaultLayout > PracticeSession.vue
/wrong              → DefaultLayout > WrongBook.vue
/favorite           → DefaultLayout > Favorite.vue
/stat               → DefaultLayout > Statistics.vue
/schools            → DefaultLayout > SchoolList.vue
/schools/:id        → DefaultLayout > SchoolDetail.vue
/documents          → DefaultLayout > DocumentList.vue
/tasks              → DefaultLayout > TaskList.vue
/profile            → DefaultLayout > Profile.vue

# 约束
- 严格按 AGENTS.md
- 不引入未列出的依赖
- 先输出文件清单，我确认后再逐个生成
- 不要动页面内容（Login.vue 等只建空壳）

# 验证
手动运行 npm run dev，浏览器打开 http://localhost:5173
应看到导航栏和空白首页
```

---

## 阶段 2：API 封装 + 登录注册 + 用户模块

### 提示词
```
# 任务
生成所有 API 封装，实现登录、注册、个人中心。

# 上下文
阶段 1 骨架已就绪，types 已定义。
规范以 AGENTS.md 为准。

# 需要生成的文件

## API 模块（src/api/）
每个模块只导出函数，返回 Promise，不写业务逻辑。

### auth.ts
- register(data: {username, password})
- login(data: {username, password})
- refresh(refreshToken: string)
- logout()

### user.ts
- getCurrentUser()
- updateAvatar(data: {avatarUrl})
- updateProfile(data: {avatarUrl, targetSchool, targetMajor, examYear, background})

### task.ts
- submitTask(data: {taskType, input})
- getTaskList(params: {page, size})
- getTaskDetail(taskId: string)

### document.ts
- getPublishedDocuments(params: {subject?})
- getAdminDocumentList(params: {status?, page, size})
- createDocument(data)
- updateDocument(id, data)
- deleteDocument(id)
- reviewDocument(id, data: {status, comment})

### school.ts
- searchSchools(params: {province?, level?, majorName?})
- getSchoolDetail(schoolId: number)

### recommend.ts
- generateRecommend()
- getRecommendList()
- deleteRecommend(id: number)

### question.ts
- getPracticeQuestions(params: {subject?, difficulty?, knowledgePoint?, limit})
- getQuestionDetail(id: number)
- getPendingQuestions(params: {page, size})
- createQuestion(data)
- updateQuestion(id, data)
- deleteQuestion(id)
- reviewQuestion(id, data: {status, comment})

### practice.ts
- startSession(data: {subject, difficulty, count})
- answerQuestion(sessionId, data: {questionId, answer})
- getSessionSummary(sessionId)
- getSessionList()
- getSessionDetail(sessionId)
- abandonSession(sessionId)

### mark.ts
- addWrong(questionId)
- removeWrong(questionId)
- addFavorite(questionId)
- removeFavorite(questionId)
- getWrongList()
- getFavoriteList()

### stat.ts
- getTodayStat()
- getRangeStat(params: {from, to})
- getOverview()

### file.ts
- uploadFile(file: File, module: string)  // FormData
- deleteFile(objectKey: string)

## 页面（src/views/）

### Login.vue
- 表单：用户名、密码
- 提交调 userStore.login
- 成功后跳 /（或 query.redirect）
- 链接到 /register

### Register.vue
- 表单：用户名、密码、确认密码
- 前端校验：用户名 3-64 位，密码 6-32 位，两次密码一致
- 提交调 auth.register，成功后自动登录并跳 /

### Profile.vue
- 展示当前用户信息（用户名、角色、头像、档案）
- 头像上传：el-upload 手动上传，先调 file.uploadFile(file, 'avatar')，
  再调 user.updateAvatar({avatarUrl})
- 档案表单：targetSchool、targetMajor、examYear、background
- 提交调 user.updateProfile

# 约束
- 请求参数类型用 types/api.ts 里定义的类型
- 组件用 <script setup lang="ts">
- 表单校验用 el-form 的 rules
- 先输出文件清单，我确认后再逐个生成

# 验证
npm run dev
1. 访问 /register 注册新用户，成功后自动登录跳首页
2. 登出，再访问 /login 用 student/password 登录
3. 进入 /profile，上传头像，改档案，刷新页面确认数据持久化
```

---

## 阶段 3：刷题 + 错题 + 收藏

### 提示词
```
# 任务
实现刷题首页、刷题会话、错题本、收藏页。

# 上下文
API 封装已就绪。
规范以 AGENTS.md 为准。

# 需要生成的文件

## src/views/PracticeHome.vue
- 卡片式配置：科目（数据结构/操作系统/计算机网络/计算机组成原理）、
  难度（EASY/MEDIUM/HARD）、题目数量（5/10/20）
- 点击"开始刷题"调 practice.startSession，拿 sessionId 后跳
  /practice/session/{sessionId}
- 下方展示历史会话列表（调 practice.getSessionList），
  每条可点击进入 /practice/session/{sessionId}
- 每条右侧有"删除"按钮，调 practice.abandonSession

## src/views/PracticeSession.vue
- 进入页面调 practice.getSessionDetail(sessionId) 拿题目列表
- 顶部进度条：已完成/总数
- 主区显示当前题：题干、四个选项（el-radio-group）
- 提交按钮调 practice.answerQuestion(sessionId, {questionId, answer})
- 提交后显示对错和解析，下一题按钮切换
- 答完最后一题展示汇总：总题数、已答、正确数、正确率
- 右上角"结束会话"按钮，调 practice.abandonSession

## src/views/WrongBook.vue
- 调 mark.getWrongList 拿错题列表
- 每条展示题干、错误次数、最近错误时间
- 点击展开解析
- "移除"按钮调 mark.removeWrong
- "收藏"按钮调 mark.addFavorite

## src/views/Favorite.vue
- 调 mark.getFavoriteList 拿收藏列表
- 每条展示题干、收藏时间
- "移除收藏"调 mark.removeFavorite
- "加入错题"调 mark.addWrong

## 组件（src/components/）
- QuestionCard.vue：展示单题（题干 + 选项 + 解析），props 控制是否显示答案
- SessionSummary.vue：会话汇总卡片

# 约束
- 用 Element Plus 的 el-card、el-radio-group、el-progress、el-button
- 答题后立刻反馈，不用刷新页面
- 先输出文件清单，我确认后再逐个生成

# 验证
npm run dev
1. 进入 /practice 开始一次刷题，答对和答错各一题
2. 完成后看汇总数据是否正确
3. 进入 /wrong 看错题是否出现
4. 进入 /favorite 收藏一道题，看列表是否刷新
```

---

## 阶段 4：统计 + 院校 + 资料 + 任务

### 提示词
```
# 任务
实现统计图表、院校查询、资料浏览、任务提交。

# 上下文
API 封装已就绪，ECharts 已安装。
规范以 AGENTS.md 为准。

# 需要生成的文件

## src/views/Statistics.vue
- 顶部三张卡片：今日做题数、今日正确数、累计正确率
- 折线图：近 30 天每日做题数（调 stat.getRangeStat）
- 饼图：各科目做题占比（从 practice 记录统计）
- 用 ECharts，按需引入 LineChart、PieChart

## src/views/SchoolList.vue
- 顶部筛选：省份（下拉）、层次（985/211/双一流）、专业名（输入）
- 调 school.searchSchools 拿列表
- 卡片式展示：院校名、省份、层次
- 点击卡片跳 /schools/:id

## src/views/SchoolDetail.vue
- 调 school.getSchoolDetail(id) 拿院校 + 详情
- 展示院校基础信息
- 表格展示专业详情：专业名、专业代码、年份、招生人数、分数线
- 按年份倒序

## src/views/DocumentList.vue
- 顶部科目筛选
- 调 document.getPublishedDocuments 拿列表
- 卡片展示：标题、科目、来源链接
- 点击展开正文（或跳外链）

## src/views/TaskList.vue
- 顶部"提交任务"按钮，弹对话框：
  - 任务类型：KNOWLEDGE_QA / SCHOOL_RECOMMEND
  - 输入：textarea
- 提交调 task.submitTask
- 下方任务历史列表，分页（调 task.getTaskList）
- 点击某条任务，展开查看结果（task.getTaskDetail）

## src/views/Dashboard.vue
- 欢迎语 + 用户名
- 快捷入口卡片：开始刷题、错题本、收藏、学习统计
- 今日统计卡片（调 stat.getTodayStat）
- 最近任务列表（前 5 条）

# 约束
- ECharts 在组件卸载时销毁实例，避免内存泄漏
- 用 el-card、el-table、el-pagination、el-dialog
- 先输出文件清单，我确认后再逐个生成

# 验证
npm run dev
1. /stat 页面图表渲染正常
2. /schools 筛选"福建"能查到厦门大学、福州大学
3. /documents 展示已发布资料
4. /tasks 提交一个 KNOWLEDGE_QA，看历史列表
```

---

## 阶段 5：管理端 + 优化

### 提示词
```
# 任务
实现管理端页面，优化交互和错误处理。

# 上下文
所有用户端页面已完成。
规范以 AGENTS.md 为准。
仅 ADMIN 角色能访问管理页面。

# 需要生成的文件

## 路由调整（src/router/index.ts）
新增管理端路由，meta.requiresAdmin = true：
/admin/documents       → AdminDocuments.vue
/admin/questions       → AdminQuestions.vue

路由守卫：非 ADMIN 访问管理端跳 /，并 ElMessage.error

## src/views/admin/AdminDocuments.vue
- 表格展示所有资料（调 document.getAdminDocumentList）
- 筛选：状态（DRAFT/PENDING_REVIEW/PUBLISHED/REJECTED）
- 每行操作：编辑、删除、审核
- 审核弹窗：通过 / 拒绝 + 意见，调 document.reviewDocument
- 新建按钮，弹窗表单，调 document.createDocument

## src/views/admin/AdminQuestions.vue
- 表格展示待审核题目（调 question.getPendingQuestions）
- 每行操作：通过、拒绝、编辑、删除
- 审核调 question.reviewQuestion
- 新建按钮，弹窗表单，调 question.createQuestion

## src/components/AppHeader.vue
- 顶部导航，右上角用户下拉
- 菜单根据角色显示：ADMIN 显示管理端入口
- 头像展示 userStore.userInfo.avatarUrl

## 错误处理优化
- src/utils/errorHandler.ts
  - handleApiError(error)：统一处理 401/403/500
  - 401 已在拦截器处理，这里处理其他错误提示
- src/utils/format.ts
  - formatDate(dt)：yyyy-MM-dd
  - formatDateTime(dt)：yyyy-MM-dd HH:mm:ss
  - formatPercent(n)：百分比

## 交互优化
- 所有列表页加 loading 状态
- 所有提交按钮加 loading，防重复点击
- 空数据用 el-empty 展示
- 表格列自适应

# 约束
- 管理端页面组件放 src/views/admin/ 子目录
- 非 ADMIN 用户看不到菜单入口，直接访问也拦截
- 先输出文件清单，我确认后再逐个生成

# 验证
npm run dev
1. 用 admin/password 登录，右上角能看到"管理端"入口
2. 进入 /admin/documents，能审核资料
3. 进入 /admin/questions，能审核题目
4. 用 student/password 登录，看不到管理端入口，直接访问 URL 被拦截跳首页
```

---

## 附：Codex 出错回滚策略

| 症状 | 处理 |
|---|---|
| 生成了多余的组件 | `git clean -fd` 删掉，重新给更严格的提示词 |
| 组件里直接调 axios | 提示词强调"必须走 src/api/" |
| 用了 Options API | 提示词强调 `<script setup lang="ts">` |
| Token 存在组件里 | 提示词强调由 Pinia 统一管理 |
| 路由跳转用 location.href | 提示词强调用 router.push |
| ECharts 内存泄漏 | 提示词强调 onUnmounted 里 dispose |
| 硬编码后端地址 | 提示词强调用 VITE_API_BASE_URL |
| 图片上传走前端直传 OSS | 提示词强调先调后端 /api/files/upload |

---

## 附：通用提示词模板

临时加需求时用这段：

```
# 角色
资深 Vue 3 前端工程师，精通 Vue 3 + Vite + TS + Element Plus + Pinia。

# 任务
[具体功能]

# 上下文
项目是 Vue 3.5 + Vite 6 + TS + Element Plus 2.8 + Pinia 2 + Axios，
已存在 api 封装、stores、types、layouts。

# 约束
- 用 <script setup lang="ts">
- 请求走 src/api/ 下的模块，不在组件里直接调 axios
- Token 由 Pinia 管理，组件不直接读 localStorage
- 路由跳转用 router.push，不用 location.href
- 禁止引入未列出的依赖

# 输出规范
1. 先输出方案和文件清单，我确认后再写代码
2. 代码完整，含 import
3. 多文件分文件输出，标注完整路径
```