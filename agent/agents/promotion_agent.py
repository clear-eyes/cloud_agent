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
from langchain_mcp_adapters.client import MultiServerMCPClient
from typing import Dict, Any

from agent.agents.billing_agent import UserIdInjector
from agent.core import AgentState
from agent.core.mcp.config_loader import load_mcp_servers_config


class PromotionAgentNode:
    """
    推广 Agent：负责处理用户的产品分享、返佣、活动查询和推广物料获取请求。
    所有的工具调用都通过 FastMCP 服务从后端营销系统中获取。
    """
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
        load_dotenv(dotenv_path)

        self.llm = ChatOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=os.getenv("MODEL", "qwen-plus"),
            base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=0.3, # 营销话术可以稍微有一点创造性
        )
        
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'mcp_servers.json')
        self.servers_config = load_mcp_servers_config(config_path)

    async def _ensure_tools(self):
        pass

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        config = {"configurable": {"user_id": state.get("user_id", "unknown")}}
        
        # 每次调用重新初始化 MCP 客户端，避免使用不支持的 async with
        client = MultiServerMCPClient(
            connections=self.servers_config,
            tool_interceptors=[UserIdInjector()]
        )
        all_tools = await client.get_tools()
        target_tools = ["get_promotable_products", "search_product_catalog", "get_promotion_materials", "generate_ai_poster"]
        tools = [t for t in all_tools if t.name in target_tools]

        memory_context = state.get("memory_context", "")
        
        system_prompt = f"""你是一个热情的云服务平台【推广营销Agent】。
            你的主要任务是帮助想要分享或推广云产品的用户，提供对应的产品亮点、专属推广链接，并使用 AI 为其生成专属推广海报。
            
            工作流程：
            1. **意图：随便看看/列出商品**：当用户仅仅说“我想推广商品”、“有哪些商品可以推广”、“我要赚钱”时，你必须**首先调用 `get_promotable_products`** 工具，获取系统当前所有支持推广的产品列表，并展示给用户，引导用户进行选择（可以给商品编上序号）。**此时不要调用生成物料的工具，等待用户回复。**
            2. **意图：明确选择商品**：当用户在上一轮列表中做出了选择（例如“我要推第1个”、“选GPU”），或者用户一开始就明确表达了要推广某款具体产品（如“云服务器ECS标准型”）时：
               - 你必须**首先调用 `search_product_catalog`** 工具，传入用户选择的关键词或编号对应的商品名，以获取标准化的 `product_id`。
            3. **处理未找到的情况**: 
               - 如果 `search_product_catalog` 返回 `status: not_found`，**不要捏造产品**！
               - 你应该诚实地告诉用户目前该款产品暂无特定的单品推广活动，并向用户推荐工具返回的通用活动（如 `P_ALL_000`）。
            4. **获取精准物料与生成海报**: 
               - 拿到合法的 `product_id` 后，你必须调用 `get_promotion_materials` 工具，获取具体的专属链接和卖点。
               - **紧接着，你必须调用 `generate_ai_poster` 工具**，根据该产品的卖点和特性，自己构思一段丰富的英文或中文 Prompt（例如："A futuristic cloud server room, glowing blue neon lights, high tech, 9:16 aspect ratio"），让系统生成一张竖屏的专属推广海报。由于生图可能需要几十秒，请在调用前或在结果中自然地安抚用户。
            
            注意：
            - 系统会自动注入用户的 user_id，你在调用 `get_promotion_materials` 时，user_id 参数写个占位符如 "auto" 即可。
            - 最终的回答必须包含：
              1. 热情的开场白，提一下当前产品的返佣比例。
              2. 产品核心卖点包装。
              3. 明确的专属推广链接。
              4. 使用 Markdown 图片语法展示通过 `generate_ai_poster` 生成的海报 URL（如 `![专属海报](URL)`）。
            
            【系统提供的用户记忆/背景上下文】:
            {memory_context if memory_context else "暂无背景上下文。"}
            """
        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt
        )
        
        print("📢 [PromotionAgent] 正在生成营销与推广物料...")
        
        result = await inner_agent.ainvoke(
            {"messages": state["messages"]}, 
            config=config
        )
        
        final_message = result["messages"][-1]
        return {"messages": [final_message]}
