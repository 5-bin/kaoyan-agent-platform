"""未来领域业务的扩展点；不从模型记忆构造招生或正式判分。"""
from .schemas import RunRequest, RunResult


def school_recommendation(request: RunRequest, mode: str) -> RunResult:
    return RunResult(taskId=str(request.taskId), status="unsupported", mode=mode,
        answer="择校工作流已预留。尚未接入经核验的招生资料、档案和筛选工具，当前不能生成院校推荐。",
        steps=["识别择校任务", "检查领域资料与业务工具"], releaseId=request.releaseId,
        data={"candidates": [], "unverifiedCandidates": []})


def wrong_question_tutor(request: RunRequest, mode: str) -> RunResult:
    return RunResult(taskId=str(request.taskId), status="unsupported", mode=mode,
        answer="错题辅导工作流已预留。尚未实现正式题库、判分和作答权限链路，当前不能提供正式错题辅导。",
        steps=["识别错题辅导任务", "检查题库与判分依赖"], releaseId=request.releaseId,
        data={"recommendedQuestionIds": []})
