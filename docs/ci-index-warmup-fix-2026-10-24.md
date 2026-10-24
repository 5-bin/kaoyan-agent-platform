# CI索引等待与浏览器检查修复

日期：2026-10-24。基线：`7efc315`。范围为隔离聊天集成测试、Python夹具、浏览器测试服务及聊天断言和验证文档，无生产接口、限额、数据库或模型配置变更。

## 失败与原因

[GitHub Actions运行40085234059](https://github.com/5-bin/kaoyan-agent-platform/actions/runs/40085234059/job/120846698041)在Java验证阶段失败：128项测试中，`publicMaterialSelectedUsingWithdrawnPrivateTopicDoesNotReachModel`一项失败，其余无错误。Python测试与文档检查已通过，后续前端及浏览器步骤被跳过。

测试辅助方法`finish`收到题目索引BUILDING后，每隔约150毫秒创建一个新的重试任务。Linux首次加载本地Qdrant较慢，索引就绪前可能耗尽每分钟6次额度，导致重试接口429。该失败来自测试等待方式，不能通过提高业务限额掩盖。

## 修复

- Java测试从隔离H2中的生成上下文读取本次索引版本，通过已有内部状态GET接口只读等待READY，然后仅创建一次重试。30秒仍未就绪、构建失败或重试后仍未就绪均明确失败，不持续消耗任务配额。
- Python聊天夹具新增仅测试可用的`QUESTION_TEST_SLOW_INDEX=true`开关，在索引构建线程中延迟2秒。Java聊天集成测试固定启用它，使本机也能覆盖较慢冷启动；生产代码不读取该开关。
- 新增慢索引回归，检查最终READY、无业务操作、首次生成及唯一重试共2条生成与2条任务，并核对每分钟限额仍为6。

## 本轮实际验证

环境：macOS、Java 25.0.4.1（编译目标17）、Python 3.13，沿用本项目`.cache/chat-venv`。使用随机端口、隔离H2、Redis及Embedding／模型替身，未启动日常MySQL或Redis。

| 检查 | 实际结果 |
| --- | --- |
| 修复前，增加2秒冷启动延迟后运行原失败用例 | 稳定复现重试接口429；1项失败，无错误 |
| 修复后Java完整verify及测试类路径生成 | 129项通过，0失败／错误／跳过，BUILD SUCCESS；包括原失败用例及新增慢索引用例 |
| Python与脚本pytest | 227项通过，保留1条已有Starlette／AnyIO弃用提示 |
| 文档、框架、夹具预览及脚本unittest | 均通过；unittest为8项；夹具预览未连接数据库或启动服务 |

复现入口（从项目根目录）：

```bash
export PYTHON_EXECUTABLE="$PWD/.cache/chat-venv/bin/python"
(cd kaoyan-B && bash mvnw -B -ntp verify dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt)
.cache/chat-venv/bin/python -m pytest -q kaoyan-agent/tests scripts/tests
.cache/chat-venv/bin/python scripts/check-project.py
.cache/chat-venv/bin/python scripts/check-framework.py
.cache/chat-venv/bin/python scripts/feature-test.py
.cache/chat-venv/bin/python -m unittest discover -s scripts/tests -v
git diff --check
```

本轮日志保存在本机`/private/tmp/kaoyan-ci-slow-index-before-20261024.log`、`/private/tmp/kaoyan-ci-index-fix-java-20261024.log`和`/private/tmp/kaoyan-ci-index-fix-python-20261024.log`。远程Linux结果以修复PR的Actions检查为准，不将本机Java25结果表述为Linux／Java17验收。

首轮索引修复没有前端代码变更，未重跑前端构建及浏览器回归；后续浏览器检查见下节。真实MySQL、真实Redis、付费模型、公网、Windows及真实手机验收均未运行。

## 后续浏览器检查与预览服务修复

[修复PR的首次CI](https://github.com/5-bin/kaoyan-agent-platform/actions/runs/40085788767)已通过Linux／Java17的129项Java测试，以及Python、文档和前端生产构建。浏览器检查为145项通过、1项失败：笔记退出登录用例在等待被挂起的第2页成功响应时超时。

下载该次诊断包并核对trace：分页请求的网络终态为`net::ERR_ABORTED`，登录页发生完整文档请求，Vite客户端在同一页面再次连接；测试本身没有调用reload。由此判断开发态重载干扰了迟到响应测试。

Playwright服务入口改为`vite preview`，复用CI前序步骤已经生成的生产构建，不加载Vite开发客户端。README同步明确先构建再运行浏览器检查。保留原有迟到响应与账号隔离断言，不通过放宽等待时间或跳过用例来规避失败。

本轮本机重新执行`npm run build`通过，保留既有大chunk提示；随后使用全新Chrome上下文运行完整桌面／移动端浏览器回归，146项全部通过（2.1分钟），包含原退出登录失败用例。日志为`/private/tmp/kaoyan-ci-preview-build-20261024.log`和`/private/tmp/kaoyan-ci-preview-e2e-20261024.log`。未改动应用业务代码或放宽测试断言。

## 后续聊天链路断言修复

[第二轮CI](https://github.com/5-bin/kaoyan-agent-platform/actions/runs/40086739859)已通过Java129项、浏览器146项和15项真实HTTP／浏览器链路检查。连续聊天步骤随后失败：新增逐条引用支持度列表后，“线程共享地址空间，保留各自的栈。”同时出现在正文段落和核验列表中，旧的全页文本定位触发Playwright严格模式，匹配到2个元素。

`scripts/browser-chat.cjs`将回答断言限定在`.task-result .markdown`正文区域，仍核对首轮、追问和刷新后的第二条正文，不使用任意元素来代替目标正文。

本机后续实跑剩余链路，全部使用随机端口、隔离H2、Redis与模型替身、独立Chrome上下文：

| 检查 | 结果与本地报告 |
| --- | --- |
| 连续聊天、文档及重启恢复 | 11项通过；`.cache/ci-fix-chat-20261024-1846.json` |
| 学情助手、隐私与受控操作 | 17项通过；`.cache/ci-fix-learning-20261024-1846.json` |
| 题目管理浏览器链路 | 10项通过；`.cache/ci-fix-question-admin-20261024-1846.json` |

同时通过`node --check scripts/browser-chat.cjs`和`git diff --check`。临时服务结束后由脚本关闭；没有启动日常数据库或Redis，没有调用付费模型。最新完整Linux结果仍以修复PR的Checks为准。

## 手动笔记场景的异步完成边界

[第三轮CI](https://github.com/5-bin/kaoyan-agent-platform/actions/runs/40087360433)再次通过Java、146项浏览器检查及15项HTTP链路；聊天脚本在手动笔记的v2标题等待处超时。原日志没有区分保存后与重新打开后的两个相同等待点。

检查脚本发现：创建成功响应会先显示v1标题，而`save()`还要等待笔记列表并更新带`noteId`的路由；此时记录`page.url()`可能仍得到不含笔记ID的`/notes`。脚本现明确等待带ID的路由再记录重开地址，并在编辑后核对实际PUT返回200。另增阶段标记和失败截图，使保存、重开和历史版本错误可以区分；CI失败产物补充聊天日志及聊天／学情截图目录。

本机再次运行完整聊天链路11项通过，报告为`.cache/ci-fix-chat-route-20261024-1857.json`；脚本语法、文档与差异检查通过。该轮改动没有修改业务保存逻辑；Linux效果继续由最新PR检查核对。
