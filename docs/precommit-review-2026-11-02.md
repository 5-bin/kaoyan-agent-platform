# 提交前检查与推送范围（2026-11-02）

用户授权：检查当前项目，问题修复后按功能分多次提交，并推送至 `5-bin/kaoyan-agent-platform` 的 `master`。检查开始时本地分支为 `adaptation-main`，HEAD 为 `369e236`；拉取后远端 `master` 为 `da80b0b`，是本地 HEAD 的祖先，本地已有12个后续提交。正常推送将同时包含这些既有提交和本轮新增提交，不重写远端历史、不合并其他分支。

## 审查与修正

- 核对三端边界及重点实现：HelloAgents真实导入、请求隔离、模型预算和取消、工具参数与引用校验；Java本人资源、快照判分及隐私清除；招生链接安全投影、院校目录快照、导出缓存与格式；前端账号切换、迟到响应和下载。
- 修正 README 架构说明链接；旧招生HTML／PDF模块和夹具已移除，历史文档改为文字路径，继续保留历史结论。
- CI增加监听 `master`，保留 `main`；搭建文档的运行版本与 README 对齐为Python3.13和Node22；环境示例补全默认关闭的学情开关及V13前置条件。
- CSV产物保留生成器的CRLF行尾；`.gitattributes`仅为CSV声明行尾空白检查规则，不改写原文件或来源摘要，其他尾部空白检查继续生效。
- 学情隔离链路首次因全页连续文本断言超时；画像新版已将标签和数值拆为卡片元素。脚本改为定位独立证据卡片并核对19条，重跑通过。
- 招生隔离链路首次使用“查询招生信息”，实际触发新增的院校库查询。脚本改为明确请求“招生官网链接”，并拒绝将 `schoolCatalog` 当作MCP结果，重跑通过。
- 对候选文本扫描模型密钥、GitHub令牌、云凭证、JWT、私钥和带凭证网址；新增命中仅为拒绝带凭证网址的合成测试，未发现真实凭证。`.env`、配置覆盖文件、数据库备份及缓存不提交。

## 实际验证

环境：macOS；Python3.13.15，项目已有 `.cache/mcp-pdf-venv`；HelloAgents0.2.8、OpenAI SDK1.109.1；Java25.0.4.1，编译目标17；Node22.23.3；系统Chrome的独立临时上下文。未更换依赖或使用日常浏览器资料。以下 `.cache/` 路径为本机证据，不随仓库公开。

| 检查 | 实际结果 | 本机证据 |
| --- | --- | --- |
| Python全量 | 947通过，65.68秒；2条依赖弃用提示 | `.cache/precommit-python-20261102.log` |
| Java verify及测试类路径 | 229项，0失败、0错误，2项默认跳过，BUILD SUCCESS | `.cache/precommit-java-20261102.log` |
| 独立Redis导出集成 | 启用 `KAOYAN_EXPORT_REDIS_TEST=true`，上述2项补跑全部通过 | `.cache/precommit-export-redis-20261102.log` |
| 脚本验证 | pytest 37项、unittest 8项通过；项目／框架检查和资料夹具预览通过 | `.cache/precommit-script-pytest-20261102.log`、`.cache/precommit-scripts-20261102.log` |
| 前端生产构建 | 通过；保留大于500kB的包体提示 | `.cache/precommit-frontend-20261102.log` |
| 桌面及390宽度浏览器回归 | 264通过，约4分钟；模拟API | `.cache/precommit-browser-20261102.log` |
| 通用HTTP与浏览器 | 15项通过，真实Java／Python、H2及Redis／模型替身 | `.cache/precommit-http-20261102.json` |
| 连续聊天／学情／题目检索 | 三组隔离链路通过 | `.cache/precommit-chain-chat-20261102.json`、`.cache/precommit-chain-learning-20261102.json`、`.cache/precommit-chain-questions-20261102.json` |
| 正式诊断及重启恢复 | 两种视口通过：20题、19答、1未答；草稿恢复、结束前不泄露判分、画像、规则推荐及已提交证据恢复 | `.cache/precommit-chain-learning-loop-fixed-20261102.json` |
| 招生官网链接MCP | 11项通过，包括真实stdio、两种视口、历史、跨账号404及Java重启恢复 | `.cache/precommit-chain-admission-fixed-20261102.json` |
| 题目管理 | 两种视口共10项通过 | `.cache/precommit-chain-question-admin-20261102.json` |
| 导出真实链路 | 独立H2／Redis／Java／Vue，两种视口共32次Word／PDF／Markdown下载通过 | `.cache/precommit-export-browser-20261102.json` |
| 正式练习MySQL | 全新随机端口MySQL实例，10项通过，不连接日常库 | `.cache/precommit-managed-mysql-20261102.json` |
| 院校目录MySQL | 6组通过，包括局部指标错误、目标年缺失、Python停止后查询、历史快照、两种视口及缺V14兼容 | `.cache/precommit-school-catalog-20261102.json` |
| 离线检索评测 | 仓库版本化夹具，lexical／BM25／hybrid分别10例全通过；未计算模型引用支持度 | `.cache/precommit-quality-lexical-20261102.json`等三份报告 |
| 依赖检查 | `pip check`无冲突；`npm audit`报告0项已知漏洞 | `.cache/precommit-npm-audit-20261102.json` |
| 差异及文档 | `git diff --check`、运行入口与当前文档链接检查通过 | 实际命令输出 |

## 公开范围与限制

新增忽略根目录 `360.JPG` 及 `outputs/collection-import-20261028/`、`outputs/collection-review-20261028/`、`outputs/collection-review-20261029/`、`outputs/collection-all-20261029/`。其中含明确限本机使用或缺少公开转载许可的采集正文、修订清单和截图；文件保留本机，不删除、不作为公开样本。历史文档改用本机路径描述这些证据。公开内容包含源码、测试、空采集模板、MIT许可课程题目及来源、公开院校事实与来源清单、OFL字体与许可、合成导出样本及说明。

验证没有调用真实付费模型，没有操作日常MySQL／Redis、用户学习记录、正式迁移或日常服务。真实模型及领域效果、公网部署、真实手机验收：未运行。依赖审计无已知漏洞不能替代完整安全审计；静态引用支持检查不能证明所有语义结论正确。GitHub Actions结果须在推送后独立核对，不用本地结果替代。
