"""仅用于真实HTTP链路验证的模型替身；不连接模型供应商或业务数据库。"""
import main
import asyncio

async def answer(*args, **kwargs):
    if args and args[0] == 'simulate-interruption':
        await asyncio.sleep(120)
    return {'answer': 'HTTP链路测试的模拟答案，不代表领域回答', 'references': []}

async def recommend(*args, **kwargs):
    return {'summary': 'HTTP链路测试的模拟推荐，不代表招生建议', 'references': []}

async def summarize(*args, **kwargs):
    return {'summary': 'HTTP链路测试的模拟总结', 'references': []}

async def route(*args, **kwargs):
    return {'intent': 'CHANGUI'}

main.wenda.handle = answer
main.tuijian.handle = recommend
main.summary.handle = summarize
main.changui.handle = answer
main.route = route
app = main.app
