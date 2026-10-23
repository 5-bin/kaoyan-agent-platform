# PR #13 CI 回归脚本修复

## 失败与修复

- [首次失败](https://github.com/5-bin/kaoyan-agent-platform/actions/runs/39935016354)：连续删除会话时确认框退出动画未结束，匹配到两个删除按钮。已在`3e74a14`增加关闭、唯一性和可见性等待；[后续运行](https://github.com/5-bin/kaoyan-agent-platform/actions/runs/39936276575)完整100项浏览器测试通过。
- 后续HTTP步骤等待旧模拟答案超时：旧脚本误把独立任务验证改为进入新聊天入口。恢复在任务历史中查看真实Java→Python保存的结果；连续聊天继续由专门脚本验证。重启检查按隔离环境唯一RUNNING任务识别，不再读取公开响应已移除的私有`inputPayload`。
- 本机预检发现学情脚本仍等待“确定”，当前清除会话复用“删除对话”确认框。改为按弹窗及“删除”按钮定位，并等待关闭。
- 本机预检发现题目管理脚本请求100题，超过当前50题上限。改为`count=1, questionIds=[id]`明确选择本测试发布的题目，保持判分、停用、恢复及历史快照检查。

## 本机实际验证

使用已有构建产物、隔离Chrome上下文、临时H2文件库、Redis替身及受控模型；各脚本结束后清理本次子进程，不修改日常数据库或用户浏览器资料。

| 验证 | 结果 | 本机忽略目录日志 |
| --- | --- | --- |
| 删除会话浏览器用例 | 桌面及390×844模拟手机宽度14项通过 | `.cache/ci-fix-delete-verified.log` |
| `smoke-current.py --browser-check` | 15项通过，含真实HTTP、页面分页、历史结果、账号隔离、重启与失败保存 | `.cache/ci-fix-http-final.log` |
| `smoke-chat.py` | 11项通过 | `.cache/ci-fix-chat.log` |
| `smoke-chat.py --learning` | 17项通过 | `.cache/ci-fix-learning-final.log` |
| `smoke-question-admin.py` | 桌面及模拟手机宽度10项通过 | `.cache/ci-fix-admin-final.log` |

本轮脚本修复后未重新运行Java/Python单元测试及前端构建；这些步骤在上述后续远端运行中已通过。远端完整CI结果须以本次修复提交的新运行记录为准。不代表真实MySQL、Redis服务、外部模型、真实手机或公网验收。
