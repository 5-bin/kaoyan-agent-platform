"""只读 question 表。"""
from sqlalchemy import text, bindparam
from db import SessionLocal


async def get_questions_by_ids(question_ids: list[int]) -> list[dict]:
    if not question_ids:
        return []
    sql = text(
        """
        SELECT id, subject, knowledge_point, content,
               option_a, option_b, option_c, option_d,
               answer, analysis, difficulty, question_type
        FROM question
        WHERE id IN :ids AND active = 1 AND review_status = 'APPROVED'
        """
    ).bindparams(bindparam("ids", expanding=True))
    async with SessionLocal() as session:
        result = await session.execute(sql, {"ids": question_ids})
        return [dict(r) for r in result.mappings().all()]
