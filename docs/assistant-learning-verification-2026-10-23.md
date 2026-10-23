# 学情助手与隐私改造验证记录

日期：2026-10-23。目标工程：`kaoyan-agent-platform-adaptation`。本轮保留既有工作区修改，由主agent集成Java隐私与生命周期，协作agent分别完成Java业务工具、Python流程和前端交互，并交叉审查。未读取真实用户记录、密钥或浏览器资料，未提交、推送或发布。

## 实际改动

- 新增“计划解析→Java业务读取→Python分析→Java校验与操作”链路。通过本人有效作答快照、收藏、统计及已发布资料生成可核对的学习依据；公开408语料仍使用现有检索器和来源校验。
- 错题、收藏、统计、资料和练习页使用共享聊天侧栏；单题明确收藏直接执行，其余操作先预览题目及实际数量再确认。新增未答练习立即进入批次列表，刷新不重复创建。
- 新批次创建时固定题目快照；判分采用该版本，撤回题目禁止继续提交，未答DTO不返回标准答案和解析。旧缺失快照不按现行题目补造。
- 分类外发授权默认关闭，绑定当前安全接收端点；模型仅接触必要字段和本轮引用。撤回授权阻断后续调用并取消在途聊天；未授权时使用本地规则。
- 历史引用和派生回答继承隐私类别；历史正文不复制进新上下文，展开检索词不额外持久化。单会话／全部清除和30天清理覆盖聊天、草稿、生成及task副本，包括已隐藏推荐。原始作答、标记、个人文档与额度元数据独立保留。
- 任务公开接口改为白名单DTO；异常和校验不回显正文，关闭自动内容追踪，Markdown外链只允许本轮来源精确URL，不加载远程图片。

详细接口及兼容方式见[学情助手契约](assistant-learning-contract.md)。

## 已运行验证

| 验证 | 命令／入口 | 实际结果与边界 |
| --- | --- | --- |
| Java全量 | `kaoyan-B` 下 `bash mvnw -B -ntp verify`，`PYTHON_EXECUTABLE`指定项目隔离环境 | 82项通过；JDK25运行、编译目标17。使用独立H2及Redis／模型替身，含真实Java→FastAPI→LangChain→SDK受控传输 |
| Python全量 | `.cache/chat-venv/bin/python -m pytest -q kaoyan-agent/tests` | 126项通过；Python3.13。覆盖分类授权、端点绑定、隐私历史、混合数据最小化、禁追踪、来源校验和独立408案例；1条既有AnyIO弃用警告 |
| 前端构建 | `kaoyan-frontend` 下 `npm run build` | 通过；保留既有大资源块提示 |
| 前端关键回归 | Playwright执行 `assistant-learning.spec.ts`、`conversation.spec.ts`、`assistant-ui.spec.ts` | 最终22项桌面／390px模拟手机检查通过，使用合成API。更早阶段全套76项及新增直接收藏回归也已通过；不以模拟API代替实际后端验收 |
| 真实页面学情链路 | `scripts/smoke-chat.py --learning --output <新的报告路径>` | 17项通过。实际Vue生产构建、Java、Python和浏览器；临时文件H2、Redis及供应商替身，不拦截浏览器业务API；1280／390宽度各独立账号，结束仅关闭测试自身进程 |
| 增量迁移 | `scripts/check-chat-migrations.py --output <新的报告路径>` | 临时MySQL8.4.11禁用网络、独立数据目录，11项通过；覆盖V10—V12、原记录保留、唯一约束及授权默认关闭 |
| 文档／静态检查 | `scripts/check-project.py`、`scripts/check-framework.py`、`git diff --check`及新增脚本语法检查 | 通过；不代表部署或完整领域内容效果验收 |

实际页面链路覆盖：默认拒绝外发→错误作答进入错题→助手直接收藏→预览错题练习且确认前不创建→确认后实际仅1题→刷新与查询无重复→助手读取真实统计并提示小样本→读取已发布资料正文→隐私UI分类授权及撤回→清除聊天且原始作答、收藏和批次仍存在→真实Java进程重启保留会话并将中断生成标失败。

隐私回归另外检查：跨账号查询、生成中撤回、并发确认、目标变化409、过期读取清理、清除与同步任务并发时不能恢复私有副本、已隐藏推荐过期擦除、历史派生类别撤回、模型替身请求不含真实业务主键和未授权资料。

## 本地输出与修复过程

- Java输出：`kaoyan-B/target/assistant-verify-delivery.log`；Python输出：`.cache/assistant-python-verification-20261023.log`。
- 实际学情页面报告：`.cache/assistant-learning-browser-delivery-20261023.json`；初次完整通过报告为`.cache/assistant-learning-browser-20261023.json`。
- 迁移报告：`.cache/assistant-mysql-migrations-20261023.json`；前端关键回归日志：`kaoyan-frontend/.cache/assistant-learning-delivery-regression.log`。这些为本地构建／缓存证据，不作为待提交源码。
- 沙箱内Chrome启动SIGABRT、MySQL初始化权限失败后，在已授权的独立临时环境重跑；没有连接日常数据库或读取日常浏览器资料。
- 实际页面检查先发现新建未答批次被`HAVING MAX(answered_at) IS NOT NULL`隐藏，修复查询并增加回归；随后发现资料弹窗关闭后被恢复操作记录的刷新重新打开，修复关闭时清理路由参数并保留所选资料上下文，补充回归。未将这些失败轮次计作通过。
- 已人工查看合成数据的桌面及模拟手机截图；最后修正窄屏标题折行和证据中的内部状态用语。

## 运行与未验证范围

新版Java启动前，在已有V11基础上备份并核对后，受控执行一次[V12迁移](../kaoyan-B/src/main/resources/db/V12__assistant_privacy.sql)。本次**未操作日常数据库、未重启日常服务**；V1含删除语句，不能重跑V1升级。旧客户端不带pageContext仍可提交聊天，未授权隐私字段默认禁止外发；新公开任务响应不再包含inputPayload。

真实模型供应商费用调用、真实模型学情解释质量、真实Redis、日常MySQL升级、JDK17运行时、真实手机设备、公网部署和独立备份删除流程均**未运行**。合成案例和模拟手机宽度不能证明真实学习效果。仅完成在线系统管理范围内的清除，不能承诺撤回已经发送给模型服务方或单独备份中的数据。

最终截图位于本地`.cache/learning-browser-1792722301220504000/`；已人工复核`learning-actions-1280.png`与`learning-actions-390.png`，手机标题保持横排，操作目标及实际题量可见。该目录仅含合成测试数据，不代表真实学生记录。
