def inspect_text(text: str) -> dict:
    """只统计本次输入，不执行用户提供的代码或表达式。"""
    return {"characters": len(text), "nonemptyLines": sum(bool(line.strip()) for line in text.splitlines())}
