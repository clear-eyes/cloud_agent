import asyncio
from core.workflow.graph_manager import AgentGraphManager

async def test_multi_turn():
    manager = AgentGraphManager()
    graph = manager.build_graph()
    
    state = {
        "messages": [],
        "user_id": "user_999",
        "session_id": "test_session_multi",
        "memory_context": "",
        "next_agent": "",
        "metadata": {}
    }
    
    # 第一轮：含糊的推广意图
    user_msg_1 = "我想推广商品赚钱，有什么可以推的？"
    print(f"\n👤 User: {user_msg_1}")
    state["messages"].append(("user", user_msg_1))
    result = await graph.ainvoke(state)
    state["messages"] = result["messages"]
    print(f"\n🤖 AI: {result['messages'][-1].content}\n")
    
    # 第二轮：根据列表做出选择
    user_msg_2 = "我要推第2个，那个计算型的ECS"
    print(f"\n👤 User: {user_msg_2}")
    state["messages"].append(("user", user_msg_2))
    
    # 将 user_id 传给 config 让底层拦截器能读到
    config = {"configurable": {"user_id": "user_999"}}
    result = await graph.ainvoke(state, config=config)
    print(f"\n🤖 AI: {result['messages'][-1].content}\n")

if __name__ == "__main__":
    asyncio.run(test_multi_turn())