# 招生MCP文字型PDF扩展与验证

> 2026-11-01状态：招生自动抓取、解析与核验已被仅提供登记网址的方案替代。当前实现见[招生官网网址契约](../考研Agent平台搭建文档.md#招生官网网址契约2026-11-01替代自动核验)。以下原始记录保留，仅证明当时的环境与验证范围。

2026-11-02提交前核对：旧PDF解析夹具已随旧方案移除，下文路径仅作历史定位，不是当前可运行入口。


日期：2026-10-29。本轮在原招生MCP中增加PDF能力；默认关闭，不修改真实`.env`、日常数据库或运行服务，不调用真实模型，不提交、推送或部署。业务设计与契约统一见[搭建文档](../考研Agent平台搭建文档.md#阅读导航)、[RAG契约](rag.md)和[会话契约](conversations.md)。

## 交付行为

原`check_admission_updates`、`ADMISSION_CHECK`、SCHOOL专家及Java保存职责不变。批准来源可直接登记PDF，也可由年份明确的官网页面发现招生目录附件；逐跳继续精确域名、公网地址及固定IP/TLS SNI校验，不自动放行CDN，不接受用户URL、文件、密码或HTTP参数。

下载根据响应类型和PDF头识别，不只信扩展名；HTML保持2MiB，文字PDF限8MiB／60页，每轮最多2份不同内容，重复文件按原字节哈希去重。仅完整同页年份、学院、专业、学位、学习方式及明确表格对应生成差异。跨页条件、方向、合并单元格、相互冲突科目、扫描件、损坏／加密／超限等均明确限制；自由文本只形成页码证据。共享研招域名还要求同页出现院校身份，不能只凭域名推定学校。

新增可选证据字段`format`、`pageNumber`和`bbox`：旧记录默认为HTML且没有页码／坐标，PDF必须有1—60的文件页序及有限非负、正面积坐标。坐标顺序为`x0,top,x1,bottom`，单位PDF点；不是印刷页码。PDF的`contentHash`为下载原字节SHA256，HTML沿用原算法；不以PDF元数据／文件名推断招生年份或公告日期。

Python、Java和前端同步校验，PDF仍为`UNREVIEWED`，只存于本人任务／会话的`admissionCheck`，不进入正式`references`、推荐依据或RAG。前端在展示时添加`#page=N`，服务端来源URL保持无片段。原历史无需回填或迁移；管理员仍使用本人助手入口。

## 隔离执行与依赖

新增`admission_pdf_worker.py`与`core/admission_pdf.py`，不复制框架、不修改已安装包。原HelloAgents原生工具实际调用MCP，PDF解析作为确定性辅助执行，不新增Agent或工具循环。

每个招生MCP服务最多1个活跃PDF解析进程。独占临时目录中的PDF权限0600，子进程仅接收公共基线身份及应用生成路径，不传账号、聊天正文、模型／业务库凭证。工作进程无网络、OCR、外部程序执行或业务数据库连接。stdout为最多256KiB的类型化JSON，stderr丢弃，结果仍受整轮64KiB上限约束。

单份解析最多5秒；整轮内部工作11秒，为清理和返回预留时间，客户端仍12秒。每100毫秒以psutil观测RSS，超过512MiB即终止；这是监测阈值，**不是绝对硬内存限额**。取消、超时、超量输出或监测失败先终止，250毫秒未退出则强制结束并等待回收，然后清理临时文件；进程创建中的取消也回收已创建子进程。解析失败或后续查询到期保留此前取得的有效证据，不把部分扫描结果称为完整核验。

本轮独立创建`.cache/mcp-pdf-venv`并安装当前`requirements-dev.txt`，没有复制或修改旧虚拟环境。实际导入与`pip check`通过：

| 包 | 锁定并实际导入版本 |
| --- | --- |
| pdfplumber／pdfminer.six | 0.11.10／20260107 |
| psutil／pypdfium2 | 7.2.2／5.14.0 |
| Pillow／cryptography | 12.3.0／50.0.2 |
| cffi／pycparser | 2.1.1／3.12 |
| HelloAgents／MCP | 0.2.8／1.12.4，保留原版本 |
| Pydantic／OpenAI | 2.10.3／1.109.1，保留原版本 |

运行环境：macOS ARM64、Python3.13.15、Node22.23.3、本机JDK25.0.4.1；Java编译目标仍17。旧`.cache/mcp-phase1-venv`不含本轮PDF依赖，不用于启动当前源码；其他机器按requirements安装，不依赖本机缓存路径。

## 实际验证

| 检查 | 本轮结果 |
| --- | --- |
| Python全量pytest | 436项通过，40.02秒；新增30项PDF检查；保留2条已有弃用警告 |
| Java `bash mvnw -B verify` | 181项通过，55.353秒；含PDF字段、旧证据兼容及实际Java→Python→MCP→PDF保存／隔离检查 |
| 前端生产构建 | 通过，3.59秒；保留已有大资源块提示 |
| 页面Playwright | 桌面1280和390宽度共6项，覆盖原HTML、不可读和PDF证据、页码链接、刷新及无横向溢出；模拟API |
| 实际三端隔离浏览器链路 | 13项通过，使用实际Vue、Java、FastAPI、stdio及真实PDF解析进程；检查页码链接、刷新、跨账号404、Java重启后证据恢复 |
| 依赖／静态检查 | `pip check`、Python语法、文档链接及`git diff --check`通过 |

新增测试包括固定中文PDF的科目变更、一致、错误年份／学院／学习方式、方向、跨页、合并单元格、自由文本、图片、乱码类缺条件样例、重复／冲突、空密码及非空密码加密、损坏、61页／8MiB超限；还覆盖附件发现、octet-stream识别、每轮2份限制、有效HTML结果在后续超时后保留、解析全局并发1、输出上限、创建中取消和子进程回收。

真实stdio测试实际启动PDF工作进程，通过协议取消／超时后验证PID消失、临时目录被删除、其他请求仍能使用共享会话。为避免消耗主机资源，内存终止测试降低观测阈值触发，**未构造实际512MiB内存耗尽**；超时夹具也使用较短测试阈值。不能据此承诺任意恶意PDF绝不瞬时超过阈值。

夹具为本项目自编的16份小PDF，说明与重建入口在夹具目录（历史路径 `kaoyan-agent/tests/fixtures/admission-pdf/README.md`）。它们不是官网资料或招生事实，不复制第三方PDF。已用PDFium渲染并人工查看有效表格、合并单元格及其余非加密样例的页面／联系表，独立核对文件第2页、科目805／408、跨页缺年份、方向列及其他招生组合。PDF解析断言还核对有效行位置`(30,116,775,152)`。本机Poppler缺少Adobe-GB1映射，首轮中文渲染不完整，改用PDFium；没有以空白渲染当作验证通过。视觉检查发现前端页码重复显示后已修正，并复测。

三端链路只替换官网响应、模型供应商和Redis，PDF解析使用实际库和独立进程，业务保存使用临时H2。它不等于真实MySQL／Redis、真实模型或真实招生内容验收；没有产生真实模型调用、token或费用。截图和报告位于忽略的本机`.cache`中，测试结束只清理本次服务及浏览器。最终报告为`.cache/admission-pdf-chain-final-20261029.json`；截图为`.cache/admission-pdf-browser-1793285553625349000/admission-1280.png`与`admission-390.png`，最终6项模拟页面检查用时4.3秒。

## 复现命令与剩余范围

```bash
# 根目录：使用当前锁定依赖的Python，不读真实.env
.cache/mcp-pdf-venv/bin/python -m pip check
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests/test_admission_pdf.py
.cache/mcp-pdf-venv/bin/python scripts/check-project.py
# 只有这个选项联网；报告路径必须为新文件
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py --live --output .cache/new-admission-pdf-live.json
```

完整浏览器链路先按README构建Java测试类路径和前端，然后从根目录执行：

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  .cache/mcp-pdf-venv/bin/python scripts/smoke-chat.py --admission-pdf --output .cache/new-admission-pdf-chain.json
```

该选项只在测试入口使用自编PDF作为官网响应，生产入口不启用测试替身。启用仍使用原`ADMISSION_MCP_ENABLED=true`和原FastAPI入口，但须使用本轮Java／前端与含PDF依赖的Python；本轮未修改开关或重启日常服务。

联网烟测报告`.cache/admission-pdf-live-20261029.json`记录10校均为`UNAVAILABLE`，仍因官网域名解析到非公网地址被拒绝连接。未绕过DNS／来源限制，不能把拒绝连接写成学校网站失效。**十校真实PDF抓取、逐校版式与内容准确性尚未验收**；扫描件OCR、用户上传、异步大文件任务及自动发布未实现。真实MySQL／Redis、真实供应商、真实手机、Windows／Linux运行及远端CI／公网部署均**未运行**。
