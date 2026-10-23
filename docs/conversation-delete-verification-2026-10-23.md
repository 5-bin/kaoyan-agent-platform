# 会话列表删除验证（2026-10-23）

## 改动范围

桌面侧栏、手机会话抽屉共用`ConversationListItem.vue`，每行常驻垃圾桶按钮，标题单行省略。确认后复用已有删除接口；失败保留当前内容，成功后修正列表、总数、分页及路由。删除当前会话清理临时状态和流订阅，删除其他会话保留当前输入。旧列表请求、旧会话消息及旧账号删除响应不能覆盖当前状态。

契约见[连续聊天说明](conversations.md#会话列表删除)。无接口、Python业务逻辑或数据库迁移变更。未操作日常数据库、提交、推送或部署。

## 实际验证

- `npm run build`：通过 TypeScript 检查与 Vite 生产构建；保留现有大分包提示。
- 原有`assistant-ui.spec.ts`和`conversation.spec.ts`：桌面与390×844模拟手机宽度共14项通过，检查行高／标题省略／选中状态、聊天、重试／停止／重连及账号切换。
- 新增`conversation-delete.spec.ts`：桌面与390×844模拟手机宽度共14项通过（最终运行21.4秒）。用例覆盖取消与失败、重复请求防护、删除当前／其他／最后一条、生成中删除、首次发送新建、刷新、分页、迟到分页、账号切换与迟到消息；两种宽度均包含键盘触发删除按钮。
- `PYTHON_EXECUTABLE=/tmp/kaoyan-delete-python-20261023/bin/python sh ./mvnw -B -ntp -Dtest=ConversationIntegrationTest test`：12项通过。真实HTTP进入Java与隔离Python，使用独立H2内存库、Redis测试替身和模拟模型供应商；包含跨账号删除404、聊天内容清除、个人笔记保留和额度记录保留。Java业务代码未修改，未运行全量`verify`。

## 环境与限制

项目Maven Wrapper未设置可执行位，使用`sh ./mvnw`运行。现有Python虚拟环境缺少LangChain，首次后端测试未能启动；改用`/tmp`独立虚拟环境安装项目声明版本及约束后通过，未修改原有环境。

Playwright自带Chromium未安装；本机Chrome在沙箱内启动即退出。经自动审批允许后，使用`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`在隔离浏览器上下文运行。测试使用临时Vite服务和模拟API，不读取日常浏览器资料。早期测试修正了模拟路径误拦截源码、弹窗退出动画及分页滚动定位，最终结果单独记录。

未运行浏览器连接真实Java／MySQL的整站验收、真实手机、真实外部模型和公网部署；页面测试通过不等于这些验收完成。未删除用户实际会话。测试日志和浏览器输出位于`/tmp/kaoyan-delete-*20261023*`。
