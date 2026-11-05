# 线上DeepSeek模型配置与验证

日期：2026-11-03。用户本轮明确要求“在服务器上帮我配置一下大模型，沿用本机配置”，据此替代此前暂不开启模型的决定。对象为现有中国香港实例 `i-j6cb4euf28b560hanyr7`，页面为[线上助手](https://47.83.150.142/tasks)。本轮已执行并生效。

## 生效配置与保留范围

只从当前项目本机根 `.env` 提取以下六项，通过私密文件传输；未复制整份本机环境文件。

| 配置 | 线上实际结果 |
| --- | --- |
| LLM_ENABLED | true |
| LLM_BASE_URL | https://api.deepseek.com |
| LLM_MODEL_MAIN | deepseek-flash |
| LLM_MODEL_ROUTER | deepseek-flash |
| LLM_THINKING_MODE | disabled |
| LLM_API_KEY | 已配置，与当前项目本机相同；不展示 |

逐项比较上述六项以外的所有解析配置，均保持一致。特别核对：`MAX_MODEL_CALLS_PER_DAY=20`、`QUOTA_EXEMPT_USERNAME`为空、`REGISTRATION_ENABLED=false`、`OSS_KEY_PREFIX=prod/`。未修改账号、隐私授权、任务额度、数据库或资料索引，也未重建发布包。Java按请求读取Agent当前供应商，无需重启Java。

全局模型开启仍需账号本人在对话“隐私”中同意当前供应商与相应个人数据类别；历史其他供应商授权不会自动转为DeepSeek授权。未替任何账号启用外发。

## 实际执行与验证

- 已先备份服务器 `/opt/kaoyan/.env`，保持原属主和0640权限；传输及操作目录0700，凭证、备份、执行日志0600。候选配置经逐项回读验证；重复配置及越界键的本机拒绝检查通过。
- 使用部署版本的 `core.model.ModelClient` 及真实HelloAgents适配层发起1次合成连接请求，内容仅为返回 `status=ok`，没有个人资料、历史或业务数据。请求预算为1，SDK无自动重试，响应通过Pydantic校验，客户端正常关闭。主模型与路由模型名称相同，此次实际调用主模型，不另增加路由请求。
- 真实请求耗时3.709秒，供应商用量为输入138、输出5、合计143 tokens；缓存命中0。此请求属于独立运维探测进程的1次预算，未创建账号任务，也未计入服务进程的日预算计数。未取得费用账单，不估算实际费用。
- 应用前只读查询任务及会话生成的RUNNING总数为0。通过部署进程锁应用配置，仅重启 `kaoyan-agent`；操作由独立瞬态systemd单元完成，退出码0。Java及Nginx继续active。
- 读取Agent实际进程环境，六项均与传输配置一致，API凭证只作内存比较、不输出。环境文件属主、权限及其余配置均保持一致。
- Agent健康：`modelEnabled=true`、`provider=https://api.deepseek.com`、`status=ok`；资料版本仍为 `rag-v1-a476bf509577d904`，检索仍为lexical，招生MCP为READY。
- 使用正常TLS证书校验访问公网首页HTTP 200；匿名注册配置返回 `registrationEnabled=false`。

## 私密证据与回退

服务器私密目录：`/root/kaoyan-llm-config-20261103/`。

- `env.before`：本轮修改前环境文件；`state.json`记录原配置指纹及权限。
- `probe.json`：合成真实调用的耗时及用量；`result.json`、`verification.json`和`apply.log`：应用与核对结果，不输出凭证。
- `configure.py`：本轮绑定该实例、该发布目录的配置工具，变更使用 `/run/lock/kaoyan-upgrade.lock`。`config.json`及传输包含凭证，仅在私密目录保存，不公开或提交。
- 应用或启动失败时工具恢复原环境并重启Agent。本轮应用成功，未实际触发故障回退。后续需要回退时，可经授权运行以下命令；工具会拒绝覆盖应用后被其他操作更改的环境文件，不应绕过保护直接复制整份旧环境。

```bash
/opt/kaoyan-releases/kaoyan-release-20261103-oss-upload/.venv/bin/python /root/kaoyan-llm-config-20261103/configure.py restore
```

本机一次性工具及私密传输材料位于忽略目录 `.cache/server-llm-20261103/`。没有修改业务源码，因此Java verify、Python业务pytest及前端生产构建未运行。登录后整站真实业务、个人学习数据外发、SSE、失败回退注入及模型领域效果验收未运行；一次合成连接成功不代表上述业务均已验收。未提交或推送代码。
