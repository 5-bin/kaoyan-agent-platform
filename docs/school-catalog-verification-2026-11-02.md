# 院校库查询与详情加载验证（2026-11-02）

本文 `.cache/` 下的日志与截图仅供本机追溯，不随公开仓库分发。

## 实现及边界

本轮按[院校查询契约](../考研Agent平台搭建文档.md#院校库查询与局部加载契约2026-11-02)增加确定性 `SCHOOL_LOOKUP`。Java先识别本轮查询、独立核对学校与筛选条件，读取业务库并保存白名单 `schoolCatalog` 快照；Python提供兼容的类型化计划及拒绝非法计划，不读取数据库。模型不能生成此动作，模型Schema不携带Java专用查询字段，避免挤占现有解析输入预算。

年份按本轮明确年份、本人档案报考年、库内最新年选择；不会继承历史会话的专业筛选。目标年缺失时保留目标年并列出已有年份。专业按年份降序、专业代码和ID升序，最多10条，保留总数量与完整详情入口。资料原备注、官方／第三方状态、年份和共享计划口径不改写；资料不会因展示进入审核RAG或推荐集合。仅链接请求仍使用原MCP，新查询从Java登记清单附确认链接，二者没有静默切换或官网抓取。

详情接口增加可选warnings。指标按条校验，非法指标隐藏，同时清空该响应中对应旧值，防止展示回退误用；不修改数据库旧值。口径冲突隐藏该专业指标，其他专业继续显示。读取按当前专业ID批量查询，取消每次列举整库表元数据；仅明确“表不存在”兼容V14未安装，其他SQL／连接失败继续报错。前端区分加载、空数据、404、失败和超时，15秒解除等待后可重试；切校和离页取消旧请求。

新查询正文不再被通用链接提示覆盖。库内专业卡片位于确认链接前；学校未入库或同名有歧义时school为null，保留缺口说明，不渲染虚构详情；已有登记链接仍可确认。旧招生核验历史继续隐藏旧核验正文。导出从本次已保存快照生成，三个格式均保留核验状态、年份及口径。

## 原问题复现

只使用现有公开导入清单回放四川大学及北京大学的30条专业、60条指标。隔离环境由全新MySQL 8.4临时目录、随机回环端口、Java测试启动器、禁用模型的Python及独立Chrome组成，不连接日常MySQL／Redis、不读取个人学习记录。Redis在Java隔离启动器中为替身，不代表真实Redis验收。

- 修改前编译产物：`GET /api/schools/11`返回200，约34毫秒。
- 修改后：同一公开清单回放返回200，约31毫秒；不将此小差异解释为性能提升。
- 原截图持续加载没有在本次环境复现，不能据此断言由数据库、指标内容或Vite缓存导致。本轮确认并修复的是无效指标拖垮详情的路径、前端失败恢复和只显示链接的路径；日常旧进程尚未加载新版。

基线证据：报告（本机 `.cache/school-catalog-baseline-20261102b.json`）。最终证据：完整报告（本机 `.cache/school-catalog-final-20261102.json`）、桌面详情（本机 `.cache/school-catalog-final-20261102/desktop-school-11.png`）、移动聊天（本机 `.cache/school-catalog-final-20261102/mobile-catalog-chat.png`）。这些截图使用公开资料与合成账号，隔离备注明确标为回放。

## 实际验证

| 项目 | 实际命令／入口 | 结果与范围 |
| --- | --- | --- |
| Python全量 | `.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests` | 808通过；含121校本地查询、明确筛选、链接路由、非法计划及零模型请求。既有SDK／MCP测试保留隔离替身或stdio范围 |
| Java全量 | 在kaoyan-B设置`PYTHON_EXECUTABLE`为本项目`.cache/mcp-pdf-venv/bin/python`，运行`bash ./mvnw -B -ntp verify` | 221项中219通过、2项按既有真实Redis开关跳过；源码与测试编译、打包通过。使用bash因仓库mvnw当前无可执行权限，不修改其权限 |
| 生产构建 | 在kaoyan-frontend运行`npm run build` | 通过；保留原有大chunk提醒 |
| 浏览器定向回归 | `npx playwright test tests/school-detail-loading.spec.ts tests/school-metrics.spec.ts tests/admission.spec.ts`，指定独立Chrome可执行路径 | 桌面／390宽度共38通过：真实15秒XHR超时、失败重试、404、空专业、快速切校、核验标注、库内信息先于链接、已登记但未入库、刷新及旧历史安全展示。使用模拟API与生产预览 |
| MySQL及真实页面 | `.cache/mcp-pdf-venv/bin/python scripts/smoke-school-catalog.py --browser --output .cache/school-catalog-final-20261102.json` | 真实MySQL／Java／Vue链路通过，含401、404、损坏JSON指标局部隔离、档案年份、目标年无数据、Python停止后仍可查询、快照不随更新变化、缺V14兼容；桌面和移动视口截图完成 |
| 三格式导出 | Java `ExportSourcesAdmissionTest.savedCatalogSnapshotPrecedesLinksAndSurvivesEveryExportFormat` | 实际生成并提取DOCX／PDF／Markdown文本，核对2027年77人、2026年310分、第三方待核实、共享口径和信息顺序。数字为合成测试值，不是招生事实；产物位于`kaoyan-B/target/export-samples/school-catalog.*` |

MySQL和Chrome在沙箱内受系统权限限制，使用获准的隔离执行完成上述检查；只回收本次启动的服务与临时目录，不操作日常进程。实际测试日志：Python（本机 `.cache/school-lookup-python-final.log`）、Java（本机 `.cache/school-lookup-java-final3.log`）、浏览器（本机 `.cache/school-lookup-browser-final2.log`）。

## 未运行与剩余限制

未运行：真实付费模型、官网内容抓取、日常账号／数据库检查、日常服务重启、公网部署。未新增迁移、提交或发布。移动端为Chrome视口模拟，不代表实机验收。完整院校详情仍为可横向滚动表格；聊天只显示前10条，更多记录通过院校详情查看。

本轮不处理原学情降级、短回答“学硕”的追问续接，也不将原有相关修改归为本轮成果。院校入库资料的准确性仍取决于已有来源和核验状态；展示不代表已审核全部招生事实。
