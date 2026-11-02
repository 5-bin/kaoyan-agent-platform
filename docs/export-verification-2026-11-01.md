# 文件导出实现与验证 2026-11-01

## 实现与数据边界

本次在当前考研平台增加 Word、PDF、Markdown 导出，入口为个人笔记当前／历史版本、学习统计页，以及成功回答中的全文、复习计划、笔记建议。共用预览弹窗；导出由 Java 确定性生成，不调用模型，不改变 HelloAgents 编排及预算。模型生成仍沿用原助手授权。

三个接口与字段统一见[搭建文档](../考研Agent平台搭建文档.md#文件导出契约2026-11-01)。预览固定数据，Redis按账号保留15分钟、最多5份；Lua原子淘汰，完整快照以JSON字符串保存，避免Lua cjson将空数组改成对象。文件生成前后核对来源，跨账号、过期、已清除来源不可读取。当前及历史笔记按精确版本读取；建议是否已保存由本人 personal_document_version 的 source_task_id 核对，文件保留原建议，不用后来笔记内容替换。

学情报告按服务器上海日期近30天统计，另列画像版本及更新时间；有效提交次数与画像去重独立证据分别展示。未记录时长、未校准参考分、辅助及未知证据、无数据和样本不足均明确标注。报告图表为服务器Java2D生成，不使用浏览器上传的截图或统计值。

## 环境与依赖

本机 macOS arm64，实际Java为25.0.4.1，Maven wrapper 3.9.9，编译目标Java17；Node22.23.3，Python3.13的 `.cache/mcp-pdf-venv`，Chrome独立临时上下文。Java17运行时本轮未运行。

新增锁定依赖：CommonMark及GFM表格扩展0.24.0、Apache POI5.4.1、OpenHTMLtoPDF PDFBox1.1.37。Word由[POI XWPF](https://poi.apache.org/components/document/index.html)生成；PDF采用[OpenHTMLtoPDF](https://github.com/openhtmltopdf/openhtmltopdf)。随包提供SIL OFL字体及许可证，来源与重建入口见[字体说明](../kaoyan-B/src/main/resources/export-fonts/README.md)。

Noto Sans SC 固定字重400；为497个共享轮廓的Unicode别名分配独立字形编号，保留轮廓和字符映射，使PDF普通汉字提取不变成部首码点。打包字体SHA256：`d28b55efbac02c122821565015991ae07523ac0c4dae736fe367184d3923eaeb`。Word嵌入混淆字体，PDF嵌入子集，避免依赖维护者本机字体。

## 实际验证

- Java最终 `verify`：195通过、0失败、0错误、0跳过，58.30秒；专项包括文本与图表、精确40000字符、600字符无空格代码、90行跨页表格、中文文件名、三格式下载、来源白名单、未登录／跨账号／注销、清除后下载拒绝、已确认建议版本、无数据／画像关闭、缓存不可用503及并发繁忙429。Redis检查启动独立随机端口真实进程，验证Lua并发创建、最多5份与过期，不使用日常Redis。
- Python Agent完整回归：546通过，2条已有依赖警告，80.02秒。新增Python仅为维护字体的脚本，未修改Agent源码；脚本另经py_compile检查。
- 前端生产构建通过（保留既有大chunk提示）。新增导出专项桌面／390px共6通过；连同笔记、助手和学情可视化相关回归共52通过，1.7分钟，业务API替身，不冒充真实后端验收。
- 实际浏览器链路由 `scripts/smoke-export.cjs` 验证：Vue生产预览 → Java → 独立真实Redis／内存H2；桌面和390px下完成32次下载，包括笔记当前／历史版本、学情、回答、计划、建议。模型关闭，未连接日常MySQL；样例均为测试类路径中的合成夹具。最终报告为 `.cache/export-smoke-final-2026-11-01.json`。
- 文件QA使用本次bundled LibreOffice及Poppler，不使用用户桌面Office资料。普通笔记与学情Word/PDF已逐页查看PNG，字体、表格、图表和分页可读。40000字符压力样例的Word转换为37页、PDF26页；末尾标记及表格完整性由自动测试检查，Word全页拼图检查并抽看原尺寸页面。
- 第一次沙箱Chrome启动失败，实际浏览器测试经系统授权后完成；早期选择器命中了Element Plus内部输入覆盖层，调整测试为点击完整选择框后通过。PDF QA初期未配置可写字体缓存时图像不可靠，最终使用任务专用Fontconfig配置与嵌入字体重新渲染。上述失败不计作通过。

复现命令（先安装README中依赖；REDIS_SERVER可设置为本机redis-server绝对路径）：

```bash
# kaoyan-B目录
KAOYAN_EXPORT_REDIS_TEST=true PYTHON_EXECUTABLE="$PWD/../.cache/mcp-pdf-venv/bin/python" bash mvnw -B -ntp verify
bash mvnw -B -ntp test-compile dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt
# kaoyan-frontend目录
npm run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="本机Chrome路径" npx playwright test tests/export.spec.ts tests/notes.spec.ts tests/assistant-ui.spec.ts tests/learning-profile-visual.spec.ts
# 项目根目录；报告和对应-artifacts目录必须不存在
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="本机Chrome路径" node scripts/smoke-export.cjs .cache/new-export-smoke.json
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests
```

未设置 KAOYAN_EXPORT_REDIS_TEST=true 时，真实Redis集成测试显式跳过；其余测试照常运行。Smoke只清理本次创建的服务与临时库，不停止日常进程。

## DeepSeek Harness 实际使用

使用本机已安装的 DeepSeek Harness `0.2.1-rc.5`，官方[headless单任务入口](https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/README.md)。独立工作区及DSH_HOME位于 `/tmp/kaoyan-export-harness-review`，仅提供相关源码、合成Markdown和脱敏测试摘要，未复制.env、用户记录或运行缓存。凭证只经环境传给供应商适配器；禁用工具、子Agent入口、自动重试、自动压缩、额外日志上传与遥测，平台自身没有引入Harness依赖。

第一次把原OpenAI端点交给Harness，Messages请求404且无生成用量；查[官方Messages配置](https://api-docs.deepseek.com/guides/anthropic_api/)后仅在隔离开发调用中改为同供应商的 `https://api.deepseek.com/anthropic`，未修改项目.env。源码审查随后完成：24.65秒，未缓存输入15584、输出3544 token。

采纳并核对的建议：图片格式与解码校验、格式枚举拒绝、单次读取可选画像服务、普通中文避免插入零宽换行；另以测试核对来源前后检查和缓存边界。Harness首轮关于已有前后检查、按需求淘汰、TTL提前过期的高风险判断不成立，未按其建议改架构。缓存空数组及字体问题由实际测试／渲染发现，不归功于模型审查。

追加最终代码／测试摘要复核输出达到2048 token上限，15.0秒退出码1；未把这次截断输出当作完整审查通过。取得输入7890、缓存读取128、输出2048 token。总可取得输入23602（其中缓存128）、输出5592，未取得供应商账单金额。最终判断以本轮源码核对及实际测试为准。

## 样例与限制

[合成学情PDF](../outputs/export-examples-2026-11-01/learning.pdf)、[合成学情Word](../outputs/export-examples-2026-11-01/learning.docx)、[合成学情Markdown](../outputs/export-examples-2026-11-01/learning.md)、[合成笔记Word](../outputs/export-examples-2026-11-01/note.docx)可直接打开；同目录保留笔记PDF／Markdown和真实下载验证摘要。

本轮未执行数据库迁移、导入或清理，不创建分支、不提交或推送。公网部署、Windows／原生Microsoft Word／WPS、真机移动端及真实用户私有内容导出均未运行。长ASCII连续片段在Word/PDF中会插入零宽换行以避免越界，复制长代码时可能包含该字符；Markdown保留原代码。复杂公式和远程图片不作富媒体渲染，图片只保留说明，HTML只作文本。导出快照是短期缓存，不是永久文件存储或新的业务记录。

## 本机加载

2026-11-01 12:55（上海时间）在此前用户启动授权范围内重新加载Java及前端，保留原MySQL、Redis、Agent进程。Java连接现有MySQL成功，前端HTTP200、Agent健康HTTP200、未登录前端代理返回401；OpenAPI确认三个导出接口已加载。仅检查启动和未认证入口，不登录或导出日常账号资料。当前页面为 http://127.0.0.1:5173/ ，已有页面需刷新。
