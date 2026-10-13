import os
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_neo4j import Neo4jGraph
from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool

# 加载环境变量
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

# 全局单例，避免每次调用工具时重复连接数据库
_graph_chain_instance = None
_graph_instance = None

def _get_graph_chain():
    """获取 GraphCypherQAChain 单例"""
    global _graph_chain_instance, _graph_instance
    if _graph_chain_instance is not None:
        return _graph_chain_instance

    print("🔌 [Init] 正在连接 Neo4j 数据库...")
    graph = Neo4jGraph(
        url=os.getenv("NEO4J_URI", "bolt://YOUR_NEO4J_HOST:7687"),
        username=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "YOUR_NEO4J_PASSWORD")
    )
    _graph_instance = graph
    graph.refresh_schema()

    llm = ChatOpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        model=os.getenv("MODEL", "qwen-plus"),
        base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        temperature=0,
    )

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
4. 查询返回格式: 返回的信息应尽可能详细，如果返回节点，请使用 RETURN node，而不是只返回 ID。

The question is:
{question}"""

    cypher_prompt = PromptTemplate(
        template=CYPHER_GENERATION_TEMPLATE,
        input_variables=["schema", "question"]
    )

    _graph_chain_instance = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=cypher_prompt,
        verbose=False, # 工具调用时关闭详细日志，保持输出整洁
        return_intermediate_steps=False, 
        allow_dangerous_requests=True,
    )
    return _graph_chain_instance

def _extract_keywords(query: str) -> list[str]:
    lower_query = query.lower()
    tokens = re.findall(r"[a-z0-9._-]+", lower_query)
    cn_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", query)
    keywords = []
    for token in tokens + cn_tokens:
        if len(token.strip()) >= 2 and token not in keywords:
            keywords.append(token.strip())
    if not keywords:
        keywords.append(lower_query[:20] if lower_query else "ecs")
    return keywords[:8]

def _fallback_graph_keyword_search(query: str) -> str:
    global _graph_instance
    if _graph_instance is None:
        _get_graph_chain()
    
    graph = _graph_instance
    if graph is None:
        return "图谱关键词检索不可用，请稍后重试。"

    keywords = _extract_keywords(query)
    
    # Neo4j 无法在 ANY/WHERE 中动态解包 $keywords 列表用于 CONTAINS 匹配，
    # 因此这里我们采用在 Python 中拼接 OR 语句的简单模式
    
    where_clauses = []
    for k in keywords:
        where_clauses.append(f"toLower(coalesce(n.id, '')) CONTAINS '{k}' OR toLower(coalesce(n.name, '')) CONTAINS '{k}' OR toLower(coalesce(n.description, '')) CONTAINS '{k}'")
    node_where = " OR ".join(where_clauses)
    
    node_cypher = f"""
    MATCH (n)
    WHERE {node_where}
    RETURN labels(n) AS labels, coalesce(n.id, n.name, '') AS node_key, properties(n) AS props
    LIMIT 8
    """
    
    rel_where_clauses = []
    for k in keywords:
        rel_where_clauses.append(f"toLower(coalesce(a.id, '')) CONTAINS '{k}' OR toLower(coalesce(a.name, '')) CONTAINS '{k}' OR toLower(coalesce(b.id, '')) CONTAINS '{k}' OR toLower(coalesce(b.name, '')) CONTAINS '{k}'")
    rel_where = " OR ".join(rel_where_clauses)

    rel_cypher = f"""
    MATCH (a)-[r]->(b)
    WHERE {rel_where}
    RETURN labels(a) AS from_labels, coalesce(a.id, a.name, '') AS from_node,
           type(r) AS rel, labels(b) AS to_labels, coalesce(b.id, b.name, '') AS to_node
    LIMIT 8
    """

    try:
        nodes = graph.query(node_cypher)
        relations = graph.query(rel_cypher)
    except Exception as exc:
        return f"图谱关键词检索失败: {str(exc)}"

    if not nodes and not relations:
        return "未查询到相关图谱信息。"

    parts = ["图谱关键词检索结果："]
    if nodes:
        parts.append("命中节点：")
        for row in nodes:
            labels = ",".join(row.get("labels", []))
            node_key = row.get("node_key", "")
            props = row.get("props", {})
            parts.append(f"- [{labels}] {node_key} {props}")
    if relations:
        parts.append("命中关系：")
        for row in relations:
            from_labels = ",".join(row.get("from_labels", []))
            to_labels = ",".join(row.get("to_labels", []))
            parts.append(f"- [{from_labels}] {row.get('from_node', '')} -[{row.get('rel', '')}]-> [{to_labels}] {row.get('to_node', '')}")
    return "\n".join(parts)

@tool
def query_knowledge_graph(query: str) -> str:
    """
    查询云产品知识图谱。
    当用户询问云产品的架构、包含关系、配置限制（例如：ecs.g8a.xlarge能挂载几块网卡？北京可用区有哪些实例？退款有什么限制？）时，使用此工具。
    输入参数 query 必须是明确的自然语言查询句子。
    """
    try:
        chain = _get_graph_chain()
        result = chain.invoke({"query": query})
        return result.get('result', "未找到相关图谱信息。")
    except Exception as e:
        fallback_result = _fallback_graph_keyword_search(query)
        if fallback_result and "失败" not in fallback_result:
            return fallback_result
        return f"查询图谱时发生错误: {str(e)}；关键词兜底结果：{fallback_result}"
