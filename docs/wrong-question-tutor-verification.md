# 错题 AI 解释与追问验证记录

日期：2026-10-25。开发基线：main `ba37b82`。本记录属于本地开发验证，不表示已提交 PR、部署或真实模型验收。

## 实现与体验入口

答错反馈、已保存作答回顾、错题本提供“AI 解释与追问”。用户主动生成解释后可以继续提问；每轮保存为任务，刷新后在“Agent 助手”（`/tasks`）查看“错题 AI 辅导”并继续。手动标记但未作答、已答对、旧快照不完整的列表项不展示入口；后端独立校验，隐藏按钮不承担授权。

业务契约集中维护在[搭建文档7.4.1](../考研Agent平台搭建文档.md#741-错题解释与追问)。本功能复用现有 task、practice_record 表，无新增迁移，不修改 V1/V7/V8/V9，也不执行种子脚本。

## 已执行验证

| 检查 | 环境和结果 | 证据范围 |
| --- | --- | --- |
| Java `mvnw.cmd -o -B -ntp verify` | JDK17，72项测试，0失败/错误/跳过，BUILD SUCCESS | H2隔离库、Redis替身，含真实Java→Python HTTP调用，模型强制关闭 |
| Python pytest | 项目虚拟环境，83 passed | 真实FastAPI校验，模型替身、预算耗尽及无模型模式；未调用付费服务 |
| Vue生产构建 | TypeScript及Vite构建通过 | 存在现有大包体积提示，不影响构建 |
| Playwright浏览器回归 | Chrome，1280×900与390×844，64 passed | 全部页面回归；新增4种场景×2视口。业务API使用测试替身，独立浏览器上下文 |
| 差异检查 | `git diff --check` | 无空白错误 |

Java `AgentChainTest` 包含9项测试，其中新增3项验证辅导HTTP往返与任务持久化、跨账号/判分状态/快照边界、伪造输入/父任务边界。连续四次追问确认服务端消息窗口最多6条；即使现行题库没有对应题，也只使用历史快照。删除原作答后任务仍可读取，新提问404。`TaskServiceTest` 另覆盖模型篡改标准答案被拒绝、Agent异常脱敏与配额拒绝前不发远程请求。

Python新增15项测试覆盖默认不请求模型、不假称已回答个性化追问、授权选项及历史作为数据传递、标准答案不一致/模型异常/多余输出字段时降级、非法或缺少快照拒绝、缺少解析明确提示、超长解析输出有界，以及模型预算耗尽时不创建供应商客户端。模型替身对系统提示和用户载荷的断言只证明工程隔离，不证明真实模型不会受提示注入影响。

页面新增场景：答错后才显示且不自动调用、解释和两轮追问、刷新后从任务历史继续、纯文本转义、未答/答对/不完整快照不提供入口、429保留原解析并可重试、未启用AI明确提示、切换作答后丢弃迟到结果、Agent FAILED后原问题保留并可重试。截图由浏览器测试生成，位于被忽略的`kaoyan-frontend/test-results/`，内容为测试替身，不是真实AI成果图。

## 复现命令

从仓库根目录运行；JAVA_HOME指向JDK17，MAVEN_USER_HOME沿用已有缓存。不要加载或输出真实.env来运行这些测试。

```powershell
$env:PYTHON_EXECUTABLE=(Resolve-Path '.\.venv\Scripts\python.exe').Path
Push-Location kaoyan-B
.\mvnw.cmd -o -B -ntp verify
Pop-Location

$tutorTemp=Join-Path '.cache' ('tutor-pytest-'+[guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -X utf8 -m pytest -q kaoyan-agent/tests --basetemp $tutorTemp

Push-Location kaoyan-frontend
npm.cmd run build
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='C:\Program Files\Google\Chrome\Application\chrome.exe'
npm.cmd run test:e2e
Pop-Location
```

首次pytest尝试遇到系统临时目录权限问题，改用仓库内唯一的隔离临时目录后全套通过。首次新增浏览器用例的宽泛API拦截误拦Vite模块，修正为仅匹配`/api/`业务根路径后，全套64项通过。未通过的初始尝试不作为验收结果。

## 本地体验与未运行项（自动化验证结束时）

按README分别重新启动更新后的Java、Python和前端，再登录做错一道已审核单选题，点击“AI 解释与追问”。已有业务库仍需具备前一版本要求的V7/V8/V9，不要重跑已执行迁移。本次未操作日常MySQL、未导入题库、未替用户启动或停止日常服务。

保持LLM_ENABLED=false时只能体验原解析和降级界面。真实个性化解释需由配置负责人在本机安全填写已有LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_MAIN并显式启用LLM_ENABLED，再重启Python；密钥不能发到聊天、截图或Git。该配置会产生模型调用，应由负责人根据团队选定供应商及费用范围启用。本次没有修改.env或进行真实模型调用。

尚未运行：真实MySQL三端联调、供应商真实调用、数学公式/复杂题目的讲解质量评估、教师内容审校、多人压力或公网验收。当前仅支持完整四选项、已提交有效错答快照的辅导；不支持未答题提示、主观题重新判分、完整知识库辅导引用或跨题长期记忆。旧快照缺失时不会伪造补全；模型解释也不能证明标准答案或原解析一定无误。

## 后续 DeepSeek 官方 V4.1 Flash 适配

用户确认使用 DeepSeek 官方 API 并持有 API Key。2026-10-25读取官方接入、模型说明、思考模式及JSON输出文档，核对当前标识`deepseek-flash`由V4.1-Flash-1017提供，地址`https://api.deepseek.com`。官方默认启用思考模式，本项目对该主机和模型显式发送`thinking:{type:"disabled"}`，继续使用原有JSON结构输出与超时；其他供应商不收到此参数。配置和依据链接见README及搭建文档。

新增6项使用httpx.MockTransport的真实SDK序列化测试，核对官方根地址及/v1地址、路由模型选择、相似恶意主机及第三方平台不接收专属参数，并检查JSON模式、消息角色和输出token上限。Python全套重跑 **89 passed**；未联系供应商推理接口，不代表API Key可用或真实解释正确。

本机已有.env仅更新4个非密钥项：官方地址、两个模型名及LLM_ENABLED=false；API Key、数据库和内部凭证保持原值，未输出凭证。由用户在本机填入官方Key并显式启用后重启Agent，真实模型调用及三端体验仍待验收。.env不作为提交内容。

## 用户本地手动联调补充（2026-10-25）

以下证据由用户实际操作和提供截图产生，范围区别于前述自动化测试。用户启动WSL MySQL及Redis，Windows侧3306/6379端口检测通过；Java启动截图显示8080已监听且Hikari连接池成功连接MySQL。Agent健康检查返回status=ok、modelEnabled=true；此前已配置DeepSeek官方地址与deepseek-flash，Key由用户本机填写。

用户在本地录入、审核一道栈操作自编示例。首次题目标准答案误填A、解析为C，截图中AI指出矛盾但未改写Java判分。随后用户重新准备正确题目，截图显示：选择A（2）、Java判错并返回标准答案C（8）；AI解释模式为ai，逐步列出[2]→[2,5]→[2]→[2,8]→弹出8，与本题推演相符。该轮任务编号为761b3097-5cdc-4ab2-81b9-ce6be659efba。

本次可确认的手动结果：一道自编题在用户本地完成录入审核、作答判分、已保存作答依据展示，以及一次模型解释返回。未读取用户任务或业务库来补充截图以外的内容，也未通过账单或供应商响应元信息独立核查实际服务模型版本。该样例不代表完整题库、所有错误选项或模型讲解质量验收。连续追问、刷新后的历史恢复仍待用户下一步验证；公式复杂题、多人压力和线上部署验收仍未完成。
