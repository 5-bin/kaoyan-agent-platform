# 考研 Agent 智能备考平台

408 考研刷题 + 错题/收藏管理 + AI 择校与总结的全栈项目。

## 技术栈

- **前端**：Vue 3.5 + TypeScript + Vite 6 + Element Plus 2.8 + Pinia 2
- **后端**：Spring Boot 3.5 + MyBatis-Plus + Spring Security + JWT + OpenFeign
- **AI Agent**：FastAPI 0.115 + SQLAlchemy async + OpenAI SDK（智谱 GLM）
- **数据库**：MySQL 8

## 目录结构

```
Kagent/
├── kaoyan-frontend/     # Vue 前端（5173）
├── kaoyan-B/            # Spring Boot 后端（8080）
├── kaoyan-agent/        # FastAPI Agent（8001）
└── docs/                # 设计文档
```

## 本地运行

### 1. 准备 MySQL
- 建库：`CREATE DATABASE kaoyan DEFAULT CHARSET utf8mb4;`
- 执行初始化脚本：
  ```bash
  mysql -uroot -p kaoyan < kaoyan-B/src/main/resources/db/V1__init.sql
  mysql -uroot -p kaoyan < kaoyan-B/src/main/resources/db/V4_network_seed.sql
  mysql -uroot -p kaoyan < kaoyan-B/src/main/resources/db/V5_school_seed.sql
  mysql -uroot -p kaoyan < kaoyan-B/src/main/resources/db/V6_school_detail_seed.sql
  ```
- 种子账号：`admin/password`（管理员）、`student/password`（考生）

### 2. 启动 FastAPI Agent
```bash
cd kaoyan-agent
py -3.12 -m venv .venv
# Windows: .\.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 然后编辑填 LLM_API_KEY、DB_PASSWORD
uvicorn main:app --port 8001 --reload
```

### 3. 启动 Spring Boot 后端
```bash
cd kaoyan-B
# 首次：从示例复制配置文件
cp src/main/resources/application-dev.example.yml src/main/resources/application-dev.yml
# 编辑里面的 MySQL 密码、OSS key、JWT secret
./mvnw spring-boot:run
# Windows: mvnw.cmd spring-boot:run
```

### 4. 启动前端
```bash
cd kaoyan-frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173

## 端口约定

| 服务 | 端口 |
|------|------|
| 前端 Vite dev | 5173 |
| Spring Boot | 8080 |
| FastAPI Agent | 8001 |
| MySQL | 3306 |

## 环境变量

**敏感配置不入库**，仓库只留 `.example` 模板，本地复制后再填：

后端：
```bash
cp kaoyan-B/src/main/resources/application-dev.example.yml kaoyan-B/src/main/resources/application-dev.yml
```
必改项：
- 数据库密码
- OSS AccessKeyId / Secret（如不用 OSS 可留空）
- JWT secret（≥32 字节随机串）
- `kaoyan.agent.internal-key`（必须和 Agent 一致）

Agent：
```bash
cp kaoyan-agent/.env.example kaoyan-agent/.env
```
必改项：
- `LLM_API_KEY`：智谱开放平台 key（https://open.bigmodel.cn/）
- `DB_PASSWORD`：MySQL 密码
- `AGENT_INTERNAL_KEY`：必须和后端一致

## 主要功能

- 刷题：408 题库，自定义题量，交卷即时反馈
- 错题本 / 收藏：分页懒加载
- 做题记录：分页 + 回顾
- 院校库：按省份/层次/专业检索，AI 择校推荐弹窗
- AI 总结：做完一批题生成薄弱点分析
- 个人中心：目标院校/专业/背景档案（喂给 Agent）
