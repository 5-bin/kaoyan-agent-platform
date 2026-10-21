# Issue #9：刷题答案安全与历史展示验证

日期：2026-10-21。分支：`feat/practice-answer-safety`，开发基线：`64c24ce`。
关联：[Issue #9](https://github.com/5-bin/kaoyan-agent-platform/issues/9)。本文记录本地实现和隔离验证，不代表已提交、推送、合并或部署。

## 接口与依赖

详细规则统一维护在[搭建文档第7节](../考研Agent平台搭建文档.md#contracts)。路径、数字题目ID和`{code,message,data}`包装保持兼容；前后端须一同发布。

| 入口 | 本次行为 |
| --- | --- |
| 学生抽题、题目详情 | 使用StudentQuestionVO，只含公开题干、选项和分类；不返回答案、解析及审核信息，详情限定启用且已审核题目 |
| 批次详情 | 返回PracticeRecordVO，隐藏原始questionSnapshot及userId |
| 作答提交 | data由null改为questionId、userAnswer、isCorrect、answer、analysis；页面使用Java结果，失败时不显示解析 |
| 批次回顾 | 未答不显示答案；已答只读对应作答快照，题目修改或删除后仍保留当时依据 |
| 收藏、错题列表 | 取本人该题最新有效已提交作答；手动标记不授予答案权限，不混用其他账号记录 |
| AI总结 | 本地快照增加选项、难度；发给Python时只投影既有字段，不改变内部模型契约 |

展示新增snapshotStatus，区分NOT_ANSWERED、AVAILABLE、PARTIAL、MISSING、UNAVAILABLE。旧快照缺少选项时仅展示已保存字段；缺失历史依据时不查询现行题目补造答案。

依赖现行JWT、题目审核启用状态及V7的question_snapshot列。本次不新增数据库脚本，不执行迁移，未改公共认证或Python协议。

## 原PR实现时的自动检查

环境：Windows PowerShell，JDK17，Maven Wrapper，仓库根目录独立Python虚拟环境，Node/npm及本机Chrome。

| 检查 | 命令与结果 | 实际边界 |
| --- | --- | --- |
| Java | 在kaoyan-B运行`mvnw.cmd -B -ntp verify`：51项通过，0失败、0错误、0跳过，打包成功 | H2隔离库、MockMvc真实安全链和Service，Redis替身；不是MySQL并发验收 |
| 前端 | 在kaoyan-frontend运行`npm.cmd run build`：通过 | TypeScript检查与生产构建；现有大包提示仍存在 |
| 页面 | 设置PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH后运行`npm.cmd run test:e2e`：16项通过 | 8案例×桌面/手机视口；API响应替身，非完整三端页面联调，非实机手机 |
| Java→Python | AgentChainTest真实启动临时端口Python服务，含扩展快照总结 | LLM_ENABLED=false、离线词项检索；未调用付费模型 |
| 差异 | `git diff --check`：通过 | 不替代代码审查 |

新增PracticeAnswerSafetyTest覆盖6组集成场景：所有未答学生入口字段隐藏；本人历史改题/删题后保留及账号隔离；非法/重复/跨账号提交不累计；空快照/部分旧快照/最新快照缺失不回退；同一作答并发只成功一次；扩展快照投影保持Python字段集。

新增页面案例验证失败提交无答案、成功使用服务器结果、未答和缺失快照提示、12题跨分页计数不变，以及收藏/错题只展示允许内容。检查桌面与手机回顾截图，调整手机标签和按钮换行。首次新增测试误拦截Vite的src/api模块，已将拦截限定为站点的/api路径后重跑。

## 审查人复现步骤

以下手动步骤应在独立测试环境进行，本次没有操作日常业务数据库。

1. 准备已审核启用单选题，以学生A创建批次。检查抽题、详情、批次详情、回顾响应，未答时不得包含answer、analysis、questionSnapshot。
2. 未答时手动收藏或加入错题本，列表只显示公开内容及尚无有效作答提示。学生B的操作不得获得A的历史答案。
3. 提交非法选项，预期400，页面不显示反馈解析。提交有效选项，预期200且返回Java判分；记录和统计只更新一次。再次提交同一题，预期409；其他账号向该批次提交，预期404。
4. 提交部分题目后查看已保存作答，未答显示“未作答”，不显示“答错”。12题批次加载10条后再加载剩余2条，计数保持不变，序号继续到12。
5. 在隔离测试库修改已答题的现行题干、选项、答案；原批次回顾、本人收藏和错题仍显示当时快照内容。
6. 对隔离测试记录模拟旧快照为NULL或空对象，回顾提示历史快照缺失且不返回答案；旧快照仅缺选项则提示不完整，不拼接新题选项。

## PR #10审查修复与重新验证（2026-10-21）

在独立本地检出目录以`1bf60bc`为基线修复三个页面问题，未改Java／Python业务实现、接口或数据库。修复用于补充[PR #10](https://github.com/5-bin/kaoyan-agent-platform/pull/10)，合并与部署另行执行。页面规则见[搭建文档第4.4节](../考研Agent平台搭建文档.md#features)。

- 不可用题目提示后自动跳过；首次加载、下一题和继续作答共用顺序导航。网络／超时／500错误保留重试，不把请求失败当作撤回。
- 提交404／409先查询本人记录；已提交则同步服务器历史，确认题目失效才跳过，配置冲突不跳过，不自动重放作答。
- 旧快照没有选项时，独立显示已保存的标准答案和本人选择；回顾可继续作答，加载失败保留原视图。
- 跳过只改变页面导航，不更新判分或统计。有效未答记录仍存在时展示“暂无可继续作答的题目”，禁用AI总结；不将其视为正式结束批次。

本次环境：macOS、JDK25.0.4.1（编译目标17）、Python3.13.15、Node22.23.3、Chrome隔离上下文。Java复用本机已有Maven缓存和Python运行时，不复制日常环境或业务数据。

| 检查 | 本次实际结果 | 边界与证据 |
| --- | --- | --- |
| Java | `bash mvnw -B -ntp -o -Dmaven.repo.local=<已有缓存路径> verify dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt`：51项通过，0失败、0错误、0跳过，打包成功 | 设置`PYTHON_EXECUTABLE`为已有虚拟环境Python；H2／Redis替身，包含Java→Python真实子进程及答案安全、快照与并发测试 |
| 前端构建 | `npm run build`通过 | TypeScript与生产构建；已有大包提示仍存在 |
| 浏览器回归 | 设置`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`后`npm run test:e2e`：42项通过 | 21案例×桌面1280／手机宽度390；API替身。新增`practice-recovery.spec.ts`的13案例覆盖三项修复、首题／中间／全部不可用、恢复后重查、网络／超时／500、提交404／409、重复提交同步、配置冲突及失败视图保留 |
| 实际Java页面 | 本地独立检查6项通过：两个宽度分别检查旧快照、不可用题目及回顾后提交 | Vite生产预览→真实Java→临时H2，Redis替身，无API拦截；验证实际404、答案隐藏、Java判分及记录保存，未调用模型。报告`.cache/pr10-real-practice.json`及两个宽度截图，仅本地保留 |
| 文档与差异 | `scripts/check-project.py`、`scripts/check-framework.py`和`git diff --check`均通过 | 静态文档、契约入口和差异检查，不替代业务或真实环境验收 |

实际后端检查使用本地诊断入口`.cache/pr10-repair-check.py`及`.cache/pr10-repair-browser.cjs`，执行后关闭本次Java、Vite和Chrome；临时库自动清理。诊断入口和报告不随源码提交。已检查390宽度截图与页面溢出，属于模拟手机宽度，不是实机验证。

新增回归用例可通过`npx playwright test tests/practice-recovery.spec.ts`单独复现；完整测试同时覆盖原有未答隐藏、服务器判分、跨页计数、收藏／错题和推荐页检查。复现旧快照时不请求现行题目；自动跳过和失败检查确认未提交题目的`isCorrect`保持NULL。

## 尚未覆盖

抽题时固定完整题目版本、持久草稿、正式批次结束与重放语义、不同题目并发统计、删除批次后的聚合一致性，以及完整题目审核发布/迁移仍需后续任务。当前判分保存的是提交时题目快照，不能声称已实现抽题时锁定版本。

未运行真实MySQL/Redis环境联调、正式数据库迁移、真实模型、外网部署及备份恢复；没有扩充真题库。原有backend/data及docs/验证输出中的本地数据保留，不应随本次提交暂存。
