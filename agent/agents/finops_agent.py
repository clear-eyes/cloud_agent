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


class FinOpsAgentNode:
    """
    FinOps Agent：成本优化与架构诊断专家。
    负责分析用户的资源监控数据，判断是否存在资源浪费，并给出降本增效的建议。
    """
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
        load_dotenv(dotenv_path)

        self.llm = ChatOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=os.getenv("MODEL", "qwen-plus"),
            base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=0.1, 
        )
        
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'mcp_servers.json')
        self.servers_config = load_mcp_servers_config(config_path)

    async def _ensure_tools(self):
        pass

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        config = {"configurable": {"user_id": state.get("user_id", "unknown")}}

        client = MultiServerMCPClient(
            connections=self.servers_config,
            tool_interceptors=[UserIdInjector()]
        )
        all_tools = await client.get_tools()
        target_tools = ["query_user_instances", "analyze_instance_usage"]
        tools = [t for t in all_tools if t.name in target_tools]
        
        system_prompt = f"""你是一个专业的云上【FinOps成本优化专家】。
            你刚刚接手了上一个 Agent (BillingAgent) 传递过来的上下文。
            
            你的任务：
            1. 仔细阅读上下文中的对话历史，优先提取用户想要优化的**实例 ID (instance_id)**。
            2. 如果上下文中没有 instance_id，先调用 `query_user_instances` 获取该用户实例列表，并优先选择 Running 状态的 ECS 实例继续分析；如果有多台实例，可先给出清单并建议用户指定目标。
            3. 调用 `analyze_instance_usage` 工具获取目标实例近期 CPU、内存等监控数据。
            4. 根据监控数据分析该实例是否存在“资源闲置 (RESOURCES_IDLE)”的情况。
            5. 以云架构师的口吻给用户提出**降本增效建议**：
               - 如果 CPU 长期极低，建议用户将实例降配（例如从 8xlarge 降级为 2xlarge，或从计算型转为通用型）。
               - 估算一下降配带来的好处（如每月可节省大量预算）。
               - 语气要专业、诚恳，完全站在为用户省钱的角度。
            
            注意：系统会自动注入 user_id，调用工具时传占位符 "auto" 即可。
            - 严禁编造实例 ID、监控指标和费用节省金额；必须基于工具返回结果回答。
            - 严禁出现“工具不可用/接口坏了/系统异常”等内部表述，对用户只给业务友好表达。
            """
        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt
        )
        
        print("💡 [FinOpsAgent] 正在接手并分析实例监控指标，生成降本优化报告...")
        
        result = await inner_agent.ainvoke(
            {"messages": state["messages"]}, 
            config=config
        )
        
        final_message = result["messages"][-1]
        
        # 执行完毕后，把 next_agent 清空，代表流程彻底结束
        return {"messages": [final_message], "next_agent": ""}
