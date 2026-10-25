# 院校省份与专业下拉筛选验证

日期：2026-10-23至2026-10-24，Asia/Shanghai。项目：`kaoyan-agent-platform-adaptation`。

## 本次改动

院校页面的省份、专业名改为可搜索选项、可清空的单选下拉框，不允许创建自定义选项。选择后仍需点击“搜索院校库”；清空表示不限制该条件。保持层次筛选、条件推荐及推荐历史原有行为。

新增认证只读接口 `GET /api/schools/options`，通过统一响应包装返回 `{provinces: string[], majorNames: string[]}`。从业务院校库查询非空、非纯空格、去重且排序的值；专业必须关联现存院校。选项不随筛选结果缩减；页面进入时加载，空库显示“暂无选项”，失败可独立重试。搜索继续使用原有参数及匹配规则。

选项仅表明数据库中存在对应记录，不表示招生资料已经核验。不读取Python推荐语料，不调用模型，无新依赖、数据库迁移或业务数据改写。新接口及页面行为已同步[搭建文档](../考研Agent平台搭建文档.md)。

## 实际验证

| 检查 | 结果与范围 |
| --- | --- |
| 前端生产构建 | `npm run build`通过；Vue／TypeScript检查和Vite构建成功，仍有现有的大包体提示 |
| Java Maven验证 | `bash mvnw -B -ntp verify`通过：95项，0失败、0错误、0跳过；包括新增4项院校选项集成测试 |
| 后端新增用例 | 独立H2验证未登录401、空库空数组、跨年份重复值去重、NULL／空字符串／纯空格过滤、排序、孤立专业排除及新增记录读取；原GET／POST筛选、清空及详情接口兼容 |
| 模拟API页面回归 | Playwright定向运行`school-options.spec.ts`与`recommendation.spec.ts`，1280及390宽度共14项通过；覆盖选项搜索、禁止自建、组合筛选、清空、选项不缩减、失败重试、空库、加载状态及原推荐交互 |
| 真实后端页面检查 | 使用随机本地端口、生产前端、真实Java及独立H2数据；无API拦截，Redis为替身。1280及390宽度均通过登录、按钮触发查询、三条件筛选、清空恢复及全部选项保留；无横向溢出及页面异常 |
| 差异检查 | `git diff --check`通过 |

本机使用Node 22.23.3、JDK 25（编译目标17）、桌面Chrome。H2配置将`USER,YEAR`声明为非关键字，仅用于测试。Java测试的Python子进程使用项目已有`.cache/chat-venv/bin/python`；未访问真实模型供应商。

## 复现与证据

在项目根目录执行后端验证：

```bash
cd kaoyan-B
PYTHON_EXECUTABLE="$PWD/../.cache/chat-venv/bin/python" bash mvnw -B -ntp verify
```

其他机器将`PYTHON_EXECUTABLE`替换为已安装项目测试依赖的Python绝对路径。新增后端用例位于`kaoyan-B/src/test/java/com/kaoyan/SchoolOptionsIntegrationTest.java`，测试建表文件仅用于独立测试库。

在`kaoyan-frontend/`执行构建和定向页面回归：

```bash
npm run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm run test:e2e -- tests/school-options.spec.ts tests/recommendation.spec.ts
```

Chrome路径是本机路径；其他机器按README指定浏览器。浏览器使用独立临时上下文，不读取日常用户资料。首次沙箱内Chrome启动即退出；随后在允许的执行范围使用独立上下文完成验证。测试调试中修正了H2年份关键字配置、模拟API路径及下拉弹层可见性断言，以上结果均为修正后的实际结果。

本地证据（缓存与临时文件不纳入源码）：

- 后端日志：`/tmp/kaoyan-school-options-maven-final-20261023.log`，测试报告另见`kaoyan-B/target/surefire-reports/`。
- 模拟API日志：`/tmp/kaoyan-school-options-playwright-final-20261024.log`，截图位于`/tmp/kaoyan-school-options-playwright-final-20261024/`。
- 真实后端报告：[report.json](../.cache/school-options-live-20261024-000157/report.json)。[桌面筛选截图](../.cache/school-options-live-20261024-000157/1280-filtered.png)、[手机宽度截图](../.cache/school-options-live-20261024-000157/390-filtered.png)。使用合成测试院校，不作为招生依据。
- 真实后端检查由本次临时脚本`/tmp/kaoyan-school-options-live-20261024.py`及对应`.cjs`启动，复用`FrameworkSmokeServer`和独立测试schema；结束后已停止本次Java和前端进程。

## 未运行与生效条件

日常MySQL、真实Redis、真实手机、远端CI及公网部署未运行。现有`browser-feature-env.cjs`已改为点击省份选项，但未运行其完整测试流程，避免写入该环境的练习记录。

未重启日常服务；已有运行中的Java后端需要重新启动以加载新接口，前端发布使用本次构建产物。保留原有工作区修改，未提交、推送或发布。
