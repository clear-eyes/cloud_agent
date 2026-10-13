import sys
from product_agent import get_product_agent

agent = get_product_agent()
config = {"configurable": {"thread_id": "auto_test"}}

questions = [
    "ecs.g8a.4xlarge 实例能挂载多少块弹性网卡？",
    "五天无理由退款有什么限制条件吗？",
    "什么是专有网络VPC？另外华北2（北京）地域有哪些实例规格族？"
]

for q in questions:
    print(f"\n[{'-'*40}]\n👤 Q: {q}")
    for event in agent.stream({"messages": [("user", q)]}, config=config, stream_mode="values"):
        last_message = event["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            for tc in last_message.tool_calls:
                print(f"🔧 调用工具: {tc['name']}")
    final_message = event["messages"][-1].content
    print(f"🤖 A: {final_message}")
