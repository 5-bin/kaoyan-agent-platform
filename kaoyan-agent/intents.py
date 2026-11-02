"""Single deterministic intent/condition source shared by chat and legacy routing."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from schemas import AssistantPageContext, ConversationConditions, ConversationResolution


REGIONS = (
    "北京",
    "上海",
    "江苏",
    "浙江",
    "广东",
    "四川",
    "湖北",
    "山东",
    "陕西",
    "天津",
    "重庆",
    "湖南",
    "安徽",
    "福建",
    "河北",
    "河南",
    "辽宁",
    "吉林",
    "黑龙江",
    "山西",
    "江西",
    "广西",
    "云南",
    "贵州",
    "甘肃",
    "青海",
    "海南",
    "宁夏",
    "新疆",
    "西藏",
    "内蒙古",
)

# Reading capabilities and routing must recognize exactly the same synonyms.
READ_TERMS: dict[str, tuple[str, ...]] = {
    "wrong": ("错题", "答错", "错因"),
    "favorite": ("收藏",),
    "stats": ("统计", "正确率", "学习情况", "学情", "薄弱", "掌握", "成绩", "诊断"),
    "practice": ("作答记录", "练习记录", "练习情况", "批次"),
    "documents": ("备考资料", "学习资料", "资料正文", "推荐资料", "复习资料"),
}


# Bare numbers in 408 questions (页大小2048、地址100000) are not admission conditions.
CONDITION_CONTEXT = re.compile(r"择校|院校|报考|考研|招生|推荐|学硕|专硕|专业|大学|学院|入学|届")
CONDITION_ONLY = re.compile(r"[\d\s，,、;；。和与及或至年届]+")
YEAR = r"(?<!\d)20\d{2}(?!\d)"
# 别 negates only as an imperative (别帮我、别推荐); 区别、分别、特别、类别 are ordinary words.
IMPERATIVE_BIE = r"(?<![区分特类级识告性派辨鉴差个])别(?=帮|给|再|去|让|把|做|安排|推荐|分析|生成|创建|收藏|查|看|管|保存|修改|删|讲|解释|用|问|整理|出)"


def positive_request(text: str) -> str:
    """Remove negated clauses while retaining separately requested capabilities."""
    clauses = re.split(r"[，。；\n]|(?:并且|然后|同时|但是|但|并)(?=\S)", text)
    return "，并".join(
        clause.strip() for clause in clauses
        if clause.strip() and not re.search(r"不要|不需要|不必|无需|" + IMPERATIVE_BIE + r"|不想|不(?:推荐|分析|安排|生成|创建|收藏|查询|查看|修改|解释|讲解)", clause)
    )


def natural_practice_topic(text: str) -> str | None:
    """Recognize 练习TCP／刷TCP题／做几道TCP题; return the raw topic ("" when generic)."""
    match = re.search(
        r"(?:^|，并)\s*(?:请|帮我|我想|我要|给我)?\s*(?:练习|刷)(?:一下|一些|几道|[0-9一二两三四五六七八九十]+道)?\s*"
        r"(?!记录|情况|批次|功能|按钮|题功能|错|过)([^，。；\n]{1,40}?)\s*[。！!]?$",
        text,
    ) or re.search(
        r"做(?:几|一些|[0-9一二两三四五六七八九十]+)\s*道\s*([^，。；\n]{0,40}?)(?:相关的?|的)?(?:题目|试题|题)",
        text,
    )
    if match is None:
        return None
    topic = re.sub(r"(?:相关的?|的)?(?:题目|试题|题)$", "", match[1].strip())
    return "" if topic in {"", "一下", "一些", "几道"} else topic


class ConditionExtractor:
    """Extract explicit condition patches; omitted fields stay unset."""

    @staticmethod
    def regions(text: str) -> dict[str, object]:
        """Retain the established required/preferred province semantics."""
        regions = [region for region in REGIONS if region in text]
        if len(regions) == len(REGIONS):
            # Every province is no region constraint (and exceeds the 30-item contract).
            return {}
        # “只考虑江苏／地区限定为上海” restricts; “不只江苏” or “只考学硕，北京优先” do not.
        required = bool(regions) and bool(re.search(
            r"(?<!不)(?:只|仅|限定|限于|必须)[^，。；,;]{0,8}?(?:" + "|".join(regions) + ")", text
        ))
        return (
            {
                "regions": regions,
                "regionConstraint": "required" if required else "preferred",
            }
            if regions
            else {}
        )

    @staticmethod
    def condition_context(text: str) -> bool:
        """Numbers count as conditions only in an admission context or a bare follow-up."""
        return bool(CONDITION_CONTEXT.search(text) or CONDITION_ONLY.fullmatch(text.strip()))

    @classmethod
    def years(cls, text: str) -> set[str]:
        """Read exam years marked by 年/届 or stated in an admission context."""
        if not (re.search(YEAR + r"\s*(?:年|届)", text) or cls.condition_context(text)):
            return set()
        return set(re.findall(YEAR, text))

    @classmethod
    def conflicting(cls, text: str) -> bool:
        """Detect incompatible year/degree choices instead of silently choosing one."""
        return len(cls.years(text)) > 1 or ("学硕" in text and "专硕" in text)

    @classmethod
    def extract(cls, text: str) -> ConversationConditions:
        """Validate the same partial patch for simple and compound conversations."""
        patch = cls.regions(text)
        years = cls.years(text)
        if len(years) == 1:
            patch["examYear"] = int(next(iter(years)))
        majors = (
            list(dict.fromkeys(re.findall(r"(?<!\d)\d{6}(?!\d)", text)))
            if cls.condition_context(text)
            else []
        )
        if majors:
            patch["majorCodes"] = majors[:10]
        if "学硕" in text:
            patch["degreeType"] = "academic"
        elif "专硕" in text:
            patch["degreeType"] = "professional"
        return ConversationConditions.model_validate(patch)


@dataclass(frozen=True)
class IntentSignals:
    """Independent requested capabilities; these never authorize business writes."""

    school: bool
    learning: bool
    knowledge: bool
    study: bool
    note: bool


class IntentResolver:
    """Share capability vocabulary while preserving existing write guards."""

    @staticmethod
    def local_plan(
        text: str, page: AssistantPageContext | None, selected: bool
    ) -> ConversationResolution | None:
        """Resolve local operations once, with document context taking precedence."""
        return local_document_plan(text, page, selected) or local_learning_plan(
            text, page
        )

    @classmethod
    def fallback_action(cls, text: str, keywords: tuple[str, ...]) -> str:
        """Preserve simple follow-up editing and school condition-only turns."""
        text = positive_request(text)
        if any(word in text for word in ("修改", "改写", "润色")):
            return "DOCUMENT_UPDATE"
        if any(word in text for word in ("创建", "写一份", "生成笔记", "复习计划")):
            return "DOCUMENT_CREATE"
        if cls.inspect(text).school:
            return "SCHOOL_RECOMMEND"
        # A year/region inside a knowledge question (“2027年408真题中TCP”) is
        # not a condition-only school turn.
        if ConditionExtractor.extract(text).model_fields_set and not cls.inspect(text, keywords).knowledge:
            return "SCHOOL_RECOMMEND"
        return cls.task_type(text, keywords)

    @staticmethod
    def inspect(text: str, keywords: tuple[str, ...] = ()) -> IntentSignals:
        """Ignore negated clauses when detecting positive requested capabilities."""
        positive = positive_request(text)
        return IntentSignals(
            school=bool(
                re.search(
                    r"择校|院校|报考|推荐学校|推荐大学|推荐专业|学硕|专硕", positive
                )
            ),
            learning=any(term in positive for terms in READ_TERMS.values() for term in terms),
            knowledge=bool(re.search(r"解释|讲解|知识问答", positive))
            or any(word.lower() in positive.lower() for word in keywords),
            study=bool(
                re.search(
                    r"(?:复习|学习)计划|安排.{0,8}复习|下周.{0,8}(?:复习|学习)",
                    positive,
                )
            ),
            note=bool(re.search(r"笔记|文档", positive)),
        )

    @classmethod
    def task_type(cls, text: str, keywords: tuple[str, ...]) -> str:
        """Legacy synchronous callers cannot represent a compound task."""
        signals = cls.inspect(text, keywords)
        if signals.school and signals.knowledge:
            return "CHAT"
        if signals.school:
            return "SCHOOL_RECOMMEND"
        if signals.knowledge:
            return "KNOWLEDGE_QA"
        return "CHAT"


def chinese_number(text: str) -> int:
    """Read an explicit Chinese or Arabic count without inventing a value."""
    if text.isdigit():
        return int(text)
    values = {
        "零": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if "十" in text:
        left, right = text.split("十", 1)
        return values.get(left, 1) * 10 + values.get(right, 0)
    return values.get(text, 0)


def requested_knowledge_point(text: str) -> str | None:
    """Extract one bounded topic, preserving subtopics and ambiguity."""

    def normalize(value: str) -> str:
        value = re.sub(r"\s+", "", value).strip("“”\"'：:")
        value = re.sub(r"tcp", "TCP", value, flags=re.I)
        value = re.sub(r"udp", "UDP", value, flags=re.I)
        return (
            value.replace("传输控制协议", "TCP")
            .replace("用户数据报协议", "UDP")
            .replace("TCP协议", "TCP")
            .replace("UDP协议", "UDP")
        )

    # Accept new topics without consulting a dictionary. Stop before commands.
    end = r"(?:内容|有关|相关|的(?:题|错题|部分)|[，。；\n”\"]|$)"
    # In “堆有关错题”, 有关 follows the topic; do not treat 错题 as a new topic.
    topic_prefix = r"(?:涉及|关于|有关(?!的|错题|题目|试题|题)|跟|(?<!进程)与)"
    explicit = re.search(r"知识点\s*(?:为|是|[:：])\s*[“\"]?(.{1,255}?)" + end, text)
    topic = re.search(topic_prefix + r"\s*(.{0,255}?)" + end, text)
    if explicit is None:
        topics = {
            normalize(m[1])
            for m in re.finditer(topic_prefix + r"\s*(.{0,255}?)" + end, text)
            if normalize(m[1])
        }
        if len(topics) > 1:
            return None
    else:
        explicit_topics = {
            normalize(m[1])
            for m in re.finditer(
                r"知识点\s*(?:为|是|[:：])\s*[“\"]?(.{1,255}?)" + end, text
            )
        }
        if len(explicit_topics) > 1:
            return None
    direct = re.search(
        r"(?:搜索|查找|找|查)(?:出|一些|几道|\d+道)?\s*([^，。；\n]{1,100}?)(?:相关的?|的)?(?:题目|试题|题)(?:[，。；\n]|$)",
        text,
    )
    practice_topic = re.search(
        r"(?:出|来)(?:一组|一套)?\s*(?:几|一些|[0-9一二两三四五六七八九十百千]+)?\s*道?\s*([^，。；\n]{1,100}?)(?:相关的?|的)?(?:题目|试题|题)(?:[，。；\n]|$)",
        text,
    )
    match = explicit or topic or practice_topic or direct
    if match:
        value = normalize(match[1])
        value = re.sub(r"^(?:一些|几道|[0-9一二两三四五六七八九十]+道)", "", value)
        if match is practice_topic:
            value = re.sub(
                r"^(?:简单|中等|困难|数据结构|计算机组成原理|操作系统|计算机网络)+",
                "",
                value,
            )
            if value in {"道", "几", "几道", "一些"}:
                return None
        if (
            not value
            or value in {"这", "这个", "那个", "它", "上述", "未知主题", "某个知识点"}
            or (
                value != "进程与线程"
                and re.search(
                    r"和|以及|或者|或|、|与|并且|同时|加入|收藏|移出|取消|创建|生成",
                    value,
                )
            )
        ):
            return None
        return value
    # Known labels are read filters, never executable expressions or write targets.
    labels = (
        "线性表",
        "栈",
        "队列",
        "树的遍历",
        "AVL树",
        "拓扑排序",
        "最小生成树",
        "最短路径",
        "堆",
        "散列表",
        "排序",
        "查找",
        "图",
        "进程与线程",
        "内存管理",
        "虚拟内存",
        "进程调度",
        "死锁",
        "TCP",
        "TCP拥塞控制",
        "TCP序号",
        "UDP",
        "路由选择",
        "存储层次",
    )
    normalized = (
        re.sub(r"\s+", "", text)
        .upper()
        .replace("传输控制协议", "TCP")
        .replace("用户数据报协议", "UDP")
    )
    found = [
        label
        for label in labels
        if re.search(
            (r"(?<![A-Z0-9])" if label[0].isascii() else "")
            + re.escape(label.upper())
            + (r"(?![A-Z0-9])" if label[-1].isascii() else ""),
            normalized,
        )
    ]
    found = [
        label
        for label in found
        if not any(label != other and label in other for other in found)
    ]
    if len(found) != 1:
        return None
    # Preserve a requested subtopic instead of silently widening it to its parent.
    topic = re.search(
        r"(?:涉及|关于|跟|与)\s*(.{1,50}?)(?:内容|有关|相关|的(?:题|错题|部分)|[，。；]|$)",
        text,
    )
    if topic:
        value = (
            re.sub(r"\s+", "", topic[1])
            .upper()
            .replace("传输控制协议", "TCP")
            .replace("用户数据报协议", "UDP")
        )
        value = value.replace("TCP协议", "TCP").replace("UDP协议", "UDP")
        if found[0].upper() in value:
            return value
    return found[0]


def local_document_plan(
    text: str, page_context: AssistantPageContext | None = None, selected: bool = False
) -> ConversationResolution | None:
    """A note can use learning reads without being routed into pure analysis."""
    text = positive_request(text)
    if re.search(r"如何|怎么|这句话|示例|例如|假设", text):
        return None
    note = bool(re.search(r"笔记|文档|计划|清单", text))
    update = bool(re.search(r"修改|改写|润色|改进|调整|补充|改成|改为", text)) and (
        note or selected
    )
    create = note and bool(re.search(r"新建|创建|生成|写一份|整理成|汇总成", text))
    if not update and not create:
        return None
    learning = local_learning_plan(text, page_context)
    return ConversationResolution(
        action="DOCUMENT_UPDATE" if update else "DOCUMENT_CREATE",
        standaloneQuery=text,
        reads=learning.reads if learning else [],
        subject=learning.subject if learning else None,
        knowledgePoint=learning.knowledgePoint if learning else None,
        **({"from": learning.from_, "to": learning.to} if learning else {}),
    )


def local_learning_plan(
    text: str, page_context: AssistantPageContext | None = None
) -> ConversationResolution | None:
    """Parse only the current user's instruction; data/history cannot authorize writes."""
    original_text = text
    text = positive_request(text)
    reads = []
    positive = positive_request(text)
    for kind, terms in READ_TERMS.items():
        if any(term in positive for term in terms):
            reads.append(kind)
    operation = "NONE"
    # Questions about how to use a button and negated requests are not commands.
    command = not re.search(
        r"不要|别帮|不需要|如何|怎么|能否介绍|说明.*功能|是什么意思|这句话|这个指令|示例|例如|假设",
        text,
    )
    if re.search(
        r"(?:出题|组题|练习)(?:功能|按钮|流程).*(?:什么|如何|怎么|作用|用途|吗)|(?:出题|组题)(?:是什么|有什么用|会收费吗)",
        text,
    ):
        command = False
    operation_text = "，并".join(
        clause for clause in re.split(r"[，。；\n]|(?:并且|然后|同时|顺便|并)(?=\S)", text)
        if not re.search(r"分析|统计|查看|查询|介绍|解释|了解", clause)
    )
    if command:
        if re.search(
            r"(?:取消|移除|移出|删除).{0,12}收藏|收藏.{0,12}(?:取消|移除|移出|删除)",
            operation_text,
        ):
            operation = "FAVORITE_REMOVE"
        elif re.search(
            r"(?:移出|移除|取消|删除).{0,12}错题|错题.{0,12}(?:移出|移除|取消|删除)",
            operation_text,
        ):
            operation = "WRONG_REMOVE"
        elif re.search(
            r"(?:帮我|请|并|顺便)\s*收藏|(?:把|将).{0,12}收藏(?:一下|起来)?[。！!]?\s*$|收藏\s*(?:这|第|Q\d|题号|题目|#|选中|当前|某|全部)|(?:加入|添加)(?:到)?(?:我的)?收藏",
            operation_text,
        ):
            operation = "FAVORITE_ADD"
        elif re.search(
            r"(?:安排|创建|生成|开始|来|出)[^，。；\n]{0,60}(?:练习|刷题|题)|(?:用|从).{0,10}(?:错题|收藏).{0,12}(?:练习|刷题)",
            operation_text,
        ) or re.search(r"(?:练|刷)(?:一遍|习)?(?:我)?的?(?:错题|收藏)", operation_text):
            operation = "PRACTICE_CREATE"
        elif natural_practice_topic(operation_text) is not None:
            operation = "PRACTICE_CREATE"
    binding_text = operation_text if operation != "NONE" else text
    target = "selected"
    if operation == "PRACTICE_CREATE":
        target = (
            "wrong"
            if "错题" in text
            else "favorite"
            if "收藏" in text
            else "selected"
            if "选中" in text
            else "visible"
            if re.search(r"这些题|当前题|这道题", text)
            else "normal"
        )
    elif any(term in text for term in ("这些", "全部", "当前页", "本页", "所有")):
        target = "visible"
    subject = next(
        (
            s
            for s in ("数据结构", "计算机组成原理", "操作系统", "计算机网络")
            if s in text
        ),
        None,
    )
    if page_context is not None:
        if not subject:
            subject = page_context.subject
        if not reads and any(
            term in text
            for term in (
                "当前页",
                "这个页面",
                "这些题",
                "这些记录",
                "这道题",
                "分析",
                "总结",
            )
        ):
            kind = {"stat": "stats"}.get(page_context.page, page_context.page)
            if kind in {"wrong", "favorite", "stats", "practice", "documents"}:
                reads = [kind]
    difficulty = next(
        (
            value
            for term, value in (("简单", "EASY"), ("中等", "MEDIUM"), ("困难", "HARD"))
            if term in text
        ),
        None,
    )
    count = 5
    match = re.search(r"([0-9零一二两三四五六七八九十百千]+)\s*道(?:题)?", binding_text)
    clarification = None
    if match:
        count = chinese_number(match[1])
        if not 1 <= count <= 50:
            clarification = "每次练习支持1至50题，请调整题目数量。"
            count = 5
    ordinal = None
    match = re.search(r"第\s*([0-9一二两三四五六七八九十百千]+)\s*(?:道|个)?题", binding_text)
    if match:
        ordinal = chinese_number(match[1])
        if not 1 <= ordinal <= 50:
            clarification, ordinal = "请指定当前可见列表1至50范围内的题目。", None
    refs = list(dict.fromkeys(re.findall(r"\bQ[1-9]\d{0,2}\b", binding_text)))[:50]
    point = requested_knowledge_point(binding_text)
    natural_topic = natural_practice_topic(binding_text) if operation == "PRACTICE_CREATE" else None
    if point is None and natural_topic:
        # Free topics follow the existing “出…题” rule; multiple topics still clarify.
        point = requested_knowledge_point("知识点：" + natural_topic)
        if point is None:
            clarification = "请先指定一个明确的练习主题；可使用“知识点：排序”指定。"
    public_questions = "题库" in text or (
        not any(k in reads for k in ("wrong", "practice"))
        and not re.search(r"收藏(?:夹|本|列表|中|里|内|的)", text)
        and bool(re.search(r"找.{0,80}题|搜索.{0,80}题|查找.{0,80}题", text))
    )
    if public_questions and not refs and ordinal is None:
        reads = ["questions"]
        target = "normal"
        subject = next(
            (
                s
                for s in ("数据结构", "计算机组成原理", "操作系统", "计算机网络")
                if s in text
            ),
            None,
        )
    if operation == "PRACTICE_CREATE" and target == "normal" and "questions" not in reads:
        reads.append("questions")
    # The collection being read is distinct from the destination of a write.
    # Explicit references still bind to the prior answer instead of a fresh list.
    source = None
    if re.search(r"错题(?:本)?(?:中|里|内|的)|从.{0,5}错题", text):
        source = "wrong"
    elif re.search(r"收藏(?:夹|本|列表)?(?:中|里|内|的)|从.{0,5}收藏", text):
        source = "favorite"
    elif operation == "FAVORITE_REMOVE" and "收藏" in text:
        source = "favorite"
    elif operation == "WRONG_REMOVE" and "错题" in text:
        source = "wrong"
    if (
        source
        and (operation != "NONE" or point is not None)
        and not refs
        and ordinal is None
        and not re.search(
            r"选中|当前页|本页|这些|将其|把其|刚才|上一|上述|找到的|那道|该题", text
        )
    ):
        target = source
        reads = [
            kind
            for kind in reads
            if kind not in {"wrong", "favorite"} or kind == source
        ]
        subject = next(
            (
                s
                for s in ("数据结构", "计算机组成原理", "操作系统", "计算机网络")
                if s in text
            ),
            None,
        )
    if (
        point is None
        and re.search(r"涉及|有关|相关|知识点|关于", binding_text)
        and not re.search(r"同知识点|(?:相关|有关).{0,4}(?:练习|资料|概念|解释)", binding_text)
    ):
        clarification = "未能确定你要筛选的知识点，请补充一个明确主题；可使用“知识点：主题名称”指定。"
    if (
        operation == "PRACTICE_CREATE"
        and point is None
        and re.search(r"(?:出|来).*(?:和|以及|或者|、).*(?:题目|试题|题)", binding_text)
    ):
        clarification = "请先指定一个明确的练习主题；可使用“知识点：排序”指定。"
    if not reads and operation == "NONE":
        return ConversationResolution(action="CHAT", standaloneQuery=original_text) if any(
            term in original_text for terms in READ_TERMS.values() for term in terms
        ) else None
    if not reads and operation in {"FAVORITE_ADD", "FAVORITE_REMOVE", "WRONG_REMOVE"}:
        reads = ["favorite" if operation != "WRONG_REMOVE" else "wrong"]
    if operation == "PRACTICE_CREATE" and not reads:
        # “这些题／选中的题” without a page snapshot names no readable collection.
        clarification = "请在错题、收藏或练习页面选择题目后再组练习，或说明使用错题、收藏还是某个知识点的题库题目。"
    dates = re.findall(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", text)
    interval = {}
    if dates:
        try:
            values = [date.fromisoformat(value) for value in dates[:2]]
            if len(values) == 2 and values[0] > values[1]:
                raise ValueError("order")
            interval = {"from": str(values[0]), "to": str(values[-1])}
        except ValueError:
            clarification = "请提供有效且开始不晚于结束的日期范围。"
    elif match := re.search(r"近\s*(\d{1,3})\s*天", text):
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        days = int(match[1])
        if days:
            interval = {"from": str(today - timedelta(days=days - 1)), "to": str(today)}
    elif page_context is not None:
        interval = {
            key: value
            for key, value in (("from", page_context.from_), ("to", page_context.to))
            if value
        }
    return ConversationResolution(
        action="LEARNING_ANALYSIS",
        standaloneQuery=original_text,
        reads=reads,
        operation="NONE" if clarification else operation,
        target=target,
        count=count,
        ordinal=ordinal,
        subject=subject,
        questionRefs=refs,
        clarification=clarification,
        difficulty=difficulty,
        knowledgePoint=point,
        **interval,
    )
