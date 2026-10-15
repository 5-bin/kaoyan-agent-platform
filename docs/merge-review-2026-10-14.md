# 上游合并与冲突审查

日期：2026-10-14。RAG分支基线 `0dce756`，上游 `5-bin/kaoyan-agent-platform` 的main为 `6383c92528acbf23a8a6b3279bbe6516ffab4f9b`。本轮在原功能分支本地合并，未重写原提交，未提交、推送或合并GitHub PR #8。

## 处理原则与实质修复

- 审查39个冲突文件；保留上游认证、Redis注销撤销、实时角色和账号状态、分页绑定、Lombok构建及框架／HTTP检查。
- 保留RAG不可变资料／Qdrant、确定性推荐、授权作答快照、来源与版本校验、前端结果／来源展示。移除被合并复活的Python业务库查询文件。
- 统一TaskService分页为PageResult，推荐仍走同一Task流程，更新旧501测试。
- 删除自动合并产生的重复任务路由和重复JSON异常处理器，避免Spring启动失败；去除重复Maven依赖。
- 任务限额保留短事务与单实例锁，UTC换日转换为数据库本地时间；恢复未完成批次409拦截。
- 模型预算使用线程安全UTC计数，默认关闭生成式LLM、禁用SDK重试，保留受约束输出与失败降级。
- 前端合并会话切换／注销处理、提交防重入和空白拦截、移动宽度布局及来源弹窗；保留可配置代理。
- 原测试的旧handler、ID列表、无版本结果契约已迁到factory、作答快照和releaseId；H2增加快照列，Redis使用测试替身。环境初始化测试区分POSIX权限与Windows编码。
- 同步搭建文档、README、AGENTS及RAG契约，框架／RAG旧验收分别保留为历史。

## 本轮验证

环境：Windows、JDK17.0.20.1、Python3.13、Node24.19.0、独立Edge浏览器上下文；CI配置为JDK17／Python3.13／Node22，未把本地结果称为远端CI。

| 检查 | 本轮结果 | 实际范围 |
| --- | --- | --- |
| Python pytest | 68项通过 | 两边契约／工作流、预算并发与UTC换日、模拟供应商无重试、来源限制、Qdrant持久化（测试编码器）、环境初始化 |
| Java Maven verify | 40项通过、JAR打包成功 | 上游认证／分页／注销测试＋RAG测试；6项真实Java→临时Python链路；H2及Redis替身 |
| 前端 | vue-tsc、Vite配置tsc与生产构建通过 | 保留推荐和任务结果来源，统一注销／会话切换 |
| Playwright | 6项通过 | 1280／390宽度，模拟API的推荐、来源、安全渲染及迟到401隔离 |
| 隔离HTTP＋页面 | 15项链路检查通过 | 随机端口、真实Java／Python、文件H2、Redis／模型替身；包含6项桌面实际后端页面操作 |
| 静态检查 | 通过 | check-project.py、check-framework.py、暂存差异空白检查、无未解决冲突或冲突标记 |

HTTP检查实际覆盖真实进程重启、Python离线失败保存、RUNNING先落库、账号隔离、分页total及注销撤销。浏览器实际操作覆盖提交、来源结果弹窗、分页、退出和旧200／401迟到响应隔离。脚本等待ApplicationRunner完成恢复，文件H2配置WRITE_DELAY=0，避免测试强制终止时尚未刷盘；正常退出后临时服务均已停止。

最初验证暴露并修复了Spring重复异常映射、旧Mockito重复设桩空参数、Windows子进程输出编码、弹窗关闭按钮本地化及H2重启检查的刷盘／就绪时序问题；表中记录修复后的成功结果。

保留1条第三方anyio弃用提示、现有Vite大包警告。此前npm audit依赖告警仍需单独治理，本轮未执行强制升级。没有重置日常MySQL、执行新迁移、连接真实Redis／远程Qdrant／真实模型供应商、重新执行真实Embedding权重检索或验证公网。

原始报告在忽略目录`.cache/merge-java.log`、`.cache/merge-frontend.log`、`.cache/merge-browser.log`、`.cache/merge-http.log`、`.cache/merge-http-20261014.json`，不加入提交。

## 运行提示与限制

- 上游恢复了Redis注销撤销，因此新后端需要Redis；不为运行方便关闭撤销。真实Redis联调须单独执行。
- 已有MySQL库需要执行一次V7；本机此前已执行，本轮不重跑。
- 当前资料仍是4段408概念及3校6条专业，不代表全国覆盖；后续仍需小组内容审核、独立效果评估。
- 刷题批次快照／草稿／结束状态、答案展示DTO、统一统计及完整刷新令牌仍未实现，不扩大为完整业务或生产验收。

## Git状态与后续提交

上游main在本轮结束前仍为6383c92。39个冲突文件全部处理，合并结果已暂存；当前MERGE_HEAD指向该上游提交，本地仍待创建合并提交。未改写历史、未推送，GitHub上的PR冲突状态只有推送新提交后才会重新计算。

由仓库负责人在当前功能分支检查后完成：

```powershell
git status
git commit -m "merge: 同步小组main并整合RAG工作流"
git push origin feat/rag-workflows
```

这会更新原PR #8，无需另建PR或强制推送。合并到小组main仍须组员审查及远端CI通过。
