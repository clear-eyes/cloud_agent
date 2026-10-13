import os
import sys
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_neo4j import Neo4jGraph as NewNeo4jGraph
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate

# 加载环境变量
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

def setup_graphrag():
    """
    初始化 Neo4j 图数据库连接与大模型，并构建 GraphRAG QA Chain
    """
    print("🔌 正在连接 Neo4j 数据库...")
    try:
        graph = NewNeo4jGraph(
            url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password")
        )
        # 刷新图谱的 Schema，让大模型知道图谱里有什么节点和关系
        graph.refresh_schema()
        print("✅ Neo4j 连接成功！图谱 Schema 已加载。")
    except Exception as e:
        print(f"❌ Neo4j 连接失败，请检查数据库状态和配置: {e}")
        sys.exit(1)

    print("🧠 正在初始化 Qwen 大模型...")
    llm = ChatOpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        model=os.getenv("MODEL", "qwen-plus"),
        base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        temperature=0,
    )

    # ========================================================
    # 增强 Cypher 生成的 Prompt 提示词
    # 这一步非常重要！用来指导大模型理解云产品图谱的正确语法
    # ========================================================
    CYPHER_GENERATION_TEMPLATE = """Task:Generate Cypher statement to query a graph database.
Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.

Schema:
{schema}

Important Rules:
1. 节点标签: Region, Zone, InstanceTypeFamily, InstanceType, Storage, BillingRule 等。
2. 注意属性访问: 如果你使用了 RETURN 语句返回某个属性，必须在前面的 MATCH 中给节点赋予一个变量名！
   错误示例: MATCH (:InstanceType {{id: "g8a"}}) RETURN vcpu
   正确示例: MATCH (i:InstanceType {{id: "ecs.g8a.4xlarge"}}) RETURN i.vcpu
3. 注意实体层级: g8a, c7 这种属于 InstanceTypeFamily（规格族）。ecs.g8a.xlarge 这种具体型号才属于 InstanceType（实例规格）。
   如果你要查询具体型号的属性（如 vCPU, memory, eni_count, network_bandwidth），你应该查询 InstanceType 节点，并在它身上找属性。
   如果你要查询整个规格族的说明，去查询 InstanceTypeFamily 节点。
4. 查询返回格式: 返回的信息应尽可能详细，如果返回节点，请使用 RETURN node，而不是只返回 ID。

The question is:
{question}"""

    cypher_prompt = PromptTemplate(
        template=CYPHER_GENERATION_TEMPLATE,
        input_variables=["schema", "question"]
    )

    # 核心：GraphCypherQAChain
    # 它的原理是：自然语言 -> 大模型生成 Cypher 语句 -> Neo4j 执行 -> 大模型将结果转为自然语言回答
    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=cypher_prompt, # 注入我们刚刚编写的专业提示词
        verbose=True, # 开启详细日志，可以看到生成的 Cypher 语句
        return_intermediate_steps=True, # 返回中间步骤（生成的查询和图谱结果）
        allow_dangerous_requests=True, # 允许执行查询
    )
    
    return chain

def chat_with_graph():
    """
    交互式命令行问答
    """
    chain = setup_graphrag()
    
    print("\n" + "="*50)
    print("🤖 智能客服 GraphRAG 已启动！")
    print("你可以用自然语言问我关于云产品的问题了，例如：")
    print("- 北京地域支持哪些抢占式实例？")
    print("- g8a 实例最多能挂载几个弹性网卡？")
    print("- 哪些实例不支持挂载本地 NVMe SSD？")
    print("输入 'exit' 或 'quit' 退出。")
    print("="*50 + "\n")

    while True:
        question = input("🧑 你的问题: ")
        if question.lower() in ['exit', 'quit']:
            print("👋 再见！")
            break
        if not question.strip():
            continue

        try:
            print("⏳ 正在思考并检索图谱...\n")
            result = chain.invoke({"query": question})
            print(f"\n🤖 回答:\n{result['result']}\n")
        except Exception as e:
            print(f"\n❌ 查询发生错误: {e}\n")

if __name__ == "__main__":
    chat_with_graph()