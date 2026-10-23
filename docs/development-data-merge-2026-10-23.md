# 日常开发库公共数据合并与启动

日期：2026-10-23。用户在确认日常库与独立库分开后明确要求“合并”。本次实际把同项目公共测试夹具补入本机`kaoyan_dev`，日常启动即可使用，不必改连独立库。

## 已合并的内容

| 数据 | 本次新增 | 日常库合并后总量 |
| --- | ---: | ---: |
| 院校 | 10所真实院校 | 16所，包含原6所名称带“测试虚构”的院校 |
| 专业 | 15条2027专业 | 27条，包含原12条虚构组合 |
| 题目 | 172题 | 188题 |
| 公共资料 | 4份可浏览短摘要 | 8份，包含原4份待审核资料 |

新增题目中160道为可练习原创功能测试题，四科各40道，每科简单16、中等16、困难8；另有4道待审、4道驳回、4道审核通过但停用样例。原16道待审题保持原状态。审核意见明确写入迁移来源和自动测试性质，审核人及审核时间为NULL，不冒充本库管理员的人工审核。题目不是历年真题，也不代表正式题库发布。

院校及专业来自[统一夹具](../scripts/fixtures/feature-2027-schools.json)，[来源清单](feature-test-sources-2027.md)保留原核验记录。本轮未重新抓取招生网站；人数、分数线仍为NULL。知识摘要沿用同项目原4份资料及原核验日期，不宣称重新完成人工内容审核。

没有复制独立库的账号、角色、密码、练习、错题、收藏、统计、任务或个人文档。登录日常环境时继续使用日常账号；`fixture_student_2027`等账号仍只属于独立环境。原有日常账号及个人记录已逐表计算摘要核对，全部保留。

本次补齐了当前代码依赖的`V12__assistant_privacy.sql`两张表；V10/V11原已存在。V12新表为空，没有预先代替用户授权外发数据。未执行V1或V2—V6种子，未修改既有业务表结构。

## Agent资料与环境

仓库新增[日常10校语料](../kaoyan-agent/knowledge/feature-2027-corpus.json)：15条专业、4条知识摘要，共19条，版本`rag-v1-0f32db2160a7daed`。根`.env`只增加`RAG_DATA`指向该文件；数据库仍是`kaoyan_dev`，模型开关、供应商配置、密钥及分类授权均未改变。

原`knowledge/corpus.json`保留作为三校基线。Python和Java链路测试已明确指定该基线，避免读取开发者本机语料而产生数量断言误报。日常配置使用词项检索，未切换Qdrant或建立向量索引；同一专业不会同时加入新旧两套院校摘要。

## 本机正常启动

先确保日常MySQL和Redis可用。从下列项目根目录开三个终端；本机已有依赖使用`.cache/chat-venv`，其他机器按[README](../README.md)安装依赖。合并任务没有启动或重启日常服务。

终端A，启动Agent：

```bash
cd /Users/bin/projects/ruanjiangongcheng/Projects/kaoyan-agent-platform-adaptation
cd kaoyan-agent
../.cache/chat-venv/bin/python -m uvicorn main:create_app --factory --host 127.0.0.1 --port 8001
```

终端B，加载可信本机配置后构建并启动Java：

```bash
cd /Users/bin/projects/ruanjiangongcheng/Projects/kaoyan-agent-platform-adaptation
set -a
source .env
set +a
export PYTHON_EXECUTABLE="$PWD/.cache/chat-venv/bin/python"
cd kaoyan-B
bash mvnw -B -ntp package
java -jar target/kaoyan-backend-1.0.0.jar
```

终端C，启动前端：

```bash
cd /Users/bin/projects/ruanjiangongcheng/Projects/kaoyan-agent-platform-adaptation/kaoyan-frontend
npm run dev
```

打开[正常项目页面](http://127.0.0.1:5173)，继续使用日常账号。在院校列表可看到新增真实院校；刷题页可选择四科和难度新建批次；条件推荐需档案年份2027并明确专业、学硕或专硕。选择“河北＋081200＋学硕”可找到燕山大学，“浙江＋085404＋专硕”可找到浙江科技大学。

若Java使用自定义端口，在终端B设置`PORT`，终端C设置相同地址的`API_PROXY_TARGET`；默认链路为5173 → 8080 → 8001。根目录及项目目录仍须对应本项目，不能进入旁边的旧工程。日常环境与15173独立环境此后各自保存修改，不自动同步。

## 导入脚本与恢复依据

[合并脚本](../scripts/merge-feature-data.py)直接读取仓库公共夹具，重现时不依赖独立库或其缓存。默认预览不连接数据库：

```bash
.cache/chat-venv/bin/python scripts/merge-feature-data.py

# 仅在获准写入本机日常开发库时使用：先备份再按自然键补缺。
.cache/chat-venv/bin/python scripts/merge-feature-data.py --apply --database kaoyan_dev
```

脚本只接受根`.env`明确配置的本机`kaoyan_dev`，拒绝数据源URL覆盖、自定义语料覆盖、向量模式及半完成V12结构。相同学校名、学校／专业／年份组合、题目来源定位、资料标题存在时保留，后续人工编辑和审核不会被重写。不会按独立库自增ID覆盖日常库记录，也不创建账号或映射审核人。

实际备份及执行证据位于本机私密目录：

```text
.cache/development-data-merge/20261023-114223-720712/
  before.sql           # 完整日常库备份
  before.env           # 改动前的本机配置，含私密值
  insert.sql           # 只新增公共数据的事务SQL
  report.json          # 新增ID、数量、V12状态及原记录校验
  verification.json    # 29项实际检查结果
```

目录权限700，以上文件权限600，不提交或分享备份。事务内插入失败会回滚；V12建表和文件配置属于分阶段操作，无法随插入事务一起回滚。若需撤销，先根据新增ID与后续引用核对，只撤回本次数据并恢复原`RAG_DATA`；不要直接覆盖已有后续作答，也不要为撤销而重跑V1。脚本不自动删除或整库恢复。

## 实际验证与限制

- 8项既有夹具边界测试通过；合并前校验201条公共记录计划、语料结构和无删除更新SQL。
- 实际新增10校、15专业、172题和4资料；原15张表的原有行摘要全部未变。重复执行同一插入SQL新增0条。
- 29项检查通过：真实日常MySQL数量、四科难度、审核／启停分布、关联和NULL字段；根配置实际加载19条新语料；Agent进程内HTTP验证河北学硕、浙江专硕及知识摘要来源。模型替身拒绝外部请求，实际模型调用为0。
- Java执行`bash mvnw -B -ntp verify`：82项通过，0失败、0错误、0跳过，后端重新打包成功；使用独立H2及临时Python链路，不修改日常库。日志：`.cache/development-data-merge/java-verify-20261023.log`。
- Python在进程环境传入新`RAG_DATA`的情况下执行pytest，126项通过；测试内部固定基线语料，验证不会继承开发者语料。保留1条既有TestClient依赖弃用提示。日志：`.cache/development-data-merge/python-verify-20261023.log`。

未运行：合并后的日常Java／Redis整站HTTP、浏览器页面、公网、真实手机、真实模型及Qdrant验证。进程内Agent检查不等于已启动日常服务。完整刷题草稿、提示辅助和结束批次仍是后续能力，数据合并不改变其实现状态。
