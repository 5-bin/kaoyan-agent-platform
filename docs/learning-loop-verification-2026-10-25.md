# 诊断、学情画像与自动推荐交付记录

核对日期：2026-10-25。初次代码交付在当前Vue → Java → Python工程实现代码，未操作日常数据库或重启日常服务；用户后续授权的本机迁移与启用单独记录在文末。业务规则与接口主契约见[搭建文档](../考研Agent平台搭建文档.md)，运行开关与命令见[README](../README.md#诊断学情画像与自动推荐2026-10-25)。

## 实际交付

- 新批次保存正式状态、服务器草稿/revision、题目固定快照、提示辅助与clientRequestId重放。普通练习逐题判分；诊断提交仅保存选择，结束时统一判分。提前结束不把草稿计作答，DELETE批次保留历史。
- 提供默认四科单选诊断及缺题清单；审核发布的版本化蓝图独立控制估分范围。无审核蓝图或必要证据缺失时不输出完整参考分。当前日常题库仍只覆盖数据结构，本轮没有把合成夹具导入日常库。
- 新增按知识点/难度统计的规则画像与历史、可靠事件工作器、失败重试、显著变化及条件/资料更新触发。自动推荐使用现有task表和额度，规则执行不依赖浏览器会话，也不调用外部模型。
- 新增不可变题目修订/审核提示及撤回管理API、历史招生指标审核录入API。默认管理页面继续保留原有录题/审核流程，新管理接口和请求格式见搭建文档。
- 首页/刷题页增加诊断入口；新批次页提供答题卡、草稿、提示及结束结果；统计页展示画像和变化；院校页保存自动推荐设置并展示画像版本、来源和历史线参考差值。助手按stats授权读取画像并解释异常。
- 新增V13增量脚本；`KAOYAN_LEARNING_ENABLED`默认关闭，启用前缺表会拒绝启动。旧批次保留原协议，旧作答不补造辅助状态或历史版本。保留用户已有README、搭建文档修改及数据收集/导学材料；未提交、推送或发布。

## 实际验证

本机JDK25.0.4.1（编译目标Java17）、Python3.13、Node22.23.3及Chrome。未在JDK17运行时或真实手机上验收。

| 检查 | 实际结果 | 环境及边界 |
| --- | --- | --- |
| Java `bash mvnw -B -ntp verify` | 149项通过，0失败、0错误、0跳过 | 含新增20项规则/业务测试；独立H2与现有真实Python进程链路，Redis及模型为替身 |
| Python pytest | 224项通过 | 含新增10项快照、授权投影及异常说明检查；1条已有Starlette/AnyIO弃用提示 |
| 前端生产构建 | 通过 | Vue/TypeScript检查与Vite构建通过；保留已有大于500kB包体提示 |
| Playwright全量页面 | 150项通过 | 桌面1280和390宽度、独立浏览器上下文、模拟API；新增4项诊断/草稿冲突回归 |
| 真实三端页面联调 | 两种宽度均通过 | 临时H2、合成四科20题/审核蓝图、Redis替身、真实Java→Python规则择校；LLM关闭 |
| Java进程中断恢复 | 通过 | 临时文件H2，暂停工作器后提交并提交事务，再终止本次Java并重启；恢复未消费画像事件，保留1次有效统计及同编号请求重放 |
| 静态检查 | 通过 | Python/Node脚本语法、Git差异空白检查；检查迁移与H2兼容夹具结构一致性 |

真实链路每种宽度均完成：创建20题诊断 → 保存并刷新恢复草稿 → 提交19题且结束前统计保持0 → 提前结束 → 有效已答19、未答1、正确19 → 画像独立证据19 → 保存本人自动推荐配置 → 保存1条SCHOOL_RECOMMEND规则任务。院校候选使用仓库小范围基线语料，不据此声称全国覆盖或当前招生事实已重新核验。

报告与截图位于本项目忽略的`.cache/`中：

- `learning-java-verify.log`、`learning-python-tests.log`、`learning-frontend-build.log`、`learning-all-browser-tests.log`。
- `learning-loop-accepted-20261025.json`记录桌面/窄屏和真实中断恢复，配套`-1280.png`、`-390.png`。
- 首轮检查发现H2保留字与夹具缺少展示表、测试点击Element Plus隐藏输入的问题，修复后重新验证；发布修订复用MyBatis时发现一级缓存与直接JDBC更新混用，已改用Mapper更新并添加历史版本/提示/撤回回归。

## 复现与启用

Java验证需将`PYTHON_EXECUTABLE`设置为当前项目安装了LangChain依赖的Python绝对路径。本机为`.cache/chat-venv/bin/python`。Maven Wrapper当前没有可执行位，因此实际使用`bash mvnw`；没有修改其文件权限。

```bash
# 项目根目录
.cache/chat-venv/bin/python -m pytest -q kaoyan-agent/tests

# kaoyan-B目录，先在环境中设置PYTHON_EXECUTABLE
bash mvnw -B -ntp verify dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt

# kaoyan-frontend目录
npm run build
npm run test:e2e

# 项目根目录；使用尚不存在的报告文件名
.cache/chat-venv/bin/python scripts/smoke-learning.py --output .cache/new-learning-loop-report.json
```

有本机Chrome时按README设置`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`；否则安装Playwright Chromium。脚本使用随机回环端口、独立浏览器上下文和临时目录，测试夹具拒绝写入普通MySQL或非测试H2路径。题目索引、资料索引和模型缓存指向本次临时目录；不使用日常向量库。结束后关闭本次服务并删除临时数据库，输出报告及截图；失败日志另存独立调试目录。新脚本使用`browser-learning-loop.cjs`，原有`browser-learning.cjs`保持原样。该进程组清理脚本按macOS/Linux实现，Windows尚未验证。

正式启用须先核对目标库V12、备份并验证恢复，再在授权维护窗口执行一次[V13](../kaoyan-B/src/main/resources/db/V13__learning_loop.sql)，然后一起更新三端并设置`KAOYAN_LEARNING_ENABLED=true`。本轮未执行日常库迁移。MySQL DDL不保证整个文件事务回滚；部分失败时先核对已创建表和备份，仅补齐未完成内容，不盲目重跑整个脚本。

回退时保留新表和数据。当前新版关闭开关后会拒绝旧逻辑继续处理L-批次；如果要换回V13前的旧JAR，须先阻止新批次入口及L-批次写入，旧JAR不能识别这些批次状态，不能直接接管未结束诊断。

## 未运行与待完成

- 初次代码交付时，日常MySQL上的V13迁移与真实Redis参与本轮新功能未运行；后续本机迁移及服务连通检查见下节。真实模型解释、远程Qdrant、公网部署、Windows与真机验收仍**未运行**。H2兼容夹具用LONGTEXT承载JSON，不代替MySQL JSON列与并发事务验证。
- 四科正式题目、审核估分蓝图、可比历史招生指标仍需按既有收集规范准备和内容审核；本轮未新增或伪造正式领域内容。
- 单选参考分和掌握指数尚无独立整卷成绩校准或学习效果证据，不提供录取概率、经验证置信区间或“提分有效”结论。
- 自动推荐与画像工作器面向单Java实例；扩展多实例、生产监控告警和运维后台需要另行验收。失败达到3次后保留失败/待处理依据，维护者检查原因后再恢复；修改推荐设置可重新申请推荐。

## 本机V13迁移与启用（后续授权）

2026-10-25，用户在了解V13内容后要求“帮我补充启动”，据此执行本机迁移、开关配置和服务启动；未导入题目、蓝图、招生指标或测试作答。

- 核对目标为回环地址的`kaoyan_dev`、MySQL 8.4.11，已有V7/V8必要字段及V10—V12相关表，V13的10张表均不存在。迁移期间应用三端保持停止。
- 完整备份保存到本机私密目录`.cache/v13-migration-20261025-140625/before.sql`，目录700、文件600，不应分享或提交。备份恢复至独立`kaoyan_v13_verify_*`库，并核对原有17张表的逐行SHA256摘要、数量、字段及索引一致。
- 在恢复库预演原V13脚本，核对旧数据不变及10张新表结构；然后在日常库执行一次同一脚本，再核对旧17张表数据和结构一致、新10张表与预演一致。未执行V1、旧种子或清理语句。私密`report.json`保存脚本/备份校验和、恢复库名与检查结果；`migration-intent.json`保存本次执行意图，不另建迁移登记业务表。
- 仅在根`.env`保存`KAOYAN_LEARNING_ENABLED=true`，保留模型与其他配置。使用现有构建及依赖启动MySQL、Redis、Agent8001、Java8080、Vue5173；Java启动结构检查通过，实际存在两个`learning-worker-*`调度线程。
- 只读检查：前端HTTP200、Agent `/health` HTTP200且status=ok、Java本人接口和学情状态接口未登录均401、前端代理同样401，Redis PING=PONG。三端就绪日志无ERROR行。运行元数据与日志位于`.cache/local-runtime/20261025-140653/`，连通结果见其中`read-only-verification.json`。

本次未修改业务源码，未重复运行前节测试；未登录日常账号、创建诊断、提交作答或启用任何人的自动推荐设置。上述401验证鉴权及代理连通，不等于登录后的业务链路验收。真实模型调用、日常MySQL上的刷题并发/恢复、完整四科内容、正式效果及公网部署仍**未运行**。

需要回退时停止业务写入，将开关关闭后重启Java，保留V13表及新增历史；不要直接整库恢复覆盖启用后产生的作答。备份已实际恢复验证，但仅在明确恢复范围、核对后续新增数据并获授权后用于恢复。再次启动本机时不要重复执行V13。
