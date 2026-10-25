# 独立可操作功能测试环境

日期：2026-10-23。项目：`kaoyan-agent-platform-adaptation`。本轮按用户确认方案实际创建并导入独立MySQL测试库，启动专用Redis、Agent、Java和前端；没有修改日常业务库或停止日常服务，没有Git提交或推送。

## 立即使用

打开 [独立测试页面](http://127.0.0.1:15173)。这是与日常5173页面分开的环境。后续已按用户“合并”授权把公共院校、题库和资料另行写入日常库，见[日常库合并记录](development-data-merge-2026-10-23.md)；两边此后的编辑和作答独立保存，不自动同步。下文账号和练习基线仅属于独立库。

| 用途 | 用户名 | 可测试内容 |
| --- | --- | --- |
| 有数据学生 | `fixture_student_2027` | 8批次、错题、6个收藏、30次有效作答、推荐历史 |
| 空数据学生 | `fixture_empty_2027` | 空列表、零作答、账号隔离；院校和公共资料仍可浏览 |
| 管理员 | `fixture_admin_2027` | 题目录入、4道待审题、按ID查看、审核、启停；此角色仅存在于独立库 |

随机密码在本机[私密凭证文件](../.cache/feature-env-2027/credentials.json)，文件中的`demo`、`empty`、`admin`对应上表。文件权限600，不提交或分享；源码和本文不包含密码、令牌或数据库连接凭证。浏览器验收另在管理员账号保留验证批次，每个宽度新建一个五题批次并实际提交1题，以保持学生演示基线不变；重复运行会新增管理员验证记录。

登录学生后，可依次打开：

1. `/schools`：10所真实院校，按地区、层次、专业筛选，点进详情查看2027专业、初试代码和来源；未收录的人数和分数线显示“未收录”。窄屏详情表可横向滚动查看其余列。
2. “条件推荐”：学生档案为2027年081200；选择学硕可得到最多5个候选，改为085404／专硕可测试另一类条件。浙江＋必须满足可找到浙江科技大学，河北＋学硕可找到燕山大学。
3. `/practice`：新建四科和不同难度的批次；已有8批次可用于历史回顾，其中1个批次仍有2题未答且可继续作答。
4. `/wrong`、`/favorite`、`/stat`：分别查看10道错题、6道收藏和30答／20正确／约66.67%的统计。继续作答会真实改变数据；不会自动恢复成初始数量。
5. 管理员进入`/admin/questions`，有4道待审样例。通过、驳回或启停会真实保存；测试学生请求管理接口返回403。

页面标签中的“AI”不表示此环境启用了模型。模型关闭，择校采用确定性规则，知识问答使用现有小范围短摘要；生成式文档和真实供应商效果未验收。

## 数据及隔离

- 独立库：`kaoyan_feature_test_2027`。数据库账号仅授予该库权限，日常根`.env`只用于读取本机初始化连接，未改写。
- Java18080、Agent18001、前端15173、Redis16379，均绑定或使用本机回环地址；使用独立JWT密钥、内部凭证及Redis密码。未读取日常浏览器用户资料。
- [院校夹具](../scripts/fixtures/feature-2027-schools.json)：10校15条专业；[来源核验](feature-test-sources-2027.md)说明动态目录、图片及研招网交叉核验，不造人数和分数线。
- [题库夹具](../scripts/fixtures/feature-2027-questions.json)：160题可练习，四科各40题，每科简单16、中等16、困难8；另12题覆盖待审、驳回、审核通过但停用。所有题为原创功能测试题，非真题。
- 题目由正常管理接口录入、审核和启停；审核意见标明自动化测试，不冒充人工审核。另有4份同项目既有短摘要的测试浏览副本，保留原来源与原核验日期。
- 学生的8批次、30次提交和6道收藏均通过真实Java接口产生，作答快照、错误次数及统计由服务端保存；没有写入假历史日期、学习时长或模拟模型结果。当前记录集中在实际执行当天，`totalMinutes=null`表示未记录。
- 同一份院校夹具生成业务库记录与专用Agent语料，`RAG_DATA`指向`.cache/feature-env-2027/corpus.json`；正常环境语料保持原位。推荐结果coverage根据当前语料生成。

## 可重复准备与启动

新脚本支持当前macOS/Linux环境，需要现有项目Python依赖、Java、Node、MySQL 8+、`mysql`／`mysqldump`、Redis，以及浏览器验证所需Playwright。下面使用本机已安装依赖的`.cache/chat-venv/bin/python`；其他机器替换为按README安装项目依赖的Python环境。未实现Windows版准备脚本，不把现有PowerShell日常启动入口指向此测试库。

从项目根目录执行：

```bash
# 只检查夹具和预览，未连接数据库或启动服务。
.cache/chat-venv/bin/python scripts/feature-test.py

# 全流程：独立库初始化、构建、启动、接口导入和真实HTTP/MySQL验收。
.cache/chat-venv/bin/python scripts/feature-test.py all --apply

# 已准备环境可以按阶段复用；不重跑已完成迁移、不覆盖已有题目或历史。
.cache/chat-venv/bin/python scripts/feature-test.py prepare --apply
.cache/chat-venv/bin/python scripts/feature-test.py build --apply
.cache/chat-venv/bin/python scripts/feature-test.py start --apply
.cache/chat-venv/bin/python scripts/feature-test.py seed --apply
.cache/chat-venv/bin/python scripts/feature-test.py verify --apply

# 查看身份校验后的进程状态。
.cache/chat-venv/bin/python scripts/feature-test.py status

# 需要关闭时，仅停止已登记且身份相符的本环境进程，持久数据保留。
.cache/chat-venv/bin/python scripts/feature-test.py stop --apply
```

首次初始化只接受尚不存在的指定库；同名非空库或同名既有MySQL账号没有本机归属凭据时拒绝接管。V1仅能在本脚本创建且业务表为空的库中执行，之后记录V1、V7—V12的校验和及完成状态；V12是当前代码已有的隐私功能依赖。本脚本不新增或自动修改日常业务迁移，不执行V2—V6旧演示种子。

重复执行先备份独立库，按稳定编号补缺；后续人工编辑、审核和作答保留。夹具来源版本或迁移内容变化时停止并要求核对，不以重新导入覆盖修改。中断或异常可能保留已经完成的API操作，不提供跨全部HTTP请求的一次性事务；保留备份和记录，禁止为恢复初始数量而重跑V1或删除已有测试记录。

`verify`包含管理样例启用后恢复停用、失败事务探针、重复导入及本环境Java重启，不是纯只读命令。验收断言针对初始演示基线，手工继续作答后可能因数量变化失败，脚本不会自动清理数据。专用端口被其他程序占用时拒绝启动，不结束占用进程。

真实浏览器脚本使用当前测试服务，默认读取上述私密凭证，不模拟接口：

```bash
# macOS本机Chrome；其他机器可省略此变量，使用已安装的Playwright Chromium。
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' node scripts/browser-feature-env.cjs
```

本地离线夹具回归可运行 `python -m unittest discover -s scripts/tests -v`；CI已加入默认预览和此回归入口，远端CI本轮未运行。

正常桌面终端可直接运行；受限执行环境若不允许读取进程身份或启动浏览器，需该环境提供相应执行权限，不能跳过身份检查冒险停止进程。

## 验证证据

本轮实际完成：

- 8项夹具／边界测试：独立数值示例、篡改答案、非法多字母答案、重复编号、拒绝远程库、SQL字面量与不执行未知核验代码。
- 后端82项测试通过并打包；Agent126项pytest通过；前端生产构建通过。已有依赖有弃用提示和前端分包体积提示，不代表功能失败。
- [最终HTTP报告](../.cache/feature-env-2027/http-report-20261023-111027.json)：63项真实MySQL与运行中Java／Python的HTTP验证，包括10校15专业、四科难度数量、提交前隐藏答案、管理样例、版本冲突、统计一致性、账号隔离、回滚、重复导入和Java重启恢复。
- [真实浏览器报告](../.cache/feature-env-2027/browser-2026-10-23T03-17-55-680Z/report.json)：13项通过、无页面异常、未拦截或模拟API；1280及390宽度检查院校筛选、来源详情、练习回顾、错题、收藏、统计、管理页及实际提交判分。已查看页面截图，修复窄屏院校详情列宽和顶部对齐，并重新通过13项；390宽度是模拟窗口，不是真实手机。

其他报告、数据库备份及服务日志均在`.cache/feature-env-2027/`，仅供本机检查与恢复，不作为可公开提交材料。`seed-report.json`记录初始导入；`http-report-*.json`记录各轮实际验收；`source-refinement-report.json`记录燕山大学补齐学习方式直接证据的受控更新，旧语料和更新前备份保留。

首次构建因测试进程继承新语料而触发“三校”断言，修正构建时使用正常语料后82项通过。新空库曾因V1与后续表的默认排序规则不同导致启动失败，统一本独立空库为MySQL 8的`utf8mb4_0900_ai_ci`后完成启动；没有转换日常数据。浏览器早期等待条件与已完成批次自动回顾的实际行为不符，修正检查后13项通过，未修改刷题规则。

未运行：真实付费模型、Qdrant向量检索、公网部署、真实手机。服务端草稿、提示辅助和正式结束批次等尚未实现能力不在本轮通过范围，未用夹具冒充实现。自动测试通过不代表招生资料全国覆盖、题目人工审核或备考效果提升。
