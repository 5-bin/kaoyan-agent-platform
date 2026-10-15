# PR #8 修复与验证

日期：2026-10-15（Asia/Shanghai）。基线提交：`a106615e663a2c8d6bcef4e0a31e2f1190832739`。本次在本地 `feat/rag-workflows` 工作区修复，不代表远端PR或CI已经更新。

## 修复行为

- 推荐删除改为带账号、类型、终态及未删除条件的原子更新，只设置内部 `deleted_at`；任务与结果继续保存，配额查询仍统计它们。两种历史及分页总数排除已删除记录，详情和重复删除404，非本人／非推荐404，未结束409。
- 总结在创建任务前检查全部有效作答快照。NULL或空对象返回409及明确提示，不创建任务、不调用Agent或消耗任务额度；完整快照继续按全部有效作答计算，不读取当前题目补造旧依据。
- 完整页面链路使用生产构建与Vite preview，通过临时代理请求真实Java。登录等待精确URL路径、当前用户名、任务接口200及分页，保留旧200／401响应隔离检查。
- 浏览器失败时输出截图、异常类别、接口路径／方法／状态及页面路径；不保存请求头、正文、令牌或完整URL。CI允许上传明确指定的隐藏诊断目录。

## 迁移与兼容

新增 [V8迁移](../kaoyan-B/src/main/resources/db/V8__task_soft_delete.sql)，为task增加可空DATETIME列，现有记录保持未删除。全新隔离库按V1→V7→V8准备；已有库核对迁移记录，各增量脚本仅应用一次，V8必须先于本版Java启动。当前没有自动执行迁移的功能。

本次只在H2的MySQL兼容模式执行迁移回归，没有运行现有MySQL上的迁移。不得重跑含DROP的V1，不回填历史作答快照。公开接口路径和包装保持不变，不公开deletedAt。已经被旧代码物理删除的任务无法通过V8恢复，其过去用量也无法凭空重建。

## 本次验证

环境：macOS、JDK25（编译目标17）、Python3.13、Node24.19.0；CI配置仍为JDK17／Python3.13／Node22。本机版本不等于CI版本验收。

| 检查 | 结果 | 范围 |
| --- | --- | --- |
| 修复前回归 | 两项预期失败 | 删除后再次请求得到200而非429；缺少快照得到200而非409 |
| Java verify及测试类路径 | 45项通过，JAR打包成功 | 每日／分钟配额分别覆盖成功与失败推荐；隐藏后的历史和详情、并发／越权／终态条件；旧／混合／空快照；真实Java→Python两题一对一错50%；增量迁移保留旧行 |
| Python pytest | 68项通过 | 新建本项目.venv并安装requirements-dev.txt；Mock模型及测试编码器Qdrant持久化；1条第三方anyio弃用提示 |
| 前端类型检查和生产构建 | 通过 | 独立npm ci后vue-tsc、tsc及Vite构建；保留已有大包警告 |
| 模拟API浏览器 | 8项通过 | 推荐、来源、迟到401及历史总结409后按钮恢复；桌面与390宽度，不是真实手机 |
| 完整HTTP／浏览器链路两次 | 各15项通过 | 每次新H2文件库、随机端口及独立浏览器；真实Java/Python、Redis／模型替身；每次包含6项桌面页面操作 |
| 浏览器失败诊断 | 通过预期失败验证 | 专用临时页面故意登录失败，检查截图、异常类别、接口401；确认JSON没有测试令牌及查询参数 |
| 静态检查 | 通过 | 文档链接、JSON、Python／Node语法、Git空白及差异范围 |

日志和报告保存在忽略的 `.cache/pr8-*`；测试进程只使用本次隔离数据。Python／前端依赖与构建文件不提交。

完整链路报告为 `.cache/pr8-http-1.json`、`.cache/pr8-http-2.json`，均记录 `temporaryProcessesStopped=true`。浏览器失败诊断验证产物位于 `.cache/pr8-browser-negative/`，属于测试页面，不是产品截图。缺少构建产物的前置检查也已验证，启动临时服务前即明确报错。

完整HTTP检查复用了本机已有Python3.13运行环境执行本工作区源码；最终pytest和Java verify中的真实Python子进程均已用本项目新建.venv复核。Java使用本机已安装的Maven3.9.9及已有依赖缓存，未复制其他工程的业务数据或虚拟环境。Node使用本机运行时；独立npm缓存及临时npm CLI均保存在忽略目录。

后续可按README复现：先安装本项目依赖并构建前端，设置 `PYTHON_EXECUTABLE` 为本项目 `.venv/bin/python` 的绝对路径，在kaoyan-B执行 `bash mvnw -B -ntp verify dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt`；在kaoyan-agent执行 `../.venv/bin/python -m pytest -q`；浏览器及完整链路命令见README，报告应使用新文件名。

npm ci报告8项现有依赖告警（7高、1中）；package.json和package-lock.json未修改，本轮未执行强制依赖升级。

## 验收边界

真实业务MySQL／Redis、真实Embedding权重、远程Qdrant、付费模型、真实手机和公网部署均未运行。Qdrant单元测试的编码器仅验证持久化与过滤，不证明语义检索质量。

没有Git提交、推送、合并或GitHub评论；没有操作现有业务库。远端CI须由后续明确授权的推送触发后另行核对。本次不改造原项目尚未完成的整套刷题、管理员发布或刷新令牌流程。
