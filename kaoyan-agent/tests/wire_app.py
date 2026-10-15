"""Isolated HTTP fixture: real RAG envelope and routing, deterministic model output."""
import asyncio
from config import Settings
from main import create_app

app = create_app(Settings(_env_file=None))

async def answer(req):
    if req.userInput == 'simulate-interruption':
        await asyncio.sleep(120)
    return {'outcome': 'COMPLETED', 'answer': 'HTTP链路测试的模拟答案，不代表领域回答', 'references': []}

async def recommend(req):
    return {'outcome': 'UNSUPPORTED', 'answer': 'HTTP链路测试的模拟推荐，不代表招生建议',
            'candidates': [], 'references': []}

async def summarize(req):
    return {'outcome': 'NEEDS_INPUT', 'answer': 'HTTP链路测试的模拟总结', 'references': []}

async def route(req):
    return 'KNOWLEDGE_QA'

app.state.engine.qa = answer
app.state.engine.schools = recommend
app.state.engine.summary = summarize
app.state.engine.resolve = route
