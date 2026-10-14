# 考研 Agent 平台前端

## 技术栈（锁定，禁止变更）
- Node.js 20 LTS
- Vue 3.5.x（Composition API + `<script setup>`）
- Vite 6.x
- TypeScript 5.x
- Vue Router 4
- Pinia 2
- Element Plus 2.8.x
- Axios 1.7.x
- ECharts 5.5.x（统计图表）
- 原生 CSS / SCSS

## 架构
- 单页应用（SPA）
- 按功能模块划分 views，组件复用放 components
- API 请求统一走 `src/api/` 下的模块，不在组件里直接调 axios
- 全局状态用 Pinia，只存用户信息、Token、字典等跨页面数据
- 路由守卫控制登录态，未登录跳 `/login`

## 目录结构
```
src/
├── api/                # 接口封装，按模块分文件
│   ├── request.ts      # axios 实例 + 拦截器
│   ├── auth.ts
│   ├── user.ts
│   ├── task.ts
│   ├── document.ts
│   ├── school.ts
│   ├── recommend.ts
│   ├── question.ts
│   ├── practice.ts
│   ├── mark.ts
│   ├── stat.ts
│   └── file.ts
├── assets/             # 静态资源
├── components/         # 通用组件
├── layouts/            # 布局（默认布局、空白布局）
├── router/             # 路由
├── stores/             # Pinia
├── types/              # TS 类型定义
├── utils/              # 工具函数
├── views/              # 页面
├── App.vue
└── main.ts
```

## 命名规范
- 组件文件用 PascalCase：`QuestionCard.vue`
- 页面文件用 PascalCase：`PracticeSession.vue`
- 工具函数用 camelCase：`formatDate.ts`
- Pinia store 用 camelCase：`useUserStore`
- API 函数用 camelCase：`login`、`getTaskList`
- 路由 path 用 kebab-case：`/practice/session/:id`

## 接口约定
- 后端基础路径 `/api`，开发环境用 Vite 代理到 `http://localhost:8080`
- 统一响应格式：`{ code, message, data }`，code=0 表示成功
- Token 存在 Pinia + localStorage，axios 拦截器自动加 `Authorization: Bearer xxx`
- 401 时清空登录态并跳 `/login`
- 分页接口返回 `{ total, page, size, list }`

## 用户信息
- 头像存 `user.avatarUrl`，直接是 URL
- 上传流程：先调 `POST /api/files/upload`（module=avatar）拿 URL，再调 `PUT /api/users/avatar`
- 头像上传用 Element Plus 的 `el-upload`，手动上传模式

## 编码禁止
- 禁止在组件里直接写 axios 请求，必须走 `src/api/`
- 禁止在组件里存 Token，统一由 Pinia 管理
- 禁止使用 Options API，统一用 `<script setup>`
- 禁止引入未列出的依赖
- 禁止硬编码后端地址，统一走环境变量 `VITE_API_BASE_URL`
- 禁止在模板里写复杂逻辑，抽到 computed 或方法

## 输出规范
- 先输出方案和文件清单，确认后再写代码
- 代码完整，含 import
- 多文件分文件输出，标注完整路径
- 每次只改指定文件，不主动创建辅助文件