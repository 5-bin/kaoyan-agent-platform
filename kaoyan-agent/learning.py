"""Bounded request planning and model projections. Never executes business tools."""
import re
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime
from schemas import ConversationResolution, StrictModel
from pydantic import Field
from config import provider_identifier


def model_allowed(req, settings):
    return (settings.LLM_ENABLED and req.privacy.modelAllowed
            and req.privacy.provider == provider_identifier(settings.LLM_BASE_URL)
            and req.privacy.provider != "unconfigured")


def has_scope(req, scope):
    return scope in req.privacy.scopes


def model_messages(req):
    # Unknown legacy sensitivity is not equivalent to public history.
    return [{"role": m.role, "content": m.content} for m in req.messages
            if m.scopes is not None and set(m.scopes) <= set(req.privacy.scopes)]


def chinese_number(text):
    if text.isdigit():
        return int(text)
    values = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if "十" in text:
        left, right = text.split("十", 1)
        return values.get(left, 1) * 10 + values.get(right, 0)
    return values.get(text, 0)


def requested_knowledge_point(text):
    def normalize(value):
        value = re.sub(r"\s+", "", value).strip('“”"\'：:')
        value = re.sub(r"tcp", "TCP", value, flags=re.I)
        value = re.sub(r"udp", "UDP", value, flags=re.I)
        return value.replace("传输控制协议", "TCP").replace("用户数据报协议", "UDP").replace("TCP协议", "TCP").replace("UDP协议", "UDP")

    # Accept new topics without consulting a dictionary. Stop before commands.
    end = r"(?:内容|有关|相关|的(?:题|错题|部分)|[，。；\n”\"]|$)"
    # In “堆有关错题”, 有关 follows the topic; do not treat 错题 as a new topic.
    topic_prefix = r"(?:涉及|关于|有关(?!的|错题|题目|试题|题)|跟|(?<!进程)与)"
    explicit = re.search(r"知识点\s*(?:为|是|[:：])\s*[“\"]?(.{1,255}?)" + end, text)
    topic = re.search(topic_prefix + r"\s*(.{0,255}?)" + end, text)
    if explicit is None:
        topics = {normalize(m[1]) for m in re.finditer(topic_prefix + r"\s*(.{0,255}?)" + end, text) if normalize(m[1])}
        if len(topics) > 1:
            return None
    else:
        explicit_topics = {normalize(m[1]) for m in re.finditer(r"知识点\s*(?:为|是|[:：])\s*[“\"]?(.{1,255}?)" + end, text)}
        if len(explicit_topics) > 1:
            return None
    direct = re.search(r"(?:搜索|查找|找|查)(?:出|一些|几道|\d+道)?\s*([^，。；\n]{1,100}?)(?:相关的?|的)?(?:题目|试题|题)(?:[，。；\n]|$)", text)
    match = explicit or topic or direct
    if match:
        value = normalize(match[1])
        value = re.sub(r"^(?:一些|几道|[0-9一二两三四五六七八九十]+道)", "", value)
        if (not value or value in {"这", "这个", "那个", "它", "上述", "未知主题", "某个知识点"}
                or (value != "进程与线程" and re.search(r"和|以及|或者|或|、|与|并且|同时|加入|收藏|移出|取消|创建|生成", value))):
            return None
        return value
    # Known labels are read filters, never executable expressions or write targets.
    labels = ("线性表", "栈", "队列", "树的遍历", "AVL树", "拓扑排序", "最小生成树",
              "最短路径", "堆", "散列表", "排序", "查找", "图", "进程与线程",
              "内存管理", "虚拟内存", "进程调度", "死锁", "TCP", "TCP拥塞控制", "TCP序号",
              "UDP", "路由选择", "存储层次")
    normalized = re.sub(r"\s+", "", text).upper().replace("传输控制协议", "TCP").replace("用户数据报协议", "UDP")
    found = [label for label in labels if re.search(
        (r"(?<![A-Z0-9])" if label[0].isascii() else "") + re.escape(label.upper())
        + (r"(?![A-Z0-9])" if label[-1].isascii() else ""), normalized)]
    found = [label for label in found if not any(label != other and label in other for other in found)]
    if len(found) != 1:
        return None
    # Preserve a requested subtopic instead of silently widening it to its parent.
    topic = re.search(r"(?:涉及|关于|跟|与)\s*(.{1,50}?)(?:内容|有关|相关|的(?:题|错题|部分)|[，。；]|$)", text)
    if topic:
        value = re.sub(r"\s+", "", topic[1]).upper().replace("传输控制协议", "TCP").replace("用户数据报协议", "UDP")
        value = value.replace("TCP协议", "TCP").replace("UDP协议", "UDP")
        if found[0].upper() in value:
            return value
    return found[0]


def clarification_with_example(message, plan):
    if "推荐问法" in message:
        return message
    if plan.action.startswith("DOCUMENT_"):
        example = "请创建一份关于 TCP 拥塞控制的复习笔记。修改已有笔记时请先选择笔记。"
    elif plan.action == "SCHOOL_RECOMMEND":
        example = "请推荐2027年计算机专业的学硕院校，地区限定为上海。"
    elif plan.action == "LEARNING_ANALYSIS":
        example = "请分析我的错题本中涉及 TCP 的题目。若要操作，可说：将我的错题本中涉及 TCP 的题目加入收藏；引用上次回答可说：收藏 Q1 和 Q2。"
    else:
        example = "请解释 TCP 拥塞控制的过程，并举例说明。"
    return message[:750] + "\n推荐问法：" + example


def local_document_plan(text, page_context=None, selected=False):
    """A note can use learning reads without being routed into pure analysis."""
    if re.search(r"不要|不需要|别帮|如何|怎么|这句话|示例|例如|假设", text):
        return None
    note = bool(re.search(r"笔记|文档|计划|清单", text))
    update = bool(re.search(r"修改|改写|润色|改进|调整|补充|改成|改为", text)) and (note or selected)
    create = note and bool(re.search(r"新建|创建|生成|写一份|整理成|汇总成", text))
    if not update and not create:
        return None
    learning = local_learning_plan(text, page_context)
    return ConversationResolution(action="DOCUMENT_UPDATE" if update else "DOCUMENT_CREATE",
        standaloneQuery=text, reads=learning.reads if learning else [],
        subject=learning.subject if learning else None,
        knowledgePoint=learning.knowledgePoint if learning else None,
        **({"from": learning.from_, "to": learning.to} if learning else {}))


def local_learning_plan(text, page_context=None):
    """Parse only the current user's instruction; data/history cannot authorize writes."""
    reads = []
    for kind, terms in (("wrong", ("错题", "答错", "错因")),
                        ("favorite", ("收藏",)), ("stats", ("统计", "正确率", "学习情况", "学情", "薄弱", "掌握情况")),
                        ("practice", ("作答记录", "练习记录", "练习情况", "批次")),
                        ("documents", ("备考资料", "学习资料", "资料正文", "推荐资料", "复习资料"))):
        if any(term in text for term in terms):
            reads.append(kind)
    operation = "NONE"
    # Questions about how to use a button and negated requests are not commands.
    command = not re.search(r"不要|别帮|不需要|如何|怎么|能否介绍|说明.*功能|是什么意思|这句话|这个指令|示例|例如|假设", text)
    if re.search(r"分析|统计|查看|查询|介绍|解释|了解", text) and not re.search(r"(?:并|然后|同时|顺便)(?:帮我)?(?:把|将)?.{0,12}(?:收藏|取消|移出|移除|创建|生成|安排)", text):
        command = False
    if command:
        if re.search(r"(?:取消|移除|移出|删除).{0,12}收藏|收藏.{0,12}(?:取消|移除|移出|删除)", text):
            operation = "FAVORITE_REMOVE"
        elif re.search(r"(?:移出|移除|取消|删除).{0,12}错题|错题.{0,12}(?:移出|移除|取消|删除)", text):
            operation = "WRONG_REMOVE"
        elif re.search(r"(?:帮我|请|并|顺便)\s*收藏|(?:把|将).{0,12}收藏(?:一下|起来)?[。！!]?\s*$|收藏\s*(?:这|第|Q\d|题号|题目|#|选中|当前|某|全部)|(?:加入|添加)(?:到)?(?:我的)?收藏", text):
            operation = "FAVORITE_ADD"
        elif (re.search(r"(?:安排|创建|生成|开始|来|出).{0,18}(?:练习|刷题|道题)|(?:用|从).{0,10}(?:错题|收藏).{0,12}(?:练习|刷题)", text)
              or re.search(r"(?:练|刷)(?:一遍|习)?(?:我)?的?(?:错题|收藏)", text)):
            operation = "PRACTICE_CREATE"
    target = "selected"
    if operation == "PRACTICE_CREATE":
        target = ("wrong" if "错题" in text else "favorite" if "收藏" in text else
                  "selected" if "选中" in text else "visible" if re.search(r"这些题|当前题|这道题", text) else "normal")
    elif any(term in text for term in ("这些", "全部", "当前页", "本页", "所有")):
        target = "visible"
    subject = next((s for s in ("数据结构", "计算机组成原理", "操作系统", "计算机网络") if s in text), None)
    if page_context is not None:
        if not subject:
            subject = page_context.subject
        if not reads and any(term in text for term in ("当前页", "这个页面", "这些题", "这些记录", "这道题", "分析", "总结")):
            kind = {"stat": "stats"}.get(page_context.page, page_context.page)
            if kind in {"wrong", "favorite", "stats", "practice", "documents"}:
                reads = [kind]
    difficulty = next((value for term, value in (("简单", "EASY"), ("中等", "MEDIUM"), ("困难", "HARD")) if term in text), None)
    count = 5
    match = re.search(r"([0-9一二两三四五六七八九十百千]+)\s*道(?:题)?", text)
    clarification = None
    if match:
        count = chinese_number(match[1])
        if not 1 <= count <= 50:
            clarification = "每次练习支持1至50题，请调整题目数量。"
            count = 5
    ordinal = None
    match = re.search(r"第\s*([0-9一二两三四五六七八九十百千]+)\s*(?:道|个)?题", text)
    if match:
        ordinal = chinese_number(match[1])
        if not 1 <= ordinal <= 50:
            clarification, ordinal = "请指定当前可见列表1至50范围内的题目。", None
    refs = list(dict.fromkeys(re.findall(r"\bQ[1-9]\d{0,2}\b", text)))[:50]
    point = requested_knowledge_point(text)
    public_questions = ("题库" in text or (not any(k in reads for k in ("wrong", "practice"))
                        and not re.search(r"收藏(?:夹|本|列表|中|里|内|的)", text)
                        and bool(re.search(r"找.{0,80}题|搜索.{0,80}题|查找.{0,80}题", text))))
    if public_questions and not refs and ordinal is None:
        reads = ["questions"]
        target = "normal"
        subject = next((s for s in ("数据结构", "计算机组成原理", "操作系统", "计算机网络") if s in text), None)
    if operation == "PRACTICE_CREATE" and target == "normal" and not reads:
        reads = ["questions"]
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
    if source and (operation != "NONE" or point is not None) and not refs and ordinal is None and not re.search(r"选中|当前页|本页|这些|将其|把其|刚才|上一|上述|找到的|那道|该题", text):
        target = source
        reads = [kind for kind in reads if kind not in {"wrong", "favorite"} or kind == source]
        subject = next((s for s in ("数据结构", "计算机组成原理", "操作系统", "计算机网络") if s in text), None)
    if point is None and re.search(r"涉及|有关|相关|知识点|关于", text) and not re.search(r"同知识点|(?:相关|有关).{0,4}(?:练习|资料|概念|解释)", text):
        clarification = "未能确定你要筛选的知识点，请补充一个明确主题；可使用“知识点：主题名称”指定。"
    if not reads and operation == "NONE":
        return None
    if not reads and operation in {"FAVORITE_ADD", "FAVORITE_REMOVE", "WRONG_REMOVE"}:
        reads = ["favorite" if operation != "WRONG_REMOVE" else "wrong"]
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
    elif (match := re.search(r"近\s*(\d{1,3})\s*天", text)):
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        days = int(match[1])
        if days:
            interval = {"from": str(today - timedelta(days=days - 1)), "to": str(today)}
    elif page_context is not None:
        interval = {key: value for key, value in (("from", page_context.from_), ("to", page_context.to)) if value}
    return ConversationResolution(action="LEARNING_ANALYSIS", standaloneQuery=text, reads=reads,
        operation="NONE" if clarification else operation, target=target, count=count, ordinal=ordinal, subject=subject,
        questionRefs=refs, clarification=clarification, difficulty=difficulty,
        knowledgePoint=point, **interval)


def _fields(value, keys):
    return {key: value[key] for key in keys if key in value and isinstance(value[key], (str, int, float, bool, type(None)))}


def safe_learning_context(req, *, external=True, plan=None):
    """Defense in depth: drop identifiers, unrequested records and withheld answers."""
    source = req.learningContext or {}
    plan = plan or req.preparedPlan
    reads = set(plan.reads) if plan else set()
    requested_categories = {"wrong" if value == "practice" else value for value in reads}
    scopes = set(req.privacy.scopes)
    result = {}
    if isinstance(source.get("statistics"), dict) and "stats" in reads and (not external or "stats" in scopes):
        stats = source["statistics"]
        clean = _fields(stats, ("questionCount", "correctCount", "uniqueQuestions", "wrongCount", "accuracy", "from", "to", "subject"))
        for name in ("daily", "knowledgePoints"):
            clean[name] = [_fields(row, ("date", "statDate", "knowledgePoint", "name", "questionCount", "correctCount", "accuracy", "count", "correct"))
                           for row in stats.get(name, [])[:366] if isinstance(row, dict)]
        result["statistics"] = clean
    items = []
    for item in source.get("items", [])[:20]:
        if not isinstance(item, dict) or not re.fullmatch(r"Q[1-9]\d{0,2}", str(item.get("ref", ""))):
            continue
        kind = item.get("scope", item.get("kind"))
        if kind not in {"wrong", "favorite", "practice", "questions"}:
            # Unknown sensitivity must not be inferred from a model's read plan.
            if external:
                continue
            kind = next((value for value in ("wrong", "favorite", "practice") if value in reads), None)
        category = "wrong" if kind == "practice" else kind
        if category not in requested_categories or external and category != "questions" and category not in scopes:
            continue
        clean = _fields(item, ("ref", "subject", "knowledgePoint", "content", "optionA", "optionB", "optionC", "optionD",
                               "difficulty", "userAnswer", "correct", "answered", "inWrongBook", "version", "snapshotStatus", "snapshotMissing", "notice", "scope", "kind", "matchMethod", "matchTopic"))
        if category == "questions":
            for field in ("userAnswer", "correct", "inWrongBook"):
                clean.pop(field, None)
            clean["answered"] = False
        if category != "questions" and item.get("answered") is True and not item.get("snapshotMissing"):
            clean.update(_fields(item, ("answer", "analysis")))
        items.append(clean)
    if items:
        result["items"] = items
        source_categories = source.get("scope", [])
        if not isinstance(source_categories, list):
            source_categories = [source_categories]
        source_categories = {"wrong" if value == "practice" else value for value in source_categories}
        # A union total may reveal the size of an unconsented collection even
        # when every emitted item individually passes its category check.
        if not external or (source_categories <= scopes | {"questions"} and len(items) == len(source.get("items", [])[:20])):
            result.update(_fields(source, ("total", "readCount", "notice")))
        else:
            result["readCount"] = len(items)
            result["notice"] = "仅包含本轮已授权类别的记录节选；其他类别总量未提供。"
    if "documents" in reads:
        docs = []
        for item in source.get("documents", [])[:5]:
            if not isinstance(item, dict):
                continue
            # Published materials are public. Personal notes require the explicit
            # selected document path and document scope, never this collection.
            if item.get("personal") or item.get("kind") in {"personal", "personal_document"}:
                continue
            if not re.fullmatch(r"D[1-9]\d{0,2}", str(item.get("ref", ""))):
                continue
            docs.append(_fields(item, ("ref", "title", "content", "locator", "version", "excerpt", "truncated", "source")))
        result["documents"] = docs
    refs = {item["ref"] for name in ("items", "documents") for item in result.get(name, [])}
    if "statistics" in result:
        refs.update(str(e.get("ref")) for e in source.get("evidence", [])
                    if isinstance(e, dict) and e.get("kind") in {"stats", "statistics"})
    result["evidence"] = [_fields(item, ("ref", "kind", "title", "locator", "version"))
                          for item in source.get("evidence", [])[:30]
                          if isinstance(item, dict) and item.get("ref") in refs]
    if not external:
        result.update(_fields(source, ("retrievalStatus", "notice", "matchTopic")))
    return result


class LearningAnswer(StrictModel):
    answer: str = Field(min_length=1, max_length=12000)
    evidenceRefs: list[str] = Field(default_factory=list, max_length=30)
    sourceIds: list[str] = Field(default_factory=list, max_length=5)


def rule_learning_answer(context, plan):
    lines = []
    if context.get("notice"):
        lines.append(context["notice"])
    if context.get("matchTopic"):
        lines.append("筛选主题：" + context["matchTopic"])
    stats = context.get("statistics")
    if stats:
        count = stats.get("questionCount", 0)
        if not count:
            lines.append("所选区间暂无有效已提交作答，不能据此判断掌握程度。")
        else:
            lines.append(f"记录事实：{stats.get('from', '')}至{stats.get('to', '')}有效作答{count}次，正确{stats.get('correctCount', 0)}次，去重题数{stats.get('uniqueQuestions', '未记录')}。")
        for point in stats.get("knowledgePoints", []):
            name = point.get("knowledgePoint", point.get("name", "未标注知识点"))
            n = point.get("questionCount", point.get("count", 0))
            lines.append(f"{name}：有效作答{n}次" + ("，样本不足5次，暂不判断掌握程度。" if n < 5 else "；可结合具体错题分析可能错因。"))
        lines.append("学习时长、提示辅助与独立作答：未记录。")
    items = context.get("items", [])
    if items:
        lines.append(f"本次读取{len(items)}条记录，总量{context.get('total', len(items))}；列表节选不代表全部学习情况。")
        for item in items:
            lines.append(f"[{item['ref']}] {item.get('knowledgePoint') or item.get('subject') or '题目'}："
                         + (("知识点匹配" if item.get("matchMethod") == "LABEL" else "语义相关") + "；" if item.get("matchMethod") else "")
                         + (item.get("content", "")[:180] + "；" if item.get("matchMethod") else "")
                         + ("历史快照缺失，不能补造当时题干与答案。" if item.get("snapshotMissing") else
                            "尚未提交，标准答案与完整解析保持隐藏。" if not item.get("answered") else
                            "最近一次已提交作答正确；仍保留在错题本。" if item.get("inWrongBook") and item.get("correct") == 1 else
                            "已提交作答，可据该版本回顾。"))
    for doc in context.get("documents", []):
        lines.append(f"[{doc['ref']}] {doc.get('title', '备考资料')}：{(doc.get('content') or doc.get('excerpt') or '')[:1500]}")
    if plan.operation != "NONE":
        lines.append("已识别操作意图，是否执行以及执行结果由业务后端核验；需要确认的操作请先查看预览。")
    if not lines:
        lines.append("没有读取到本次请求所需记录。请明确对象或筛选范围；未授权外发时仍可使用本地页面功能。")
    if context.get("retrievalStatus") == "READY" and not items:
        lines.append("没有找到符合该主题的题目，未修改记录。")
    return "\n".join(lines)
