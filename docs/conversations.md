# 连续聊天与个人学习文档契约

2026-10-23学情助手增量以[学情与隐私契约](assistant-learning-contract.md)为准：新增页面上下文、受控读写、分类外发授权、V12与30天清除；本页其余内容保留连续聊天和文档基础协议。历史明文改为引用加载，task不再重复存聊天上下文，任务响应使用白名单DTO。

## 会话列表删除

桌面侧栏与手机会话抽屉共用会话行，每行右侧常驻删除按钮，标题保持单行省略。点击删除不切换会话，确认文案为“删除此对话？聊天记录将被清除，无法恢复；已保存的个人笔记不受影响。”，操作为取消／删除。请求期间禁止重复删除，失败保留列表、聊天与输入。

复用`DELETE /api/conversations/{id}`，无新增接口、字段或迁移。Java校验本人归属，跨账号404；现有清除流程停止生成、清除会话消息及操作上下文、隐藏相关任务并保留额度记录，已保存个人笔记独立保留。

删除其他会话保留当前聊天和输入；删除当前会话清理输入、引用、临时结果及订阅，切换至已加载列表第一条剩余会话。删除最后一条显示空聊天并移除URL旧会话编号，发送时才创建会话；若分页刷新发现剩余会话则选中第一条。成功后从第一页刷新列表与总数，废弃删除前的列表／分页请求，并隔离旧会话及旧账号的迟到响应。仅支持单条删除，无回收站和恢复功能。

## 实现与职责

`/tasks` 为Agent助手，`/tasks/history`只读旧任务。旧独立任务不迁移为会话。前端只调用Java；Python仅接收Java从认证上下文组装的资料、最近3轮有效历史和当前文档快照，不连接业务数据库。

Python使用LangChain提示模板、Runnable分支、ChatOpenAI及白名单工具实现固定流程：上下文解析 → 知识检索／确定性院校筛选／文档建议 → 结果校验。保留词项／FastEmbed＋Qdrant检索及资料版本，不新增任意SQL、网络、文件或命令工具。LangGraph随LangChain作为依赖安装，本版不建立第二套持久会话或自主循环。

一次聊天最多一次解析、一次内容生成；显式旧工作流保持原入口。所有实际模型请求分别消耗原模型预算，SDK与框架均不自动重试。Python全流程42秒，Java后台48秒保护；客户端订阅65秒超时、10秒心跳，前端25秒无数据重连。停止及失败计入Java原每日／分钟任务配额，读取、确认文档和重连不计模型次数。现有Python每日模型预算仍为单进程内存计数，重启会重置，不是账单硬限额。

模型关闭时直接返回资料摘要或确定性候选；不会将完整文本拆字伪装模型流。指代不明和条件矛盾追问；AI文档生成明确不可用，手动文档功能仍可使用。

## 助手界面展示

个人文档的用户界面统一称“个人笔记”，在左侧“复习”分组通过`/notes`管理；支持手动创建、编辑预览、差异和分页历史版本。聊天保留笔记选择与建议预览，管理入口跳转笔记页。笔记页“让助手修改”显式选择该份笔记，发送时Java核对其归属和版本；不自动选择其他笔记。旧API、已保存笔记和版本继续兼容。

会话历史使用44px等高单行条目，超长标题省略，悬停及无障碍名称保留完整标题；桌面侧栏和移动抽屉均标识当前会话。回答保留各次生成记录，但不显示尝试序号、任务编号、内部发布版本、成功标签或生成方式标签。需补充条件、资料未覆盖、生成失败／停止和解释降级仍有提示；来源定位与版本、招生年份及个人文档历史版本继续展示。以上仅影响展示，不改变接口字段、流版本校验或保存行为。

## 数据与迁移

部署前依次对已有V9数据库执行一次`V10__chat_conversation.sql`、`V11__personal_document.sql`、`V12__assistant_privacy.sql`。迁移为增量建表，不执行V1、不清空旧任务；尚未引入自动迁移。

- `chat_conversation`：归属、首问标题、初始档案快照、当前条件与消息序号。
- `chat_message`：用户问题、顺序及所选文档编号；每个问题有多个生成尝试。
- `chat_generation`：一条生成对应一条原`task`，保存请求编号、内容指纹、上下文、状态、增量草稿、版本和正式结果。
- `personal_document`与`personal_document_version`：本人Markdown文档与不可变历史版本，独立于公共审核资料。

状态为`RUNNING / SUCCESS / FAILED / CANCELLED`。任务与生成在短事务中预占，调用模型期间不持有数据库事务。数据库唯一约束限制同一会话一个活动生成，以及请求编号、消息顺序和尝试序号唯一。任务配额预占锁定账号行，和原任务入口共用持久计数。

生成过程约每500毫秒保存草稿，最后一个未保存片段可能在进程崩溃时丢失；正式结果、失败或取消必须立即保存。进程启动将遗留生成改为中断失败并清除活动占用和临时答案。完成与取消仅一个终态生效。

## 对外接口

普通接口保持`{code,message,data}`，分页从1开始，默认20、上限100。私有资源均校验当前账号，跨账号返回404。

| 方法与路径 | 请求／结果 |
| --- | --- |
| `POST /api/conversations` | 从本人档案创建会话；返回id、title、conditions |
| `GET /api/conversations` | pageNum/pageSize；按更新时间分页 |
| `GET /api/conversations/{id}/messages` | 按问题序号倒序分页，返回conversation、list、total；每条含全部attempts |
| `POST /api/conversations/{id}/messages` | query、clientRequestId，可选documentId与documentVersion；立即返回messageId/taskId |
| `GET /api/conversations/{id}/generations/{taskId}/stream` | Bearer认证的SSE订阅 |
| `POST /api/conversations/{id}/generations/{taskId}/cancel` | 显式停止；重复调用返回当前终态 |
| `POST /api/conversations/{id}/messages/{messageId}/retry` | clientRequestId；仅最后一问且上次FAILED/CANCELLED可创建新尝试 |
| `POST /api/conversations/{id}/generations/{taskId}/apply-document` | 可选title/content人工调整；幂等确认文档建议 |

问题1—8000字符；请求编号1—64位ASCII字母、数字、下划线或连字符。同一会话相同请求编号和内容返回原尝试；不同内容409。生成中提交其他问题409。重试使用新的请求编号，保留原尝试。浏览器发送未确认时保留原编号，避免网络重试重复生成。

文档接口为`/api/personal-documents`的POST和分页GET、`/{id}`的GET/PUT、`/{id}/versions`的分页GET以及`/{id}/versions/{version}`的精确版本GET。创建／更新使用title、content，更新必须传baseVersion。标题1—100字符，正文最多40000字符；版本过期409。首版不提供删除、共享、公开发布或Word/PDF导入导出。

## 内部上下文与流事件

保留`POST /internal/rag/chat`同步接口。新增`POST /internal/rag/conversation/stream`，继续使用`X-Internal-Key`，请求继承现有字段，增加conditions和可选document快照。

conditions仅允许examYear、majorCodes、degreeType、regions、regionConstraint、studyMode、examSubjects、explainWithAi。新会话从档案取初始年份和可识别专业，聊天条件仅影响本会话。Python提取的补丁重新校验；正式结果保存时Java再次校验并更新会话条件，不更新个人档案。

模型历史由Java读取最近3轮SUCCESS且已校验结果，不接受浏览器伪造历史。每条超过3900字符追加明确节选标记；完整内容仍保存在数据库。失败、取消、临时文本和更早轮次不传给本轮。指代改写后的standaloneQuery重新检索，历史助手文本不替代新证据。

内部流发送stage、delta、result、error；Java消费后转换为对外事件：

| SSE事件 | 内容 |
| --- | --- |
| snapshot | taskId、messageId、attemptNo、status、version、stage、draft、result、errorMessage |
| stage | taskId、version、stage |
| delta | taskId、version、slot、offset、text；slot仅answer/content/summary/candidate.0—4 |
| completed / failed / cancelled | 完整终态快照，draft清空 |

offset按Unicode码点计数，version单调增加。每次订阅先发送完整快照；快照和后续订阅注册在同一进程锁内完成。客户端忽略旧版本，版本或位置不连续则重新获取快照。后端仅依赖已落库生成，不因订阅、刷新或重连再次调用模型。

模型JSON通过真实SDK流输入，增量解析只展示允许的正文投影。完整结果经Schema、候选、引用编号及来源校验后，Java落库成功才发送completed。来源链接限定HTTPS和当前审核语料的来源域名；新增资料域名时需同步Java校验与前端链接白名单。Markdown禁用原始HTML、清洗渲染，禁用远程图片。

## 文档建议与确认

文档生成结果保留resolvedTaskType=CHAT，使用operation标识DOCUMENT_CREATE/DOCUMENT_UPDATE，documentProposal包含operation=create/update、documentId、baseVersion、title和content。创建建议不含目标编号和基础版本；修改建议只能指向本轮授权文档快照。

建议生成不会修改正式文档。前端提供Markdown预览、修改差异与人工调整；点击确认后Java校验归属、成功任务和基础版本，再保存不可变新版本。确认按source_task_id唯一，重复点击返回同次保存版本；即使后来人工修改，也不重放旧建议覆盖当前内容。发生409时需重新读取并核对，不能自动覆盖。

个人笔记是用户上下文，不自动成为审核资料，不自动加入公共Qdrant或招生事实来源。账号切换、退出和页面离开关闭订阅并丢弃旧响应；不把断开订阅当作取消生成。

## 验证入口

现有Python测试、Java verify和前端build仍为基础检查。新增：

```bash
python scripts/check-chat-migrations.py --output .cache/新迁移报告.json
python scripts/smoke-chat.py --output .cache/新聊天链路报告.json
python scripts/smoke-chat.py --skip-browser --timeout-check --output .cache/新超时报告.json
```

前者只启动临时数据目录、禁用网络的独立MySQL；后者使用随机端口、文件H2、Redis替身、真实FastAPI／LangChain／SDK和受控模型供应商。后者要求已构建前端、Java测试类及`target/test-classpath.txt`，浏览器可通过PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH指定Edge。脚本只清理自身启动的进程，拒绝覆盖已有报告。

验证结果及未运行范围见[聊天验证记录](chat-verification-2026-10-22.md)。实际供应商、日常数据库升级、现有服务重启和公网发布均须另按授权执行。

### 2026-10-23 助手界面精简验证

- `kaoyan-frontend` 下执行 `npm run build` 通过；构建仍有大体积资源块提示。
- Chrome / Playwright 在1280×900与390×844两种视口下共20项通过，覆盖 `tests/assistant-ui.spec.ts`、`tests/conversation.spec.ts` 和 `tests/recommendation.spec.ts`。检查标题44px等高、省略与完整名称、移动抽屉选中状态、失败／停止记录、重试／重连、来源保留、必要状态提示，以及推荐和任务历史共享结果展示。
- 首轮浏览器在沙箱内无法启动；改用隔离浏览器后发现原5173服务已无法连接。最终使用临时 `.cache/assistant-ui-built.config.ts`，通过浏览器请求拦截直接加载本次 `dist` 并模拟API，未启动或停止应用服务，未访问日常数据库，未调用真实模型。这是生产构建的模拟接口浏览器验证，不代表实际后端或真实设备验收。
- 最终截图与输出位于 `kaoyan-frontend/.cache/assistant-ui-results-20261023-final/`；已人工查看桌面标题、移动抽屉及回答展示截图。实际后端联调、真实手机和公网检查未运行。
