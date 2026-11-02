"""Deterministic intent hints for explicit study plans and compound requests."""

import logging
import re

from pydantic import GetJsonSchemaHandler, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from core.admission_contract import AdmissionSource, load_sources
from intents import ConditionExtractor, IntentResolver, chinese_number, local_learning_plan, positive_request
from schemas import (
    AdmissionLinksQuery,
    ConversationRequest,
    ConversationResolution,
    ExpertStep,
    SchoolLookupQuery,
)

log = logging.getLogger(__name__)

ADMISSION_EXAMPLE = "查官网南京审计大学。"
REGISTRY_UNAVAILABLE = "招生官网登记配置暂不可用，请联系维护者检查后重试。"
ADMISSION_TRIGGER = (
    r"查(?:询|看)?(?:一下)?(?:学校)?官网|"
    r"(?:大学|学院)\s*(?:查|看)(?:一下)?官网|"
    r"(?:核验|核对|查询|查|给我|提供|要|看看).{0,30}"
    r"(?:招生信息|招生网址|招生官网|招生公告|招生目录|官网)|"
    r"(?:招生信息|招生网址|招生官网|招生公告|招生目录)"
)
ADMISSION_EXCLUSION = r"不要|不必|不需要|别查|别帮|示例|例如|这句话|这个指令|如何|怎么|功能介绍|假设"
# Admission lookups are single-action plans; another explicit task in the same
# turn must not be silently dropped. Java AdmissionLinksValidator mirrors both.
ADMISSION_COMPOUND = (
    r"解释|讲解|知识问答|是什么|什么是|复习计划|学习计划|安排.{0,8}(?:复习|学习)|笔记|错题|学情|"
    r"学习情况|正确率|刷题|出题|组题|做.{0,8}题|练习|择校|推荐.{0,6}(?:院校|学校)"
)
ADMISSION_SPLIT = (
    "本轮同时包含招生查询和其他事项，一次只能处理一类。"
    "请先单独发送招生查询（如“查询北京大学招生信息”），再另行发送其他问题。"
)
SCHOOL_NAME = re.compile(r"[^\s和与及、，。；：,;:\ufffc]{2,24}?(?:大学|学院)")
COMMAND_PREFIX = re.compile(
    r"^(?:请帮我|帮我|帮忙|麻烦|请问|查询|查一下|核对|查|给我|我要|我想|想|"
    r"了解|关于|提供|看看|看|一下|推荐|找|问|和|与|及|、|的|请|官网|学校官网)+"
)


class ModelConversationResolution(ConversationResolution):
    """Parse model plans without allowing them to authorize admission requests."""

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        """Keep Java-only lookup parameters out of model input and its budget."""
        schema = handler.resolve_ref_schema(handler(core_schema))
        schema["properties"].pop("schoolLookup", None)
        actions = schema["properties"]["action"]["enum"]
        schema["properties"]["action"]["enum"] = [
            action for action in actions if action != "SCHOOL_LOOKUP"
        ]
        return schema

    @model_validator(mode="before")
    @classmethod
    def refuse_admission(cls, value: object) -> object:
        """Discard model admission fields before nested query validation can fail."""
        if isinstance(value, dict) and (
            value.get("action") in {"ADMISSION_CHECK", "ADMISSION_LINKS", "SCHOOL_LOOKUP"}
            or value.get("admissionCheck") is not None
            or value.get("admissionLinks") is not None
            or value.get("schoolLookup") is not None
        ):
            query = value.get("standaloneQuery")
            return {
                "action": "CHAT",
                "standaloneQuery": query
                if isinstance(query, str) and query.strip()
                else "招生官网链接查询",
                "clarification": "招生官网链接仅由服务端按登记院校生成。\n推荐问法："
                + ADMISSION_EXAMPLE,
            }
        return value


def admission_scope_requested(text: str) -> bool:
    """Recognize a registry-scope question without authorizing a network request."""
    return bool(
        re.search(
            r"(?:哪些|哪几|什么)(?:所|个)?(?:学校|院校|大学)|"
            r"学校名单|院校名单|支持.{0,6}(?:学校|院校)",
            text,
        )
        and re.search(r"官网|招生网址|招生信息|核验|登记", text)
        and not re.search(ADMISSION_EXCLUSION, text)
    )


def registered_sources() -> dict[str, AdmissionSource] | None:
    """Read the trusted registry; a broken file degrades to a maintainer notice."""
    try:
        return load_sources()
    except (OSError, ValueError) as error:
        log.warning("admissionRegistryFailure=%s", type(error).__name__)
        return None


def admission_source_answer() -> str:
    """List registered school links and require the user to confirm details manually."""
    sources = registered_sources()
    if sources is None:
        return REGISTRY_UNAVAILABLE
    lines = [
        f"当前登记{len(sources)}所院校的官网入口如下；登记年份不代表网址当前内容年份，"
        "请自行确认招生年份、专业及报考条件。部分入口为学校主页，请从研究生招生栏目继续查阅。"
    ]
    for source in sources.values():
        lines.append(f"- {source.name}（登记年份 {source.year}）")
        lines.extend(
            f"  - [官网入口{index}]({url})"
            for index, url in enumerate(source.entries, 1)
        )
    return "\n".join(lines)


def _admission_scope_hint() -> str:
    """Keep missing-school guidance bounded as the registry grows."""
    sources = registered_sources()
    if sources is None:
        return REGISTRY_UNAVAILABLE
    return (
        f"当前登记{len(sources)}所院校；发送“你可以查询哪些学校官网”查看完整范围。"
    )


def _clean_school_name(value: str) -> str:
    """Remove a leading command phrase from a generic school-name match."""
    previous = None
    while value and value != previous:
        previous = value
        value = COMMAND_PREFIX.sub("", value, count=1)
    return value


def explicit_schools(text: str) -> list[tuple[str, AdmissionSource | None]]:
    """Return one explicit registered or generic school; never infer from history."""
    sources = registered_sources() or {}
    # Mask exact registered names first so surrounding polite text cannot invent
    # another school, while a second unregistered school still requires clarification.
    # Longer names win at the same occurrence; a separate mention of the shorter
    # school's name must still count (e.g. 矿大北京和矿大 are distinct institutions).
    found: dict[str, AdmissionSource | None] = {}
    remaining = text.replace("(", "（").replace(")", "）")
    for source in sorted(sources.values(), key=lambda source: len(source.name), reverse=True):
        if source.name in remaining:
            found[source.name] = source
            remaining = remaining.replace(source.name, "\ufffc")
    found = {source.name: source for source in sources.values() if source.name in found}
    for match in SCHOOL_NAME.finditer(remaining):
        name = _clean_school_name(match.group(0))
        if len(name) < 4 or not name.endswith(("大学", "学院")) or name in found:
            continue
        # A college suffix after a named school is a department, not a second school.
        if (
            name.endswith("学院")
            and remaining[:match.start()].rstrip().endswith("\ufffc")
        ):
            continue
        found[name] = None
    return list(found.items())


def admission_requested(text: str) -> bool:
    """Only an explicit current link lookup can authorize the local admission tool."""
    return bool(re.search(ADMISSION_TRIGGER, text)) and not bool(
        re.search(ADMISSION_EXCLUSION, text)
    ) and not admission_scope_requested(text)


def admission_compound(text: str) -> bool:
    """Whether an admission request also asks for another capability."""
    return bool(re.search(ADMISSION_COMPOUND, text))


def school_lookup_plan(req: ConversationRequest) -> ConversationResolution | None:
    """Resolve public catalog lookups locally; database reads belong only to Java."""
    text = req.userInput
    if not admission_requested(text) or re.search(r"官网|网址|链接|核对|核验", text):
        return None
    schools = explicit_schools(text)
    years = set(re.findall(r"(?<!\d)(20\d{2}|2100)(?:年)?(?!\d)", text))
    majors = set(re.findall(r"(?<!\d)\d{6}(?!\d)", text))
    clarification = None
    if admission_compound(text):
        clarification = ADMISSION_SPLIT
    elif len(schools) != 1:
        clarification = "请提供一个院校全名。" if not schools else "本轮包含多所院校，请只选择一所。"
    elif len(years) > 1 or len(majors) > 1:
        clarification = "请指定一个招生年份和一个专业代码，或省略这些筛选条件。"
    query = None if clarification else SchoolLookupQuery(
        schoolName=schools[0][0],
        year=int(next(iter(years))) if years else None,
        majorCode=next(iter(majors)) if majors else None,
    )
    return ConversationResolution(
        action="SCHOOL_LOOKUP", standaloneQuery=text, schoolLookup=query,
        clarification=clarification,
    )


def admission_links_plan(req: ConversationRequest) -> ConversationResolution | None:
    """Extract exactly one registry school or ask a bounded clarification."""
    if not admission_requested(req.userInput):
        return None
    text = req.userInput
    if admission_compound(text):
        # A CHAT clarification: Java rejects a link plan that only clarifies
        # one registered school, and no link parameters may be carried.
        return ConversationResolution(action="CHAT", standaloneQuery=text, clarification=ADMISSION_SPLIT)
    if registered_sources() is None:
        return ConversationResolution(
            action="ADMISSION_LINKS", standaloneQuery=text, clarification=REGISTRY_UNAVAILABLE,
        )
    schools = explicit_schools(text)
    registered = [source for _, source in schools if source is not None]
    if not schools:
        issues = [
            "请提供一个院校全名。",
            _admission_scope_hint(),
        ]
        query = None
    elif len(schools) > 1:
        issues = ["本轮包含多所院校，请只选择一所。"]
        query = None
    elif registered:
        source = registered[0]
        issues = []
        query = AdmissionLinksQuery(schoolCode=source.code)
    else:
        issues = [
            f"“{schools[0][0]}”未登记，当前不能提供招生官网链接。",
            _admission_scope_hint(),
        ]
        query = None
    return ConversationResolution(
        action="ADMISSION_LINKS",
        standaloneQuery=text,
        admissionLinks=query,
        clarification=None if query is not None else "".join(issues),
    )


def basic_dialogue(text: str) -> bool:
    """Recognize greetings and product guidance without an external model call."""
    return bool(
        re.fullmatch(
            r"\s*(?:你好|您好|嗨|hello|hi|你能做什么|介绍一下你自己)[！!。.?？\s]*",
            text,
            re.I,
        )
        or re.search(r"(?:跳过诊断|先了解).{0,12}(?:介绍|功能|了解)", text)
    )


def local_orchestration(req: ConversationRequest) -> ConversationResolution | None:
    """Build only a bounded expert graph; writes still come from current intent."""
    text = req.userInput
    if admission_scope_requested(text):
        return ConversationResolution(action="CHAT", standaloneQuery=text)
    lookup_plan = school_lookup_plan(req)
    if lookup_plan is not None:
        return lookup_plan
    links_plan = admission_links_plan(req)
    if links_plan is not None:
        return links_plan
    if basic_dialogue(text):
        return ConversationResolution(action="CHAT", standaloneQuery=text)
    if re.search(r"这句话|这个指令|示例|例如|假设|功能介绍|(?:如何|怎么).{0,12}(?:使用|按钮|功能|创建|收藏|查看|修改|制定|安排)|(?:出题|组题|练习)(?:功能|按钮|流程)", text):
        return ConversationResolution(action="CHAT", standaloneQuery=text)
    signals = IntentResolver.inspect(text)
    note, study = signals.note, signals.study
    practice_plan = local_learning_plan(text, req.pageContext)
    practice = (
        practice_plan is not None and practice_plan.operation != "NONE"
    )
    if note and practice and practice_plan.operation == "PRACTICE_CREATE" and not re.search(r"笔记要整理(?:知识讲解|练习题目|已完成作答)", text):
        return ConversationResolution(
            action="CHAT",
            standaloneQuery=text,
            clarification="已识别练习和笔记两项请求。请先明确笔记要整理知识讲解、练习题目还是已完成作答；明确前不会创建练习或笔记建议。",
        )
    # Ordinary note editing preserves its selected version and write guards.
    if note and req.document is not None and not study and not practice and not signals.school and not signals.knowledge:
        return None
    school, learning, knowledge = signals.school, signals.learning, signals.knowledge
    if practice and not re.search(r"分析|学情|学习情况|统计|诊断|正确率|掌握", positive_request(text)):
        learning = False
    selected = []
    if learning or study:
        selected.append("LEARNING")
    if study:
        selected.append("STUDY_PLAN")
    if knowledge:
        selected.append("KNOWLEDGE")
    if school:
        selected.append("SCHOOL")
    if practice:
        selected.append("PRACTICE")
    if note:
        selected.append("NOTE")
    if not study and (len(selected) < 2 or (note and not school and not knowledge and not practice)):
        return None
    if re.search(r"如何|怎么|功能|是什么意思|例如|假设", text) and not study:
        return None
    steps = []
    for name in selected:
        dependencies = []
        if name in {"STUDY_PLAN", "SCHOOL"} and "LEARNING" in selected:
            dependencies.append("LEARNING")
        if "STUDY_PLAN" in selected and (name == "NOTE" or name == "PRACTICE" and practice_plan.operation == "PRACTICE_CREATE"):
            dependencies.append("STUDY_PLAN")
        steps.append(ExpertStep(agent=name, dependsOn=dependencies))
    fields = practice_plan.model_dump(by_alias=True) if practice_plan else {}
    fields.update(
        action="STUDY_PLAN" if study and not school and not practice else "MULTI_AGENT",
        standaloneQuery=text,
        planVersion=2,
        steps=steps,
    )
    reads = set(fields.get("reads", []))
    if "LEARNING" in selected or "STUDY_PLAN" in selected:
        reads.add("stats")
        if "错题" in text:
            reads.add("wrong")
    fields["reads"] = sorted(reads)
    if not practice:
        fields.update(operation="NONE", target="selected")
    if ConditionExtractor.conflicting(text):
        fields.update(
            clarification="本轮出现多个年份或学位条件，请明确希望采用的条件。",
            operation="NONE",
            reads=[],
        )
    fields["conditionPatch"] = ConditionExtractor.extract(text)
    counts = {
        chinese_number(value) for value in re.findall(
            r"([0-9零一二两三四五六七八九十百千]+)\s*天", positive_request(text)
        )
    } if study else set()
    if len(counts) > 1 or any(not 1 <= value <= 30 for value in counts):
        fields.update(clarification="复习计划支持1至30天，请指定一个明确的天数。", reads=[], operation="NONE")
    fields["studyDays"] = next(iter(counts)) if len(counts) == 1 and 1 <= next(iter(counts)) <= 30 else 7
    if fields.get("clarification"):
        fields.update(action="CHAT", steps=[], planVersion=1, reads=[], operation="NONE")
    return ConversationResolution.model_validate(fields)
