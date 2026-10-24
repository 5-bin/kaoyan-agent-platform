# CI题目索引冷启动重试修复

日期：2026-10-24。基线：`7efc315`。范围仅为隔离聊天集成测试及其Python夹具，无生产接口、限额、数据库或模型配置变更。

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

前端代码未变，本轮前端构建及浏览器回归未运行；真实MySQL、真实Redis、付费模型、公网、Windows及真实手机验收均未运行。
