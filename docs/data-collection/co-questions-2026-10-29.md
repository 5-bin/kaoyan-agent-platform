# 2026-10-29 计算机组成原理课程习题接入

按用户“联网查找一些计算机组成原理题目，并导入数据库上线”的授权，本次已经在当前本机项目新增并发布40道中文单选题。来源为Chris Terman的Computation Structures课程既有习题子问，明确标为`COURSE_EXERCISE`，不冒称408统考真题、教师审核题或原作者审定的中文版本。没有部署公网。

## 实际结果

| 项目 | 结果 |
| --- | --- |
| 新增题量 | 计算机组成原理40题：简单11、中等19、困难10 |
| 题库总量 | 404题：数据结构144、操作系统120、计算机网络100、计算机组成原理40 |
| 录入与发布 | Java整批预览、一次导入40条待审核版本1，再逐条审核为已启用版本2 |
| 内容范围 | 补码、溢出、组合逻辑、流水线性能、寄存器／基址／相对寻址、数据通路、Cache、中断 |
| 个人及既有数据 | 原364题逐行摘要一致；其余27张业务表摘要一致，未新增个人作答或修改历史 |
| 知识／招生资料 | 36篇公开资料、121校797条专业记录保持不变；知识／招生RAG仍为31条 |

这40题没有补齐计算机组成原理每档难度及100题的收集目标，也没有据此完成整卷估分或408全知识点覆盖。

## 联网题源、许可及改编

本轮从原站下载题目与答案附件，保留SHA256摘要及获取日期；候选附件8套，实际选用以下7套。每道数据库记录均有作者、原编号、题目PDF页序、题目／答案链接、获取日期、改编说明和完整MIT许可。逐题对应见[题目目录](../../outputs/co-questions-20261029/catalog.json)，下载证据见[来源清单](../../outputs/co-questions-20261029/sources.json)。

| 原课程练习册 | 本次采用的原编号／PDF页序 | 改编题数 |
| --- | --- | ---: |
| [Basics of Information](https://computationstructures.org/worksheets/L01.html) | 2.A–I第一式、2.K；第4、5页 | 10 |
| [Combinational Logic](https://computationstructures.org/worksheets/L04.html) | 7.A、7.B、9.A、9.C；第7、9页 | 4 |
| [Performance Measures](https://computationstructures.org/worksheets/L07.html) | 1.A–D；第2页 | 4 |
| [Instruction Set Architectures](https://computationstructures.org/worksheets/L09.html) | 2.A、2.B1–4、2.D；第3页 | 6 |
| [Building the Beta](https://computationstructures.org/worksheets/L13.html) | 1中的SHLC、SUB、LD、ST；第2、3页 | 4 |
| [The Memory Hierarchy](https://computationstructures.org/worksheets/L14.html) | 1.A、1.B三项、2.A–D；第2–4页 | 8 |
| [Devices & Interrupts](https://computationstructures.org/worksheets/L18.html) | 2.A–C、4.A；第3、5页 | 4 |

[原站使用条款](https://computationstructures.org/terms.html)明确将网站及其材料以MIT许可提供，同时排除另标“all rights reserved”的第三方内容。本次选用的题目与答案页未见该例外标记。完整版权、授权与免责文字保留在每题`permissionNote`及[许可文件](../../outputs/co-questions-20261029/LICENSE-MIT-course.txt)，保留署名，不使用学校标识作宣传或暗示背书。

改编包括中文翻译、填空／判断转单选、新增干扰项与中文解析；以Beta为背景的题目在题干完整给出本题指令语义，不将Beta参数当作通用处理器约定。流水线原题需要在图中放置寄存器，本批改编明确给定合法划分及级延迟后考查性能，不声称是原图布局题的原样翻译。各题改动已单独登记。

学生刷题入口选中计算机组成原理后，可查看[完整许可静态文件](../../kaoyan-frontend/public/licenses/computation-structures-mit.txt)和[40题出处静态文件](../../kaoyan-frontend/public/question-sources/co-20261029.json)。公开出处文件不包含本地标准答案、解析或选项；原站公开的教材答案与本平台提交前隐藏答案的业务边界分别处理。

## 内容核对与实际验证

- 使用PDF渲染检查13张相关答案页，并对照原题定位。40题均进行了独立计算或完整真值表检查，结果见[独立验算](../../outputs/co-questions-20261029/independent-checks.json)。例如6位−21补码101011、0xD6为−42、直接映射Cache标记20位、寄存器编号与立即数区分、中断可抢占响应时间及800秒程序耗时。属于用户委托的AI辅助检查，未虚构另一位人工或教师审核。
- 对本机`kaoyan_dev`的28张表完整备份，恢复到独立库`kaoyan_realdata_verify_f1770c31d03e`后摘要一致；40题隔离追加、故障注入回滚、显式回滚均通过。Java批量预览不写库，正式导入先进入待审，再经现有审核接口发布。原题及其他表逐行摘要不变，见[写入报告](../../outputs/co-questions-20261029/publication-result.json)。
- 40个学生详情均能读取且不含答案、解析；按简单／中等／困难分别读取11／19／10道，全部40题进入组成原理学生题池。验证没有创建练习、作答、笔记或任务。
- 404题本地索引`questions-61a43a79e166fc054b2f3fd3d84efe12`已READY。以本批40题ID为授权集合执行“补码”“Cache”“中断”本地检索均有结果且未越出集合；索引请求不含标准答案及解析。知识／招生RAG版本仍为`rag-v1-a476bf509577d904`。本轮付费模型调用0次。
- 前端`npm run build --prefix kaoyan-frontend`通过，包含静态许可／出处文件，保留既有大分包提示。Java与Agent源码未因本次题库操作修改；本轮Java全量verify、Agent pytest、真实模型、完整判分与统计闭环、断电恢复和公网部署检查均未运行。
- 独立Chrome检查学生新题预览、科目选择与许可链接、管理页审核／来源／答案和390像素预览通过，截图已检查。初次验证脚本的API拦截范围误匹配前端源码路径，已改为只拦截站点根`/api/`后复测；新增public目录经前端重启后静态许可与出处实际回读一致。验证未写业务记录。

接口、索引及浏览器结果以[本轮验证文件](../../outputs/co-questions-20261029/verification.json)为准。独立浏览器仅检查公共题库与管理题目页面；个人学情及做题历史请求使用替身，不接管日常浏览器或读取个人记录。

页面证据：[学生预览](../../outputs/co-questions-20261029/student-preview.png)、[组成原理入口及许可](../../outputs/co-questions-20261029/practice-entry.png)、[审核与来源登记](../../outputs/co-questions-20261029/admin-reviewed-cache.png)、[手机宽度预览](../../outputs/co-questions-20261029/student-preview-mobile.png)。

## 本机运行与恢复

开始时MySQL与Redis在运行，8001／8080／5173没有监听。已按本机上线范围启动Agent、Java和前端，保留现有数据库及Redis服务。初次Java启动后，`target`运行包被随后构建替换，出现依赖加载失败；本批仍未写入。校验当前JAR完整性后，只停止本次启动的Java，将已校验产物复制到独立私密目录重新启动，预览接口及注销接口恢复正常后才执行导入。

当前Java使用`.cache/local-runtime/20261029-093345-co-stable/kaoyan-backend.jar`；Agent与前端启动记录在`.cache/local-runtime/20261029-092459-start/processes.json`，Java新进程记录在上述独立目录。新增静态文件时原前端进程尚未加载新建的public目录，已只重启本次启动的前端；当前前端进程记录在`.cache/local-runtime/20261029-094523-co-frontend/processes.json`。运行包副本解决本次构建覆盖问题，不表示已部署公网或完成整站其他改动验收。

正式导入前备份位于`.cache/co-questions-20261029/20261029-093418-publish/before.sql`，文件600、审计目录700；逐题新增ID见[写入映射](../../outputs/co-questions-20261029/published-mapping.json)。若后续需要撤销，先按ID停用本批，核对新产生的历史及版本后再处理，不覆盖原364题或回滚用户后续个人记录。本次未执行删除、旧迁移、账号改密、分支、提交或推送。
