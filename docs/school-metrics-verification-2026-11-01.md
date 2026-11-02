# 院校招生指标实施与验证（2026-11-01）

代码、来源清单和隔离预演已完成。用户对精确影响清单回复“确认按清单写入数据库”后，**已在本机`kaoyan_dev`执行V14及正式导入；后续按用户要求重启三端并加载新版Java**。确认清单SHA-256为`7c7a735a784174013e42ddb61f38a5b8bc2280035bd02c2d75b4a659367d78ec`，与[清单](../outputs/school-enrichment-20261101/final/preview.md)及[正式执行摘要](../outputs/school-enrichment-20261101/final/application.json)一致。19:01的[日常库回读](../outputs/school-enrichment-20261101/final/daily-readback.json)确认121校层次无缺失、1594项指标全部存在。

## 查证结果

覆盖121所学校、797条2027专业记录；合并原Excel的782条映射及原15条专业资料。121校均完成计划、参考线两类公开检索，另有追加检索及官网页面取证。原始收据保留在本机`.cache/school-enrichment-20261101/`；不从检索摘要推定数字。整理105条有来源的数值观察，按学院、代码、学习方式、类别和方向精确匹配。

| 结论 | 2027计划 | 往年复试线 |
| --- | ---: | ---: |
| 官方数值 | 54 | 146 |
| 第三方待核实 | 12 | 55 |
| 范围不匹配，数值空 | 8 | 104 |
| 未找到可靠来源，数值空 | 723 | 492 |
| 合计 | 797 | 797 |

按专业记录计数，共用计划不累计为多份名额。大量缺口仍存在，检索未找到不等于未公布，更不代表全国数据完备。图片、不可读附件、专业拆分或更名依据不足时未估算。无明确公告时不标“未公布”；官方来源不代表完成招生部门或小组人工审核。未公布、冲突等状态通过合成测试，本次真实清单没有这两类结论。

层次按教育部985、211及2022第二轮国家“双一流”名单核对，并保留更名、两地办学依据。分类为39所985、76所211、1所双一流、5所普通本科；已补115所空层次，并更新其`updated_at`。

交付：[层次依据](../outputs/school-enrichment-20261101/final/school-levels.csv)、[逐条结果](../outputs/school-enrichment-20261101/final/metrics.csv)、[逐校覆盖](../outputs/school-enrichment-20261101/final/gaps.md)、[1327条缺口](../outputs/school-enrichment-20261101/final/gaps.csv)、[来源与原文位置](../outputs/school-enrichment-20261101/final/sources.csv)、[观察输入](../outputs/school-enrichment-20261101/final/reviewed-observations.json)、[完整清单](../outputs/school-enrichment-20261101/final/manifest.json)。共享范围标识、链接、标题、原文位置、获取日期及状态均保留。

## 实现与验证

契约见[搭建文档](../考研Agent平台搭建文档.md#院校招生指标增量契约2026-11-01)。V14独立指标表每专业两项，共1594行。未知值NULL，不写2027旧`score_line`、`enrollment_count`或学情历史表。Java增加可选`admissionMetrics`；无V14时旧响应兼容。页面分年份、口径、来源、状态，补学院、方向、方式和类别。Agent、审核语料、Qdrant及条件推荐不接入新表。原Excel、采集payload、个人数据保持原值。

维护脚本默认只读；清单校验和、原行摘要、完整集合、已有指标全字段及事务锁保护人工修订。每条指标提交前再次核对所有写入值，SQL使用安全字面量；重复导入不新增或刷新时间戳。

| 实际执行 | 结果及边界 |
| --- | --- |
| Python | 两个维护脚本测试文件共24项通过；年份、学院、方式、专项、推免、共用计划、冲突及旧字段保护 |
| Java | `PYTHON_EXECUTABLE=../.cache/mcp-pdf-venv/bin/python bash mvnw -B -ntp verify`成功；日志逐套件206项，0失败、0错误；H2及模型／Redis替身 |
| 前端 | `npm run build`通过，有既有大包提示 |
| 浏览器 | 系统Chrome独立上下文，两个院校测试文件桌面／移动共12项通过；接口替身，来源、状态、共享范围、兼容及页面溢出检查 |
| 真实MySQL恢复 | 正式写入前重新完整私密备份，恢复至随机隔离库，28张原表摘要一致，隔离库V14预演通过 |
| 导入预演 | 故障回滚、显式回滚、1594指标与121校回读、重复导入、人工修订拒绝全部通过 |
| 非目标数据 | 原专业、采集、个人及其他表摘要不变；院校除层次及相应时间戳外字段不变 |
| 日常库正式写入 | 用户确认后执行V14、更新115所层次、新增1594条指标；121所及全部指标逐条回读通过，非目标数据摘要不变。再次只读预览待更新层次0、待插入指标0 |

首次Java验证因所选Python缺MCP失败，换用项目已有完整隔离环境后全量重跑通过。初次浏览器缺Chromium且沙箱启动受限，后使用获自动批准的系统Chrome独立临时上下文通过。上述隔离测试未调用付费模型、未启停日常服务；后续重启见下文。预演摘要见[rehearsal.json](../outputs/school-enrichment-20261101/final/rehearsal.json)；本机日志在`.cache/school-enrichment-20261101/`下`java-verify-mcp.log`、`browser-approved.log`及`final-guarded-rehearsal.log`。

2026-11-01后续按用户“帮我重启该项目”的指令，确认原进程工作目录属于本项目，保留各进程原有环境，正常终止并依次重启Agent、Java和Vite前端。Agent使用项目`.cache/mcp-pdf-venv`；Java加载含`SchoolAdmissionMetrics`的新JAR。重启后Agent `/health`为200、`status=ok`、招生MCP为`READY`；Java受保护院校接口无令牌返回401；前端首页及新版`SchoolMetric.vue`均返回200。MySQL和Redis保持运行。未使用真实账号、未访问需登录的实际院校详情页面，也未调用模型；端口与组件检查不代表实际页面已验收。结果及私密进程日志保存在本机`.cache/project-restart-20261101/`。

## 写入与恢复

本次确认具体清单后已使用README的`--apply --expected-sha`。入口重新备份及独立恢复预演，确认日常库期间未变后执行V14和数据事务，再回读目标与非目标摘要。不运行V1，不启动服务。正式写入也未改动原专业旧人数、分数线，797条两字段仍为NULL；267个有数值的指标全部位于新表，其中66个2027计划、201个2026参考线，67个第三方待核实。

本次备份位置及恢复库名见[执行摘要](../outputs/school-enrichment-20261101/final/application.json)；原始私密操作记录在`.cache/school-enrichment-20261101/operations/20261101-185852-944916/report.json`，执行日志在`.cache/school-enrichment-20261101/approved-apply.log`。恢复说明不变，备份SQL不随公开来源文件交付。

私密备份在`.cache/school-enrichment-20261101/operations/<时间>/before.sql`，目录700、SQL文件600，含个人数据，不公开。对应`report.json`保留备份位置、恢复库名及摘要。隔离恢复库本轮保留供复查，清理需核对范围。

DDL独立提交，后续数据事务失败可能保留空指标表；事务内失败回滚层次及指标。提交后如需撤销，先独立恢复备份，生成逐行撤销预览：仅删除全部字段仍与本清单一致的新增指标，仅恢复导入后未被人工修订的层次；后续修改保留并人工处理。禁止整库覆盖日常库，避免丢失后续账号、作答或笔记。实际撤销按具体预览另行确认。

**未运行：新指标登录后真实页面验收、真实模型／远端CI／公网部署。** 本次已完成数据库写入、回读和服务重启，实际页面显示仍需在用户登录后核验。
