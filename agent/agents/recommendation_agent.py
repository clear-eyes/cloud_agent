"""
 * 小滴课堂,愿景：让技术不再难学
 * @Remark 有问题联系我【xdclass68】
 * 源码-笔记-技术交流群,官网 https://xdclass.net
"""
import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from typing import Dict, Any
from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.agents.billing_agent import UserIdInjector
from agent.core import AgentState
from agent.tools.vector_tool import query_vector_db
from agent.core.mcp.config_loader import load_mcp_servers_config


class RecommendationAgent:
    """
    智能推荐 Agent：负责根据用户的业务需求（类型、预算、并发等）进行云产品选型与推荐。
    它会调用向量数据库了解产品特性，并结合 MCP 获取真实可用的商品列表。
    """
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
        load_dotenv(dotenv_path)

        self.llm = ChatOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=os.getenv("MODEL", "qwen-plus"),
            base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=0.3, # 推荐场景需要一点灵活性，但不宜过高
        )
        
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'mcp_servers.json')
        self.servers_config = load_mcp_servers_config(config_path)

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        memory_context = state.get("memory_context", "")
        config = {"configurable": {"user_id": state.get("user_id", "unknown")}}
        
        # 获取 MCP 工具（用于拉取商品库）
        client = MultiServerMCPClient(
            connections=self.servers_config,
            tool_interceptors=[UserIdInjector()]
        )
        all_tools = await client.get_tools()
        # 我们需要 search_product_catalog 和 get_promotable_products 来拉取商品
        # 并引入 get_promotion_materials 获取最终的下单/推广链接
        target_tools = ["get_promotable_products", "search_product_catalog", "get_promotion_materials"]
        mcp_tools = [t for t in all_tools if t.name in target_tools]
        
        # 组合向量工具与 MCP 工具
        tools = [query_vector_db] + mcp_tools

        system_prompt = f"""你是一个资深的云架构师和【智能推荐Agent】。
        你的任务是根据用户的业务场景（如：Java+MySQL、高并发、特定预算），推荐最合适的云产品型号。
        
        【工作流程】
        1. 分析用户的业务需求（业务类型、日活/并发、预算、地域等）。如果用户只是单纯询问“有哪些产品”，请跳过分析，直接展示当前平台的商品库。
        2. (必须) 调用 `get_promotable_products` 或 `search_product_catalog` 获取当前平台可供推荐和购买的真实商品列表。
        3. 如果是选型推荐，调用 `query_vector_db` 检索相关规格（如 c7, g8a）的技术特性和适用场景。
        4. 为用户精选 1-3 款最合适的商品，并给出专业的推荐理由（为什么选这款，满足了用户的什么痛点）。如果是询问列表，直接结构化列出。
        5. (非常重要) 在推荐结论中，针对你推荐的商品，调用 `get_promotion_materials` 获取购买/活动链接，并在最终回复中附上这些直接购买链接。
        
        【回答要求】
        - 语气要像专业且热情的云架构师顾问。
        - 必须包含具体的实例型号或产品名称。
        - 必须条理清晰（使用列表、加粗）。
        - 绝不要推荐 `get_promotable_products` 列表中不存在的虚构商品。
        - 每次回答结尾，只需列出实际获取到数据的来源，格式如下：
          答案来源：
          - 向量检索：xxx.md
          （不要输出“未使用”的工具或“可信度”）
        
        【系统提供的用户记忆/背景上下文】:
        {memory_context if memory_context else "暂无背景上下文。"}
        """
        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt
        )
        
        print("🔍 [RecommendationAgent] 正在进行智能产品选型与推荐...")
        
        result = await inner_agent.ainvoke(
            {"messages": state["messages"]},
            config=config
        )
        final_message = result["messages"][-1]
        return {"messages": [final_message]}
