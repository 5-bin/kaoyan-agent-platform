"""Reviewed translations of existing OpenDSA exercises; never generates questions.

Each tuple translates the original solution and three original distractors, in
that order. Rendering rotates these four entries without inventing distractors.
Source snapshots retain upstream Git blob hashes and the upstream MIT notice.
"""
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DATE = '2026-10-24'
SOURCE_NAME = 'OpenDSA课程习题（中文翻译）'
SUBJECTS = ('数据结构', '操作系统', '计算机组成原理', '计算机网络')

# path, knowledge point, translated stem, solution + original distractors,
# independently checked explanation. A brace alternative is fixed explicitly.
TRANSLATIONS = [
('Sorting/InssortMCQcostb','直接插入排序','直接插入排序处理含n条记录的数组时，最好情况时间复杂度是什么？',['Θ(n)','Θ(n²)','Θ(log n)','Θ(n log n)'],'输入已经有序时，每次只需一次失败比较；总比较次数与n成正比。'),
('Sorting/InssortMCQcosta','直接插入排序','直接插入排序处理含n条记录的数组时，最坏情况时间复杂度是什么？',['Θ(n²)','Θ(n)','Θ(log n)','Θ(n log n)'],'逆序输入时依次移动1至n−1条记录，求和为n(n−1)/2。原题的平均／最坏情况变体本次固定为最坏情况。'),
('Sorting/InssortMCQcomplex','直接插入排序','直接插入排序在哪些情况下具有相同的时间复杂度增长阶？',['仅最坏情况与平均情况','仅最坏情况与最好情况','仅最好情况与平均情况','最坏、平均、最好情况均相同'],'通常实现的平均和最坏情况均为二次阶，已排序输入的最好情况为线性阶。'),
('Sorting/InssortMCQsorted','直接插入排序','当输入数组已经排序时，直接插入排序的运行时间复杂度是什么？',['Θ(n)','Θ(n²)','Θ(log n)','Θ(n log n)'],'每轮内层比较立即结束，n−1轮的开销是线性的。'),
('Sorting/SelsortMCQcost','简单选择排序','简单选择排序处理含n条记录的数组时，最坏情况时间复杂度是什么？',['Θ(n²)','Θ(n)','Θ(log n)','Θ(n log n)'],'每轮扫描剩余区间选择最小值，共比较n(n−1)/2次，与初始顺序无关。原题三种情况变体固定为最坏情况。'),
('Sorting/SelsortMCQswaps','简单选择排序','按原课程的实现，即使当前位置已正确也执行交换，选择排序最坏情况下的交换总次数最接近哪个值？',['n','n²/2','n²','n log n'],'每轮至多执行一次交换，n−1轮的交换次数最接近n。题干保留原实现包含原位交换的条件。'),
('Sorting/HeapsortMCQcost','堆排序','堆排序处理含n条记录且关键字互异的数组时，最坏情况时间复杂度是什么？',['Θ(n log n)','Θ(n)','Θ(log n)','Θ(n²)'],'建堆为线性阶；反复移出堆顶并调整的总开销为n log n阶。原题情况变体固定为最坏情况。'),
('Sorting/HeapsortMCQspace','堆排序','除保存记录的数组外，原地堆排序需要多少辅助空间？',['Θ(1)','Θ(log n)','Θ(n)','Θ(n²)'],'采用原课程迭代调整的原地堆排序，只需常数个临时变量。'),
('Sorting/MergesortMCQcost','归并排序','归并排序处理含n条记录的数组时，最坏情况时间复杂度是什么？',['Θ(n log n)','Θ(n)','Θ(log n)','Θ(n²)'],'每层归并处理n条记录，划分层数为log n阶。原题三种情况变体固定为最坏情况。'),
('Sorting/MergesortMCQcomplex','归并排序','按原课程的归并排序实现，哪些情况下时间复杂度相同？',['最坏、平均和最好情况','最坏情况与最好情况','最好情况与平均情况','最坏情况与平均情况'],'标准归并排序无论输入次序如何，都执行相同层次的划分和归并，总体为n log n阶；仅列两种情况并未完整回答原题。'),
('Sorting/QuicksortMCQcosta','快速排序','快速排序处理含n个元素的数组时，最坏情况时间复杂度是什么？',['Θ(n²)','Θ(n)','Θ(log n)','Θ(n log n)'],'若枢轴反复将区间分为0和n−1两部分，划分成本求和为二次阶。'),
('Sorting/QuicksortMCQcostb','快速排序','快速排序处理含n个元素的数组时，最好情况时间复杂度是什么？',['Θ(n log n)','Θ(n)','Θ(log n)','Θ(n²)'],'每次枢轴将区间近似对半划分，每层线性开销、对数层数。原题最好／平均变体固定为最好情况。'),
('Sorting/BubsortMCQcost','冒泡排序','原课程所示没有提前退出优化的冒泡排序，处理n条记录时最好情况时间复杂度是什么？',['Θ(n²)','Θ(n)','Θ(log n)','Θ(n log n)'],'该实现仍逐轮比较所有相邻位置，比较总数为n(n−1)/2。不能把带提前退出标志的优化实现结论套到本题。'),
('Sorting/ShellsortMCQ2','希尔排序','希尔排序最有利的输入是哪一种？',['已经排序的数组，因为各子序列可在线性时间内完成插入排序','逆序数组，因为所有子序列都能在线性时间内排序','顺序不太有序也不太无序的随机数组，这样可以保持均衡','输入无关紧要，同样大小的输入成本总是相同'],'原课程用插入排序处理增量子序列。有序数组的各个子序列也有序，因此插入排序的移动成本最低。'),
('Sorting/SortBoundMCQ1','问题复杂度上界','一个问题的上界按原课程定义为哪一项？',['目前已知解决该问题的最好算法的成本','目前已知解决该问题的最差算法的成本','与该问题的下界相同','该问题最坏输入的成本'],'问题的上界由一个已知可行算法给出；比较已知算法时取最好的上界。不要混淆问题的界与某算法的最坏输入。'),
('List/ListdsMCQpshpp','栈','术语push和pop与哪种数据结构关联？',['栈','队列','数组','线性表'],'push与pop是栈的入栈和出栈操作。'),
('List/ListdsMCQenqdq','队列','术语enqueue和dequeue与哪种数据结构关联？',['队列','栈','数组','线性表'],'enqueue与dequeue分别表示队列入队和出队。'),
('List/ListdsMCQrcrsn','栈与递归','实现递归调用通常使用哪种数据结构？',['栈','队列','顺序表','链表'],'活动调用的现场按后进先出的顺序恢复，通常由调用栈保存。'),
('List/StackQMCQschrct','栈','下列哪项最能描述栈的行为？',['后进先出','先进先出','先来先服务','及时处理'],'栈的插入和删除均在栈顶进行，后入栈的元素先出栈。'),
('List/ListdsMCQntlnr','线性结构与树','下列哪一种不是线性数据结构？',['树','队列','顺序表','链表'],'树描述分支层级关系，不满足线性结构的一对一前驱后继关系。'),
('Graph/GAdjacentMCQ','图的基本概念','若顶点Q和K之间有一条边相连，应如何描述它们的关系？',['Q和K相邻','Q和K关联','Q和K不安全','Q和K孤立'],'边与其端点之间称关联；由边连接的两个顶点之间称相邻。'),
('Graph/GcliqueMCQ','团','给定图的顶点子集S，若S中任意两个不同顶点之间都有边相连，S构成什么？',['团','连通分量','有向图','有向无环图'],'团是两两相邻的顶点集合；连通分量只要求存在路径，不要求两两直接连边。'),
('Graph/GcycleMCQ','无环图','不含环的图称为什么？',['无环图','无向图','有向图','简单图'],'无环直接描述没有环；有向性与是否含环是不同属性。'),
('Graph/GdegreeMCQ','顶点的度','与某顶点关联的边的数量称为该顶点的什么？',['度','计数','编号','大小'],'原题讨论不涉及自环的基本图；与顶点关联的边数称为度。'),
('Graph/GdigraphMCQ','有向图','英文digraph指哪种图？',['有向图','无向图','连通分量','有向无环图'],'digraph是directed graph的简称，并不额外要求无环。'),
('Graph/GsimppathMCQ','简单路径','简单路径满足哪个条件？',['路径上的顶点互不相同','只要路径长度小于5，就允许重复顶点','只要没有重复边，就允许重复顶点','除起点与终点相同外，其余顶点互不相同'],'原课程定义简单路径的所有顶点互异；首尾相同且其余互异描述简单环。'),
('Graph/GsimpcycleMCQ','简单环','简单环满足哪个条件？',['除起点与终点相同外，其余顶点互不相同','只要路径长度小于5，就允许重复顶点','只要没有重复边，就允许重复顶点','所有顶点互不相同'],'环需要首尾闭合；简单环在此之外不重复顶点。'),
('Hashing/HashMCQcollision','散列冲突','下列哪项最准确地定义散列表中的冲突？',['关键字不同的两条记录具有相同散列值','两条记录除关键字外完全相同','两条记录的关键字相同','两条记录的关键字和散列值都相同'],'散列冲突发生在不同关键字被映射到同一个槽位。'),
('Hashing/HashMCQprobe','探测序列','下列哪项最准确地定义散列表中的探测序列？',['冲突处理时访问散列表槽位的顺序','散列函数的别称','散列函数访问散列表槽位的顺序','冲突处理的别称'],'探测序列属于冲突处理，规定当前位置无法使用时依次检查哪些槽位。'),
('Binary/HfeatureMCQ','二叉堆','堆具备哪项性质，使它可以高效地用数组实现？',['堆是完全二叉树','堆是二叉树','堆是二叉搜索树','堆是满二叉树'],'完全二叉树的层序位置连续，可以直接通过数组下标确定父子位置。'),
('Binary/HgreatestMCQ','大根堆','按原课程从0开始的数组下标约定，含n个元素的大根堆中最大元素位于哪里？',['0','n−1','n+1','n'],'大根堆的最大元素位于根节点，根的数组下标为0。'),
('Binary/HworstMCQ','二叉堆','关于二叉堆操作的最坏时间，下列哪项正确？',['插入和删除都优于线性时间','插入优于线性时间，但删除不是','删除优于线性时间，但插入不是','插入和删除都不优于线性时间'],'插入上滤和删除后的调整均最多沿树高移动；完全二叉树的高度为log n阶。'),
('AlgAnal/AlgAnlsMCQrelalgprb','算法与问题','关于算法与问题的关系，下列哪项正确？',['问题是输入到输出的映射，可能存在多种算法实现该映射','问题是输入到输出的固定映射，因此只有一种正确计算方法','算法是问题的另一种称呼','问题是操作步骤，算法是问题的解'],'同一输入输出要求可由不同过程完成；固定映射不意味着算法唯一。'),
('AlgAnal/AlgAnlsMCQsqlsrch','顺序查找','对固定长度的数组进行顺序查找时，最好情况在什么时候发生？',['查找目标接近数组前端','数组很小','算法实现得很高效','待查关键字很小'],'顺序查找从前向后检查，首个位置命中时只需一次比较。最好情况比较的是固定输入规模下的排列或位置。'),
('AlgAnal/ThetaUpperMCQ','渐近复杂度','若已知算法X的平均情况时间复杂度为Θ(n)，其最紧的渐近上界是什么？',['平均情况下为O(n)','平均情况下为O(n)或更大，但没有足够信息细化','平均情况下为O(n)或更小，但没有足够信息细化','没有足够信息作出判断'],'Θ(n)同时给出了线性阶的渐近上界与下界，因此最紧上界可确定为O(n)。'),
('List/ALMCQdelarb','顺序表','对于基于数组实现的线性表，在任意位置i删除元素的平均时间复杂度是什么？',['Θ(n)时间','Θ(1)时间','Θ(log n)时间','Θ(n log n)时间'],'为保持连续存储和元素次序，删除后需移动后续元素，平均移动数量与表长成正比。'),
('List/ALMCQinsarb','顺序表','对于基于数组实现的线性表，在任意位置i插入新元素的平均时间复杂度是什么？',['Θ(n)时间','Θ(1)时间','Θ(log n)时间','Θ(n log n)时间'],'为给新元素腾出位置，需把后续元素依次后移，平均成本为线性阶。'),
('List/LLMCQaccs','单链表','从单链表表头访问位置i的节点，需要怎样做？',['访问它的所有前驱节点','只需要一步','只需要两步','访问它的所有后继节点'],'单链表不支持按位置直接寻址，必须沿next指针从表头向目标移动。'),
('List/LLMCQsuccelm','链表存储','链表中逻辑相邻的元素在内存中的位置有什么要求？',['不要求占据连续空间','必须占据连续空间','必须不占据连续空间','以上均不正确'],'链表通过指针或链接表示逻辑次序，既可能连续也可能不连续，不要求物理相邻。'),
('List/StackQMCQqrmv','队列','依次将字符D、C、B、A入队，再逐个出队，出队顺序是什么？',['DCBA','ABCD','ABDC','DCAB'],'队列先进先出，出队顺序与入队顺序一致。'),
('List/StackQMCQsrmv','栈','依次将字符D、C、B、A入栈，再逐个出栈，出栈顺序是什么？',['ABCD','ABDC','DCAB','DCBA'],'栈后进先出，最后入栈的A最先出栈。'),
('Hashing/HashDelMCQ2','散列表删除','散列表中用于标识某槽位的记录已被删除的特殊标记称为什么？',['墓碑标记（tombstone）','旗标（flag）','哨兵（原选项拼写Sentinal）','墓石（gravestone）'],'墓碑标记使探测搜索不会在曾经占用的槽位提前终止，并允许后续插入复用槽位。'),
('List/LLMCQfndelm','链表查找','在含n个节点的链表中查找值为X的元素，最坏需要访问多少节点？',['n个节点','2个节点','log n个节点','1个节点'],'目标位于末尾或不存在时，必须遍历所有n个节点。'),
('List/LLMCQadv','链表与顺序表','相比基于数组的线性表，链表的一项优势是什么？',['易于扩展','任意位置的访问成本低','查找速度最优','没有额外存储开销'],'链表可以逐节点分配空间，不要求扩展连续大块内存；仍需指针开销且不支持常数时间的任意位置访问。'),
]


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value))).strip()


def source_parts(source):
    raw = source['content']
    actual = hashlib.sha1(f'blob {len(raw.encode())}\0'.encode() + raw.encode()).hexdigest()
    if actual != source['sha']:
        raise ValueError('upstream snapshot hash mismatch: ' + source['path'])
    question = re.search(r'<p class="question">(.*?)</p>', raw, re.S)
    solution = re.search(r'<(?:div|p) class="solution">(.*?)</(?:div|p)>', raw, re.S)
    choices = re.search(r'<ul class="choices"[^>]*>(.*?)</ul>', raw, re.S)
    if not all((question, solution, choices)) or '<var' in raw or '<img' in raw:
        raise ValueError('unsupported source question: ' + source['path'])
    correct = clean(solution[1])
    wrong = [clean(x) for x in re.findall(r'<li[^>]*>(.*?)</li>', choices[1], re.S)]
    # Original Khan exercises can supply more distractors than are displayed.
    # Never import an option equal to the answer, nor add a new distractor.
    wrong = list(dict.fromkeys(x for x in wrong if x != correct))
    if len(wrong) < 3:
        raise ValueError('fewer than three original distractors')
    return clean(question[1]), [correct, *wrong[:3]]


def questions():
    sources = json.loads((ROOT/'scripts/fixtures/real-opendsa-sources.json').read_text())
    files = {f['path']: f for f in sources['files']}
    if 'MIT-license.txt' not in files:
        raise ValueError('missing upstream license')
    result = []
    for i, (name, point, stem, translated, rationale) in enumerate(TRANSLATIONS):
        source = files['Exercises/' + name + '.html']
        original_stem, original_options = source_parts(source)
        if len(translated) != 4 or len(set(translated)) != 4:
            raise ValueError('invalid translation options')
        rotation = i % 4
        options = translated[-rotation:] + translated[:-rotation] if rotation else translated[:]
        english = original_options[-rotation:] + original_options[:-rotation] if rotation else original_options[:]
        result.append(dict(code=name.replace('/','-'), subject='数据结构', knowledge_point=point,
            content='【课程习题·中译】' + stem, options=options, answer='ABCD'[rotation],
            analysis=rationale + '\n\n来源：OpenDSA / ' + name + '；中文翻译与解释核对（2026-10-24），非408统考真题。',
            difficulty='MEDIUM' if point in ('问题复杂度上界','渐近复杂度','快速排序','堆排序','归并排序') else 'EASY',
            source_type='COURSE_EXERCISE', source_name=SOURCE_NAME,
            source_locator=source['display_url']+'；Git blob '+source['sha'], source_question_no=source['name'],
            permission_note='OpenDSA Project；Ville Karavirta、Cliff Shaffer及贡献者；MIT License（上游声明保存在real-opendsa-sources.json）。本项目中文翻译，保留原正确答案和三个原干扰项，固定原题条件变体并调整选项顺序。非统考真题。获取日期2026-10-24。',
            original_stem=original_stem, original_options=english, original_answer=original_options[0],
            source_blob=source['sha'], review_method='原题solution核对＋中文逐项语义核对＋独立概念/复杂度复算；非教师人工审核'))
    if len(result) != len({q['code'] for q in result}):
        raise ValueError('duplicate source IDs')
    return result


READINGS = [
('docs/chapter_stack_and_queue/stack.md','栈的后进先出与基本操作','数据结构','栈；基本操作',
 '栈在同一端进行插入和删除，这一端称为栈顶；另一端称为栈底。最后进入栈的元素最先离开，因此称为后进先出（LIFO）。入栈push把新元素放在栈顶，出栈pop删除并返回栈顶元素，peek只读取栈顶而不删除。访问或删除前应检查栈是否为空。栈可用动态数组或链表实现；数组实现利用尾部插入删除，链表实现可把表头作为栈顶。调用栈、括号匹配等问题都依赖这种逆序恢复关系。'),
('docs/chapter_stack_and_queue/queue.md','队列的先进先出与双端实现','数据结构','队列；基本操作',
 '队列只允许在队尾加入元素、在队首移除元素，遵循先进先出（FIFO）。enqueue或offer表示入队，dequeue或poll表示出队，front或peek只访问队首。数组实现需要管理队首与队尾位置，不能把每次出队都平移整个数组当作高效实现；链表实现可用首尾指针完成两端操作。访问队首或出队前应检查是否为空。队列适合按到达顺序处理请求，也是广度优先遍历使用的基本结构。'),
('docs/chapter_tree/binary_tree.md','二叉树的节点与层级术语','数据结构','二叉树；节点',
 '二叉树的节点包含一个值、左子节点引用和右子节点引用，每个节点最多有两个子节点。没有父节点的节点称为根；没有子节点的节点称为叶节点。父子连接构成边，从根到某节点的一串连接构成路径。二叉树体现分支和层级关系，不能把逻辑上的父子关系理解成内存中必须相邻。学习树的高度、深度、层数等指标时，要明确是否从0计数，避免不同定义导致一位之差。'),
('docs/chapter_searching/binary_search.md','二分查找的有序前提与边界','数据结构','二分查找；有序数组',
 '二分查找要求搜索区间具有有序性。对递增且无重复元素的数组，可初始化闭区间[i,j]=[0,n−1]，计算中点m，比较nums[m]与target。若中点较小，保留右半区间并令i=m+1；若中点较大，保留左半区间并令j=m−1；相等则返回索引。区间为空表示没有找到。每轮规模减半，迭代版本时间复杂度为O(log n)、辅助空间为O(1)。为避免i+j溢出，可用i+(j−i)/2的向下取整计算中点。'),
('os-memory','虚拟内存、页表与访问权限','操作系统','虚拟内存；页表；内核态',
 '操作系统通过地址虚拟化隔离不同程序的内存。虚拟地址被分解为虚拟页号和页内偏移，MMU按页表把虚拟页号映射为物理页号，偏移保持不变。页表项还记录页面是否驻留以及读写、用户或内核访问权限等信息。多级页表按需分配下级表，以减少一次性分配大页表的开销，但转换可能需要多次访问。仅有虚拟地址不足以保护页表，仍需用户态和内核态等硬件权限机制。本摘要对应课程中的32位示例，不推断所有体系结构的具体位数。'),
('os-locks','有界缓冲区与互斥锁','操作系统','并发；互斥锁；有界缓冲区',
 '有界缓冲区最多保存N条消息：为空时接收者需要等待，已满时发送者需要等待。多个发送者并发写入会使检查空间、写入消息和递增位置之间发生交错，导致覆盖或空洞。锁应保护需要作为一个整体完成的临界区，而不是机械地逐行加锁。检查条件与执行写入必须处于一致的同步规则之内；若在缓冲区已满时持锁无限等待，会阻止接收者取得锁并释放空间。原课程逐步比较这些错误实现，再给出正确同步方案。'),
('os-threads','线程切换、条件变量与丢失唤醒','操作系统','线程；上下文切换；条件变量',
 '课程把线程视为虚拟处理器。线程切换需要保存当前执行状态，选择可运行线程，再恢复其状态。条件变量让等待线程休眠，由其他线程在状态变化后通知。若释放锁和进入等待分成互不关联的步骤，通知可能在等待真正开始前到达，从而造成丢失唤醒。因此等待操作需要同时处理条件变量与关联锁，并在休眠时按同步协议释放锁。抢占式调度还利用定时中断，使一个从不主动让出CPU的线程也不会永久垄断处理器。'),
('os-structure','虚拟机监控器与微内核','操作系统','虚拟机；VMM；微内核',
 '虚拟机监控器VMM负责为多个客户操作系统分配资源、分派事件并处理需要访问真实硬件的操作。逐条解释执行兼容性较好但速度慢，直接执行普通指令并截获特权行为可改善性能；现代硬件提供额外虚拟化支持。客户虚拟地址、客户物理地址和宿主物理地址是不同层次，不能混用。微内核把部分服务移到用户空间以加强模块隔离，其通信开销与接口设计也带来权衡。虚拟机和微内核解决的目标不同：前者运行多个系统，后者拆分单个系统的内部职责。'),
('co-7','吞吐率、延迟与流水线性能','计算机组成原理','流水线；吞吐率；延迟',
 '延迟衡量一个输入从进入系统到产生输出所需的时间；吞吐率衡量单位时间完成的工作量。流水线通过让不同输入处于不同处理阶段，提高持续处理多项任务时的吞吐率，但不保证单项任务的延迟下降。时钟周期必须满足最慢阶段的时序要求，并考虑寄存器开销；不均衡阶段会形成瓶颈。比较性能时，应同时说明任务数量、阶段划分、启动和排空成本，不能把吞吐率的提升直接解释为每个任务都同倍加速。'),
('co-9','存储程序与指令集体系结构','计算机组成原理','存储程序；ISA；指令',
 '存储程序思想把表示操作的指令编码存入存储器，使同一硬件可以通过改变程序处理不同计算任务。指令集体系结构ISA规定软件可见的操作、寄存器与存储访问约定，而不等同于某一种具体电路实现。课程使用Beta这一教学指令集，介绍ALU运算、常数操作数、加载、存储和分支等指令。数据通路负责数据移动和运算，控制逻辑根据指令选择相应动作。Beta的寄存器数、指令长度等是教学体系结构的约定，不能直接套用到所有处理器。'),
('co-14','存储层次、局部性与Cache','计算机组成原理','Cache；存储层次；局部性',
 '处理器寄存器、SRAM、DRAM与非易失存储在容量、延迟和成本上各有取舍，形成存储层次。时间局部性表示近期访问的数据可能再次访问，空间局部性表示邻近地址可能很快被访问。Cache利用这些规律，把部分主存块保存在更快的存储中。直接映射为每个块规定唯一位置，可能发生冲突失效；组相联允许块放在对应组的若干路中，减少部分冲突但增加硬件选择成本。写直达和写回采用不同的一致性维护方式，写回通常需要脏位记录修改。'),
('co-15','处理器流水线中的数据与控制冒险','计算机组成原理','流水线；数据冒险；控制冒险',
 '程序执行时间可分解为动态指令数量、平均每条指令周期数CPI和时钟周期时长的乘积。流水化缩短单级组合逻辑路径，但引入了多条指令重叠执行的依赖问题。数据冒险发生在后续指令需要尚未生成或写回的结果时，可使用暂停和旁路转发；某些加载后立即使用的情况仍需暂停。控制冒险来自分支去向尚未确定，可通过暂停、预测和出错后清除等机制处理。流水线的异常和中断还需要维持可理解的程序状态。'),
('foundation/architecture.rst','网络分层、协议与服务接口','计算机网络','网络分层；协议；封装',
 '网络体系结构通过分层和抽象管理复杂性。每一层向上提供服务，并使用下一层的服务；同层对等实体之间遵守协议，层间则通过接口交互。发送端通常把上层数据封装为本层的协议数据单元，接收端按相反方向解释并交付。协议描述对等方如何通信，服务接口描述本层向上提供什么能力，两者不能混为一谈。OSI七层模型和互联网体系结构是不同的组织方法，实际互联网协议并不需要逐层一一对应OSI模型。'),
('foundation/performance.rst','网络带宽、时延与带宽时延积','计算机网络','带宽；时延；带宽时延积',
 '网络性能的两个基本维度是带宽与时延。带宽可用单位时间可传输的比特数量衡量，实际吞吐率还受实现、协议和竞争等因素影响。传输时延与报文长度和链路速率有关，传播时延与距离和传播速度有关；排队和处理也会贡献时延。高带宽并不自动意味着低时延。带宽时延积描述一段时间内链路上可以在途的数据量；若讨论往返路径，必须明确使用的是RTT而不是单程传播时延，避免口径混用。'),
('e2e/tcp.rst','TCP可靠字节流、流量控制与拥塞控制','计算机网络','TCP；可靠传输；流量控制；拥塞控制',
 'TCP向应用提供面向连接、可靠且按序交付的字节流服务，而不是保留应用每次发送的报文边界。一条连接支持两个方向的字节流，属于全双工通信。序号、确认和重传用于处理丢失及乱序等问题。流量控制约束发送者，避免超过接收方的接收能力；拥塞控制关注网络承载能力，避免向拥塞路径继续过量注入数据。两种控制的目标不同，不能把接收窗口与拥塞窗口混为同一个概念。'),
('e2e/udp.rst','UDP端口与尽力交付','计算机网络','UDP；端口；复用分用',
 'UDP在网络层提供的主机到主机交付之上，通过端口把数据交付到相应的进程或应用端点。源端口和目的端口支持传输层的复用与分用。与TCP不同，UDP不提供连接建立、可靠有序字节流、流量控制或拥塞控制这一整套能力，而是保留数据报边界并使用简单的传输机制。应用若需要重传、排序或拥塞管理，应由应用或更高层协议实现；不能因UDP首部简单就推断它适合任意网络条件。'),
]


def documents():
    sources = json.loads((ROOT/'scripts/fixtures/real-reading-sources.json').read_text())
    files = {f['path']: f for f in sources['files']}
    result = []
    for path, title, subject, keywords, content in READINGS:
        f = files[path]
        if 'sha' in f:
            blob = hashlib.sha1(f'blob {len(f["content"].encode())}\0'.encode()+f['content'].encode()).hexdigest()
            if blob != f['sha']: raise ValueError('reading source hash mismatch')
            version = 'git-blob-' + blob
        else:
            if hashlib.sha256(f['content'].encode()).hexdigest() != f['sha256']:
                raise ValueError('MIT source hash mismatch')
            version = 'sha256-' + f['sha256']
        if path.startswith('docs/'):
            author='靳宇栋（krahets）与Hello算法贡献者'
            license='CC BY-NC-SA 4.0；https://creativecommons.org/licenses/by-nc-sa/4.0/；中文节选整理，保留署名与相同许可。'
        elif path.startswith(('foundation/','e2e/')):
            author='Larry Peterson、Bruce Davie及Systems Approach贡献者'
            license='CC BY 4.0；https://creativecommons.org/licenses/by/4.0/；英文原文的中文摘要，已修改表达。'
        else:
            author=f['author']
            license='CC BY-NC-SA 4.0；https://ocw.mit.edu/pages/privacy-and-terms-of-use/；教学讲义中文摘要，已修改表达；不含第三方图片。'
        identifier='real-knowledge-'+hashlib.sha256(path.encode()).hexdigest()[:12]
        result.append(dict(id=identifier, domain='knowledge', title=title, subject=subject,
            url=f['display_url'], locator=path+'；按主题中文节选整理；作者：'+author,
            version=version,retrievedAt=DATE,license=license,reviewStatus='verified',
            content=content,keywords=keywords.split('；'),metadata={'author':author,'adaptation':'中文摘要，非完整教材','sourcePath':path}))
    return result


if __name__ == '__main__':
    print(json.dumps({'question_count':len(questions()), 'subjects':{'数据结构':len(questions())},
                      'source':'OpenDSA', 'generated_questions':0,'documents':len(documents())},ensure_ascii=False))
