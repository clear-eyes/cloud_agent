import asyncio
import sys
import os

# 确保能正确导入 app 模块
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from infra.cache import semantic_cache

# 预设的 QA 列表 (包含退款规则、课程有效期等高频标准问题)
PRESET_QA = [
    {
        "query": "云服务器ECS的退款规则是什么？",
        "response": "### ☁️ 云服务器 ECS 退款规则\n\n- **包年包月实例**：支持五天无理由退款，超过五天按使用天数扣除费用后退还余额。\n- **按量付费实例**：不涉及退款，随时释放，释放后停止计费。\n- **退款路径**：登录控制台 -> 费用中心 -> 退订管理 -> 发起退订。\n\n> ⚠️ 注意：活动特价机器可能不支持五天无理由退款，请以具体活动规则为准。"
    },
    {
        "query": "退款要多久到账？",
        "response": "正常情况下，发起退订并审核通过后，退款将在 **1-3 个工作日** 内原路退回到您的支付账户（支付宝、微信或银行卡）。"
    },
    {
        "query": "你们的云计算架构师课程有效期是多久？",
        "response": "您好！我们的**《云计算高级架构师认证课程》**自购买激活之日起，有效期为 **365 天（一年）**。\n\n在有效期内，您可以无限次观看视频回放、参与线上实验，并获得一次免费的认证考试机会。如果需要延期，可在到期前 30 天内联系客服申请。"
    },
    {
        "query": "VPC 专有网络怎么计费？",
        "response": "VPC 专有网络本身是**免费**的。\n\n您在 VPC 内创建的交换机（VSwitch）、路由器等基础网络逻辑组件也不收费。但如果您使用了以下 VPC 相关资源，将会产生费用：\n1. **弹性公网 IP (EIP)**\n2. **NAT 网关**\n3. **云企业网 (CEN) 跨地域带宽**\n4. **VPN 网关**\n请根据实际业务需求合理规划。"
    }
]

async def preload_cache():
    print("🔄 开始预热 L1 语义缓存...")
    await semantic_cache.initialize()
    
    for item in PRESET_QA:
        query = item["query"]
        response = item["response"]
        print(f"注入缓存 -> Query: '{query}'")
        
        # 调用 set_cache 将问题向量化并写入 Milvus 语义缓存集合
        await semantic_cache.set_cache(query, response)
        
    print("✅ 缓存预热完成！")

if __name__ == "__main__":
    asyncio.run(preload_cache())
