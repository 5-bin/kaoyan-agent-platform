# 当前Ubuntu服务器正式更新准备

日期：2026-11-03。目标为用户服务器上的现有 `/opt/kaoyan`，新版程序包在 `/opt/kaoyan-releases/kaoyan-release-20261102-233824-8e34094`。本文及 `scripts/activate-server-release.py` 仅支持已经核对过的单实例服务和Nginx布局，不是通用初始化／部署系统，不执行V1或旧种子。

## 已有依据

用户已回传 `/root/kaoyan-data-rehearsal-20261103-005207/report.json`：原15条专业复用、新增782条，备份恢复及回滚通过；计划SHA为 `e9b56eaaaaef5c24f7421e7d66f259401d3281319275b516a2e7f6f9a4bc76df`。原程序仍运行，生产迁移与写入未执行。完整历史见[资料预演记录](deployment-data-verification-2026-11-03.md)。

用户回传：两个服务均为kaoyan用户，使用 `/opt/kaoyan/.env`，无现有drop-in、RootDirectory或ProtectSystem限制；正式账号已能导入新版框架。现有LLM_ENABLED=false、RAG_BACKEND=lexical；RAG_DATA及来源策略指向旧目录中现有受控文件，均保留。三个默认模型／索引缓存目录尚不存在。ONNX遥测标识缓存告警未阻止导入，不将其当成模型权重已经就绪。

## 工具与影响

默认调用只读校验，不停服、不迁移：

```bash
新版目录/.venv/bin/python /root/activate-server-release.py \
  --release-root /opt/kaoyan-releases/kaoyan-release-20261102-233824-8e34094 \
  --rehearsal /root/kaoyan-data-rehearsal-20261103-005207 \
  --expected-plan e9b56eaaaaef5c24f7421e7d66f259401d3281319275b516a2e7f6f9a4bc76df \
  --output /root/新的更新输出目录
```

用户了解下述影响后，显式添加 `--activate` 才进入正式更新。可添加 `--enable-learning` 启用V13诊断／学情，`--enable-admission-links` 启用只读招生链接MCP。服务器已有显式关闭配置时，启用选项会停止而非覆盖用户偏好。LLM继续为false，工具不配置密钥、不启用模型、不请求供应商，也不下载Embedding权重。

1. 核对部署文件清单、固定版本资料工具、公共资料SHA、已预演计划及备份SHA，并重新只读比对当前库。状态改变则停止。
2. 备份Nginx，临时让API返回503；确认维护生效后只停止项目Java和Python，不停止MySQL／Redis。HTTP跳转与ACME验证目录保留。
3. 在停服后取得新的完整备份，并再次在独立恢复库验证同一计划；仅对实际业务库执行已确认的V13/V14，再提交带行锁和数量／指纹保护的公共资料事务。账号和个人记录逐行指纹必须不变。
4. 新版.env只链接到已有受保护的服务器.env，不复制本机凭证；创建同项目共享缓存目录，由kaoyan用户持有。添加两个专用systemd drop-in，将WorkingDirectory和ExecStart指向新版；原unit和旧程序保留。
5. 仅在维护状态中启动单Python实例和Java，核对健康、实际启动路径、模型仍关闭；选用招生链接时检查MCP READY。GET健康及未认证GET探测不创建任务或写账号。
6. 只切换HTTPS静态根目录，验证首页200及内容哈希，再解除API维护。HTTP ACME根目录、证书路径、内部端口及原代理配置保留。环回HTTPS校验临时允许旧过期证书，探测禁止重定向，不能据此声称公网证书有效。

正式范围：新增111校、782条专业、360题、20篇资料、59条题目版本、1594条指标；更新已预演的5所学校省份／层次字段；复用已有记录及编号、许可说明和备注。V13/V14为独立提交DDL，不能用事务回滚它们。

## 回退边界

失败时恢复旧服务及Nginx配置，删除本次创建且内容仍一致的两个drop-in；不会删除已有程序、账号、个人记录、已成功提交的公共资料或新增表。若旧服务不能恢复，则保留API维护状态并要求人工处理。不会自动重跑V1、清空库、恢复整库覆盖后续记录或删除索引。新的完整备份、配置原件、命令诊断及activation-result.json保存在指定0700私密目录。

因此“程序回退”不等于“数据库回到更新前”。实际需要数据库恢复时，须另行确认维护状态、备份及恢复影响。DDL或数据提交失败后不盲目重复执行，先依据当前表和结果报告处理。

## 实际验证与未运行

- 数据规则pytest15项（7个子案例）通过；切换测试11项通过，覆盖维护在先、失败回退、默认只读、旧配置保留、不清除已提交数据、旧服务恢复失败继续维护，以及环回HTTP禁止重定向。
- 原资料预演的完整CLI已在独立MySQL验证。新增正式切换工具的data阶段也在独立临时MySQL中执行，重新备份恢复、V13/V14、资料事务、个人记录保护及最终121校／797专业／404题／36篇资料／59版本／1594指标通过；原题许可及专业备注不变，旧SQL重复执行拒绝。报告为忽略目录 `.cache/deployment/server-activation-data-verification-20261103.json`，不连接本机业务库或服务器。
- 首次正式更新前的本机切换测试使用模拟服务，不扩大为原生服务验收；随后的真实服务器状态见下一节。公网证书、自动续期、本地Embedding权重及登录后的业务验收均未完成。

## 正式更新后的实际状态与修复

用户回传 `/root/kaoyan-activation-20261103-013209/activation-result.json`：V13/V14及公共资料已提交，个人表指纹不变，数量为121校、797专业、404题、36篇资料、59题目版本和1594指标。新服务启动后，工具错误地用 `GET /api/auth/login` 判断Java就绪；该接口只支持POST，项目异常处理将其返回500，造成误判。工具回退到旧版服务时沿用同一错误检查，因而未自动解除API维护；旧版Java/Python进程实际运行。

用户随后按指示恢复备份的Nginx配置。重载立即检查仍返回503，之后助手外网复查 `/api/_deployment_probe` 返回401，表明旧版API已恢复响应；HTTPS证书仍过期。不得再次执行首次资料导入方案。

切换工具现改用受保护的 `GET /api/_deployment_probe`，严格要求401，并增加 `--committed-activation` 模式。该模式核对先前提交及个人记录保护结果，确认当前来源和服务器资料、表结构及数量一致，停服后重新备份恢复和检查幂等；生产库不再执行迁移或资料写入，然后才切换程序。失败仍仅回退程序，保留数据库。切换与资料规则pytest共29项通过；使用独立MySQL验证已经提交后的重试分支重新备份、恢复并保持所有表指纹不变，见 `.cache/deployment/server-activation-reuse-verification-20261103.json`。真实服务器的重试切换和后续证书／页面验收尚未运行。

### 修复后服务器程序切换

用户回传修复后的正式切换成功，`dataAlreadyCommitted=true`，各新增条目及学校更新数为0，未重复迁移或导入；公开数据数量为121校、797条专业、404题、36篇资料、59个题目版本和1594条指标。报告显示个人记录保留、`servicesSwitched=true`，私密备份及回退记录位于 `/root/kaoyan-activation-20261103-014131`。诊断／学情及只读招生链接开关随服务启用，模型仍关闭。

助手随后从公网读取新首页，内容SHA256为 `fc00a28859dd26e08d7231b9ce4fabeb70cf85203f7a75aafda61c7482cc59c6`，与本地部署包的首页一致；未认证API探测返回401。此处仅为静态入口和认证边界检查，使用了针对过期证书的临时验证豁免；不代表HTTPS证书有效、登录业务或模型功能通过。证书更新、自动续期、Embedding权重及登录后的业务验收仍待完成。

### 新公网IP证书

用户随后回传Certbot已为 `47.83.150.142` 签发新证书，证书备份位于 `/root/kaoyan-cert-backup.TDCCCq`，证书到期时间为2026-11-09 08:45:27 UTC（北京时间16:45:27），SAN包含该IP。续期timer已列出下次执行时间；实际自动续期尚未验证。助手以正常证书校验从公网访问首页得到HTTP 200，未认证API返回401。Certbot显示的hook stderr中Nginx配置检查均为successful；公网验证已确认当前证书可用。自动续期流程、Embedding权重及登录后业务仍待检查。

用户进一步回传续期timer为enabled/active，webroot配置一致，无证书级pre/post钩子和pre/post目录钩子；证书级deploy钩子不等于本轮命令中的预期字符串，deploy目录有一个可执行钩子，其内容及续期模拟结果仍待核查。用户按命令以kaoyan账号下载公开模型 `BAAI/bge-small-zh-v1.5`，下载约95.2MB，本地512维编码通过，未调用付费LLM或读取业务数据库；题目索引构建及页面语义检索尚未验收。ONNX标识写入告警后编码成功，不宣称该告警已消除。

用户随后回传全局deploy钩子 `kaoyan-nginx-reload` 的命令均属于已识别的简单Nginx检查／重载命令，并包含重载；`certbot renew --cert-name kaoyan-ip --dry-run` 模拟续期成功。Certbot默认不在dry-run执行deploy钩子，因此该结果验证续期挑战，不证明定时器未来实际运行及重载已被再次执行。此前真实签发后公网已验证有效证书；首次定时续期与登录后业务验收仍待观察。用户明确选择暂不开启真实大模型，保留服务端 `LLM_ENABLED=false`。

## V15增量上线（2026-11-03）

本轮用户明确授权实施增量升级。旧版本为 `/opt/kaoyan-releases/kaoyan-release-20261102-233824-8e34094`，新版本为 `/opt/kaoyan-releases/kaoyan-release-20261103-local-sync`。此前直接连接服务器核实三项服务均运行，Java包及首页与本地构建一致；V15尚未在生产执行。

独立工具 `scripts/upgrade-server-release.py` 复用基础切换组件，默认只读，要求 `--current-release`、`--release-root`、`--rehearsal`、`--data-helper`、`--manifest`、`--expected-plan`、`--expected-manifest` 和全新的 `--output`；显式 `--activate` 才执行。保留已有drop-in中非路径配置，只替换旧版本路径；比较配置原件并持有进程锁，失败恢复其原始内容。生产数据库只执行哈希绑定的V15，所有表按迁移前列比较指纹，公共资料不写入。完整V15只核对并跳过，部分V15或其他待执行迁移拒绝。所有输出和备份留在0700目录。

本轮运维pytest 84项（另含7个子案例）通过；真实独立MySQL 8.4验证新备份恢复、V15执行、CHECK拒绝非法值、全部原字段指纹保持及已存在V15跳过，报告 `.cache/deployment/v15-upgrade-verification-20261103.json`。首次隔离验证发现MySQL的CHECK元数据使用转义引号，已修正并覆盖回归；首次本机MySQL沙箱初始化失败，随后在获批的独立socket实例完成验证，不连接本机日常库。

可信清单来自原本地发布资料、当前源码及构建，包含165个运行文件，SHA256为 `9d5c61d392bd88de3a966ce2a7dfd8f2c27e52b0e73edb152f3a2a23fe3cdd4d`。前次系统tar上传的前端含macOS元数据文件，已将该暂存dist保留为 `dist.with-macos-metadata`，使用无扩展元数据的新包替换待上线静态目录；服务器清单逐文件通过，旧版线上未因此改变。

独立MySQL及服务器只读预检通过后，以瞬态systemd服务 `kaoyan-upgrade-20261103-live` 执行，避免客户端断开中断迁移或回退；日志 `/root/kaoyan-upgrade-20261103-live.log`，输出 `/root/kaoyan-upgrade-20261103-live`。最终状态及公网验收在本节后续记录，不以启动升级进程视为上线成功。

### 本次直接执行结果

2026-11-03，助手通过已配置Workbench CLI直接执行并核对：瞬态升级服务退出码0，`activation-result.json` 为 `status=SUCCESS`、`v15Verified=true`、`schemaApplied=true`、`originalRowsPreserved=true`、`publicWrites=false`、`servicesSwitched=true`。生产新备份位于 `/root/kaoyan-upgrade-20261103-live/database/server-before.sql`，SHA256为 `3a2da9b3e75479feccf2a34a66cf2e32b834a894a113d1f89e439bd675f02e03`；同目录保留已恢复预演报告，输出根目录保留原Nginx、两个原drop-in及其权限／属主元数据。未执行公共资料事务，V15新列回读全部为空。

上线后Java、Python、Nginx均active，两个服务的实际WorkingDirectory均指向新版本。Python健康为ok，审核资料版本仍为 `rag-v1-a476bf509577d904`、词项检索、模型关闭，招生MCP为READY。数据库回读121校、797专业、404题、36篇资料、76个题目版本、1594条指标；76是本次库的实际总量，不把公共资料导出快照的59个版本当成当前全库数量。迁移在重启前已按所有表的原字段指纹验证无数据变化。

公网以正常TLS校验访问 `https://47.83.150.142/` 返回200，首页SHA256为 `6bb790935e9dd7bfcc2d0920dd4b39903636e53cd2de9c49dca706079de2852e`，与本地新版一致；首页引用的JS/CSS及新版个人档案JS逐字节哈希相符，未认证API探测为401。未使用证书校验豁免。公共探测报告 `.cache/deployment/v15-upgrade-public-verification-20261103.json`。

本轮未重复运行此前已经通过且未再修改的业务三端验证（Python981项、Java230项中2项跳过、前端生产构建）；运维验证单独如上。登录后档案保存、真实模型、真实手机和业务全流程未运行；没有创建线上测试账号或复制本机模拟作答。旧程序目录、服务器凭证、公共资料与共享索引保留，不自动撤销已提交V15。
