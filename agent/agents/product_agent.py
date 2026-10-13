import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import create_react_agent

# from tools.vector_tool import query_vector_db
# from tools.graph_tool import query_knowledge_graph
# from core.workflow.state import AgentState
from typing import Dict, Any
# 导入已经封装好的工具
from agent.core import AgentState
from agent.tools.graph_tool import query_knowledge_graph
from agent.tools.vector_tool import query_vector_db


class ProductAgentNode:
    """
    包装了 LangGraph create_react_agent 的节点类
    供主图编排时直接调用
    """
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        load_dotenv(dotenv_path)

        self.llm = ChatOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=os.getenv("MODEL", "qwen-plus"),
            base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=0.1, 
        )
        self.tools = [query_vector_db, query_knowledge_graph]

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        供主 LangGraph 调用的处理函数
        """
        memory_context = state.get("memory_context", "")
        system_prompt = f"""你是一个专业的云服务平台【产品咨询Agent】。
            你的任务是解答用户关于云产品（如云服务器ECS、专有网络VPC等）的疑问。
            你有两个强大的检索工具可供使用：
            
            1. `query_vector_db` (向量数据库检索):
               - 适用场景: 查询大段的概念解释、操作步骤说明、详细的规则政策。
               - 特点: 擅长处理模糊的语义匹配和长文本阅读。
            
            2. `query_knowledge_graph` (知识图谱检索):
               - 适用场景: 查询云产品的架构、实体包含关系、具体的配置数值与限制、组合查询等结构化数据。
               - 特点: 擅长处理精确的属性、关系和多跳拓扑查询。
            
            工作要求：
            - 仔细分析用户的问题，自主决定使用哪个工具，或者结合使用两个工具（如果问题很复杂）。
            - 如果问题偏结构化参数（如网卡数、带宽、实例关系），优先尝试 `query_knowledge_graph`；若图谱查询超时或失败，自动降级为 `query_vector_db` 并继续完成回答。
            - 如果问题同时包含结构化参数和规则解释，建议组合使用两个工具；但以可用性优先，不强制必须调用图谱。
            - 优先通过工具获取事实依据，不要凭空捏造（幻觉）。
            - 获取到信息后，请以专业、清晰、友好的客服口吻组织回答。
            - 如果工具返回没有找到相关信息，请诚实地告诉用户目前知识库中没有相关记录。
            - 答案来源只能引用工具原始返回中明确出现的来源名；禁止编造任何文档名、版本号、白皮书名称。
            - 如果某工具未调用或调用失败，不要在“答案来源”中提及该工具，也不要解释为什么失败。
            - 每次最终回答的结尾，只需列出实际获取到数据的来源，不要输出“可信度”，也不要输出“未使用”的工具。
              格式示例：
              答案来源：
              - 向量检索：xxx.md
              （如果只用到了向量检索，就只输出这一行；如果只用到了图谱，就只输出图谱检索结果；都用到了就输出两行）
            
            【系统提供的用户记忆/背景上下文】:
            {memory_context if memory_context else "暂无背景上下文。"}
            """
        # 使用 create_react_agent 创建一个内部的执行器
        inner_agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt
        )
        
        print("💡 [ProductAgent] 正在处理产品咨询请求...")
        
        # 传递整个对话历史给内部 agent
        result = await inner_agent.ainvoke({"messages": state["messages"]})
        
        # 提取最后一条 AI 消息返回给主图
        final_message = result["messages"][-1]
        
        # 为了兼容主图的消息追加，我们将返回包装在 messages 列表中
        return {"messages": [final_message]}

def get_product_agent():
    """保留给独立测试用的入口"""
    pass

if __name__ == "__main__":
    # 简单的交互式测试入口
    agent = get_product_agent()
    
    print("🤖 ProductAgent 已启动！(输入 'quit' 或 'exit' 退出)")
    print("=" * 50)
    print("您可以尝试问我：")
    print("1. [图谱测试] ecs.g8a.4xlarge 实例能挂载多少块弹性网卡？")
    print("2. [向量测试] 五天无理由退款有什么限制条件吗？")
    print("3. [混合测试] 什么是专有网络VPC？另外华北2（北京）地域有哪些实例规格族？")
    print("=" * 50)

    # 需要传入一个线程ID以维持上下文（如果需要记忆的话），这里简单测试每次生成新的即可
    config = {"configurable": {"thread_id": "test_thread_1"}}

    while True:
        user_input = input("\n👤 用户: ")
        if user_input.lower() in ['quit', 'exit']:
            break
            
        if not user_input.strip():
            continue

        print("\n🤖 正在思考并检索...")
        
        # 调用 Agent
        try:
            # stream_mode="values" 可以让我们拿到状态的最后结果
            for event in agent.stream({"messages": [("user", user_input)]}, config=config, stream_mode="values"):
                # 获取最后一条消息
                last_message = event["messages"][-1]
                # 打印工具调用过程（可选，为了演示清晰）
                if getattr(last_message, "tool_calls", None):
                    for tc in last_message.tool_calls:
                        print(f"   [Tool Call] 正在调用工具: {tc['name']} (参数: {tc['args']})")
            
            # 最终回答
            final_message = event["messages"][-1].content
            print(f"\n💡 ProductAgent: {final_message}")
        except Exception as e:
            print(f"\n❌ 发生错误: {str(e)}")
