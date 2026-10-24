# 真实数据来源与使用边界（2026-10-24）

本清单对应日常库本轮接入，不把课程习题描述为408统考真题。原文快照用于版本核对，不执行其中的HTML脚本。

## 题目

44题均为OpenDSA已有习题的中文翻译，当前只覆盖数据结构。保留原正确答案，从原题干扰项中选取3项并调整顺序；不新增干扰项。原题存在多种条件变体时，在中文题干固定并说明所用变体。含重复正确选项、条件歧义或不足3个有效干扰项的候选没有导入。

上游许可与版权声明完整保存在[原文快照](../scripts/fixtures/real-opendsa-sources.json)的MIT-license.txt记录中。作者：Ville Karavirta、Cliff Shaffer及OpenDSA贡献者；[MIT许可](https://github.com/OpenDSA/OpenDSA/blob/master/MIT-license.txt)。逐题记录原文Git blob SHA，快照加载时重新计算校验；中文核对记录见[目录模块](../scripts/real_data_catalog.py)。这是本次代理执行的原题答案、语义与概念复核，不是教师人工审核或真实考生难度标定。

| 原题标识 | 知识点 | 官方项目原文 |
| --- | --- | --- |
| InssortMCQcostb | 直接插入排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/InssortMCQcostb.html) |
| InssortMCQcosta | 直接插入排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/InssortMCQcosta.html) |
| InssortMCQcomplex | 直接插入排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/InssortMCQcomplex.html) |
| InssortMCQsorted | 直接插入排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/InssortMCQsorted.html) |
| SelsortMCQcost | 简单选择排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/SelsortMCQcost.html) |
| SelsortMCQswaps | 简单选择排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/SelsortMCQswaps.html) |
| HeapsortMCQcost | 堆排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/HeapsortMCQcost.html) |
| HeapsortMCQspace | 堆排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/HeapsortMCQspace.html) |
| MergesortMCQcost | 归并排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/MergesortMCQcost.html) |
| MergesortMCQcomplex | 归并排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/MergesortMCQcomplex.html) |
| QuicksortMCQcosta | 快速排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/QuicksortMCQcosta.html) |
| QuicksortMCQcostb | 快速排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/QuicksortMCQcostb.html) |
| BubsortMCQcost | 冒泡排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/BubsortMCQcost.html) |
| ShellsortMCQ2 | 希尔排序 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/ShellsortMCQ2.html) |
| SortBoundMCQ1 | 问题复杂度上界 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Sorting/SortBoundMCQ1.html) |
| ListdsMCQpshpp | 栈 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/ListdsMCQpshpp.html) |
| ListdsMCQenqdq | 队列 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/ListdsMCQenqdq.html) |
| ListdsMCQrcrsn | 栈与递归 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/ListdsMCQrcrsn.html) |
| StackQMCQschrct | 栈 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/StackQMCQschrct.html) |
| ListdsMCQntlnr | 线性结构与树 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/ListdsMCQntlnr.html) |
| GAdjacentMCQ | 图的基本概念 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Graph/GAdjacentMCQ.html) |
| GcliqueMCQ | 团 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Graph/GcliqueMCQ.html) |
| GcycleMCQ | 无环图 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Graph/GcycleMCQ.html) |
| GdegreeMCQ | 顶点的度 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Graph/GdegreeMCQ.html) |
| GdigraphMCQ | 有向图 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Graph/GdigraphMCQ.html) |
| GsimppathMCQ | 简单路径 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Graph/GsimppathMCQ.html) |
| GsimpcycleMCQ | 简单环 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Graph/GsimpcycleMCQ.html) |
| HashMCQcollision | 散列冲突 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Hashing/HashMCQcollision.html) |
| HashMCQprobe | 探测序列 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Hashing/HashMCQprobe.html) |
| HfeatureMCQ | 二叉堆 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Binary/HfeatureMCQ.html) |
| HgreatestMCQ | 大根堆 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Binary/HgreatestMCQ.html) |
| HworstMCQ | 二叉堆 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Binary/HworstMCQ.html) |
| AlgAnlsMCQrelalgprb | 算法与问题 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/AlgAnal/AlgAnlsMCQrelalgprb.html) |
| AlgAnlsMCQsqlsrch | 顺序查找 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/AlgAnal/AlgAnlsMCQsqlsrch.html) |
| ThetaUpperMCQ | 渐近复杂度 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/AlgAnal/ThetaUpperMCQ.html) |
| ALMCQdelarb | 顺序表 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/ALMCQdelarb.html) |
| ALMCQinsarb | 顺序表 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/ALMCQinsarb.html) |
| LLMCQaccs | 单链表 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/LLMCQaccs.html) |
| LLMCQsuccelm | 链表存储 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/LLMCQsuccelm.html) |
| StackQMCQqrmv | 队列 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/StackQMCQqrmv.html) |
| StackQMCQsrmv | 栈 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/StackQMCQsrmv.html) |
| HashDelMCQ2 | 散列表删除 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/Hashing/HashDelMCQ2.html) |
| LLMCQfndelm | 链表查找 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/LLMCQfndelm.html) |
| LLMCQadv | 链表与顺序表 | [原文与版本](https://github.com/OpenDSA/OpenDSA/blob/master/Exercises/List/LLMCQadv.html) |

## 四科学习资料

16篇均为真实教材／教学讲义的中文节选整理，各科4篇，不是完整教材。每篇正文和数据库记录保留作者、原文位置、版本、获取日期和许可。英文来源明确说明为中文摘要；MIT资料不复制第三方图片。

| 科目 | 标题 | 作者与定位 | 原文 | 使用许可 |
| --- | --- | --- | --- | --- |
| 数据结构 | 栈的后进先出与基本操作 | 靳宇栋（krahets）与Hello算法贡献者；docs/chapter_stack_and_queue/stack.md | [原文](https://github.com/krahets/hello-algo/blob/main/docs/chapter_stack_and_queue/stack.md) | CC BY-NC-SA 4.0；中文摘要 |
| 数据结构 | 队列的先进先出与双端实现 | 靳宇栋（krahets）与Hello算法贡献者；docs/chapter_stack_and_queue/queue.md | [原文](https://github.com/krahets/hello-algo/blob/main/docs/chapter_stack_and_queue/queue.md) | CC BY-NC-SA 4.0；中文摘要 |
| 数据结构 | 二叉树的节点与层级术语 | 靳宇栋（krahets）与Hello算法贡献者；docs/chapter_tree/binary_tree.md | [原文](https://github.com/krahets/hello-algo/blob/main/docs/chapter_tree/binary_tree.md) | CC BY-NC-SA 4.0；中文摘要 |
| 数据结构 | 二分查找的有序前提与边界 | 靳宇栋（krahets）与Hello算法贡献者；docs/chapter_searching/binary_search.md | [原文](https://github.com/krahets/hello-algo/blob/main/docs/chapter_searching/binary_search.md) | CC BY-NC-SA 4.0；中文摘要 |
| 操作系统 | 虚拟内存、页表与访问权限 | Katrina LaCurts / MIT OCW；os-memory | [原文](https://ocw.mit.edu/courses/6-033-computer-system-engineering-spring-2018/pages/week-2/lecture-3-outline/) | CC BY-NC-SA 4.0；中文摘要 |
| 操作系统 | 有界缓冲区与互斥锁 | Katrina LaCurts / MIT OCW；os-locks | [原文](https://ocw.mit.edu/courses/6-033-computer-system-engineering-spring-2018/pages/week-3/lecture-4-outline/) | CC BY-NC-SA 4.0；中文摘要 |
| 操作系统 | 线程切换、条件变量与丢失唤醒 | Katrina LaCurts / MIT OCW；os-threads | [原文](https://ocw.mit.edu/courses/6-033-computer-system-engineering-spring-2018/pages/week-3/lecture-5-outline/) | CC BY-NC-SA 4.0；中文摘要 |
| 操作系统 | 虚拟机监控器与微内核 | Katrina LaCurts / MIT OCW；os-structure | [原文](https://ocw.mit.edu/courses/6-033-computer-system-engineering-spring-2018/pages/week-4/lecture-6-outline/) | CC BY-NC-SA 4.0；中文摘要 |
| 计算机组成原理 | 吞吐率、延迟与流水线性能 | Chris Terman / MIT OCW；co-7 | [原文](https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c7/c7s1/) | CC BY-NC-SA 4.0；中文摘要 |
| 计算机组成原理 | 存储程序与指令集体系结构 | Chris Terman / MIT OCW；co-9 | [原文](https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c9/c9s1/) | CC BY-NC-SA 4.0；中文摘要 |
| 计算机组成原理 | 存储层次、局部性与Cache | Chris Terman / MIT OCW；co-14 | [原文](https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c14/c14s1/) | CC BY-NC-SA 4.0；中文摘要 |
| 计算机组成原理 | 处理器流水线中的数据与控制冒险 | Chris Terman / MIT OCW；co-15 | [原文](https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c15/c15s1/) | CC BY-NC-SA 4.0；中文摘要 |
| 计算机网络 | 网络分层、协议与服务接口 | Larry Peterson、Bruce Davie及Systems Approach贡献者；foundation/architecture.rst | [原文](https://github.com/SystemsApproach/book/blob/master/foundation/architecture.rst) | CC BY 4.0；中文摘要 |
| 计算机网络 | 网络带宽、时延与带宽时延积 | Larry Peterson、Bruce Davie及Systems Approach贡献者；foundation/performance.rst | [原文](https://github.com/SystemsApproach/book/blob/master/foundation/performance.rst) | CC BY 4.0；中文摘要 |
| 计算机网络 | TCP可靠字节流、流量控制与拥塞控制 | Larry Peterson、Bruce Davie及Systems Approach贡献者；e2e/tcp.rst | [原文](https://github.com/SystemsApproach/book/blob/master/e2e/tcp.rst) | CC BY 4.0；中文摘要 |
| 计算机网络 | UDP端口与尽力交付 | Larry Peterson、Bruce Davie及Systems Approach贡献者；e2e/udp.rst | [原文](https://github.com/SystemsApproach/book/blob/master/e2e/udp.rst) | CC BY 4.0；中文摘要 |

[阅读资料原文快照](../scripts/fixtures/real-reading-sources.json)保存Git blob SHA或SHA-256，以便与中文摘要对照。[Hello算法许可](https://github.com/krahets/hello-algo/blob/main/LICENSE)、[MIT OCW许可](https://ocw.mit.edu/pages/privacy-and-terms-of-use/)、[Systems Approach许可](https://github.com/SystemsApproach/book/blob/master/LICENSE)分别适用，不把某个代码仓库的代码许可套到第三方教材上。

## 院校招生事实

保留本项目已有10校15专业的官方事实，详见[逐专业原始来源清单](feature-test-sources-2027.md)和[本次复核说明](../scripts/fixtures/real-schools-verification-20261024.json)。保留其原来源定位和专业字段，不复制官网整页到仓库，不收录人数、复试线、报录比或录取概率。

本次复核9校13专业：南京审计大学、中国科学院大学、中国传媒大学、北京航空航天大学、四川大学、燕山大学、郑州航空工业管理学院、浙江科技大学、安徽师范大学。北航使用正常公开目录POST查询；四川大学使用带2027参数的公开只读专业详情；浙江科技大学的专业和科目通过实际查看官方原图核对。郑州航院科目通过网页工具核对，学习方式沿用上轮章程依据。

华南师范大学官方2027目录入口本次可读，但两个动态专业详情本次403／不可访问。两条记录保留2026-10-23核验日期和证据，没有标记为2026-10-24重新核验。其余事实的本次获取记录及页面摘要在本机`.cache/real-data-source-check/`；不把动态入口可访问等同于专业详情复核完成。

## 未采用的内容

未直接复制商业题库、王道／天勤教材、论坛回忆版解析或只有代码许可的真题仓库。未获得清晰收录许可的408真题未导入。操作系统、组成原理、网络的正式可练习题量目前为0；没有用模型生成题补齐，也没有将其他科目题改标签。
