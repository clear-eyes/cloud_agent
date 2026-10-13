import os
import pymysql
import json
import asyncio
import time
import requests
import sys
from decimal import Decimal
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# ==============================================================================
# 初始化环境配置
# ==============================================================================
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

# ==============================================================================
# 初始化 FastMCP 服务器
# 这个 Server 可以独立运行，支持 SSE 或 stdio 协议
# ==============================================================================
mcp = FastMCP("CloudPlatformMCPServer")

# ==============================================================================
# 数据库连接辅助函数
# ==============================================================================
def get_db_connection():
    """获取远程 MySQL 连接。在生产环境中应使用连接池。"""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "YOUR_MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "YOUR_MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "cloud_platform"),
        cursorclass=pymysql.cursors.DictCursor # 让查询结果以字典形式返回，方便转 JSON
    )

# ==============================================================================
# MCP 核心工具定义 (Tools)
# ==============================================================================

# 模拟的云产品目录数据库 (基于 mock_data 真实文档)
PRODUCT_CATALOG = {
    "P_ECS_G8A_XLARGE": {
        "name": "第八代企业级通用型实例 ecs.g8a.xlarge",
        "keywords": ["ecs", "云服务器", "通用型", "g8a", "4核16g", "amd", "genoa"],
        "price": 299.0,
    },
    "P_ECS_C7_8XLARGE": {
        "name": "第七代企业级计算型实例 ecs.c7.8xlarge",
        "keywords": ["ecs", "云服务器", "计算型", "c7", "32核64g", "高并发", "intel"],
        "price": 1299.0,
    },
    "P_GPU_GN7I": {
        "name": "GPU 计算型实例 ecs.gn7i-c8g1.2xlarge",
        "keywords": ["gpu", "算力", "大模型", "a10", "深度学习", "推理", "gn7i"],
        "price": 3500.0,
    },
    "P_RDS_MYSQL_HA": {
        "name": "云数据库 RDS MySQL 高可用版",
        "keywords": ["rds", "mysql", "数据库", "关系型", "高可用", "主备", "同城容灾"],
        "price": 599.0,
    },
    "P_ESSD_PL1": {
        "name": "ESSD PL1 性能云盘",
        "keywords": ["云盘", "块存储", "essd", "pl1", "存储"],
        "price": 50.0,
    }
}

@mcp.tool()
def get_promotable_products() -> str:
    """
    当用户说“我想推广商品”、“我想赚钱”、“有哪些商品可以推广”时调用。
    获取系统当前所有支持推广、返佣的产品列表。
    """
    promotable_list = []
    for pid, pinfo in PRODUCT_CATALOG.items():
        # 假设 P_ESSD_PL1 不支持单独推广，我们过滤掉它作为演示
        if pid != "P_ESSD_PL1":
            promotable_list.append({
                "product_id": pid,
                "product_name": pinfo["name"],
                "price": pinfo["price"]
            })
            
    return json.dumps({
        "status": "success",
        "message": "为您找到以下可推广的商品列表：",
        "data": promotable_list
    }, ensure_ascii=False)

@mcp.tool()
def search_product_catalog(keyword: str) -> str:
    """
    根据用户的自然语言描述（如“云服务器”、“2核4G”、“GPU”），模糊搜索并返回符合条件的产品信息及【产品ID】。
    
    Args:
        keyword: 用户描述的产品关键词。
    """
    results = []
    kw_lower = keyword.lower()
    
    for pid, pinfo in PRODUCT_CATALOG.items():
        # 简单的关键字匹配模拟
        if kw_lower in pinfo["name"].lower() or any(kw_lower in k for k in pinfo["keywords"]):
            results.append({
                "product_id": pid,
                "product_name": pinfo["name"],
                "price": pinfo["price"]
            })
            
    if not results:
        # 没匹配到具体型号，返回未找到，并提供通用推荐
        return json.dumps({
            "status": "not_found", 
            "message": f"未找到精确匹配 '{keyword}' 的产品。", 
            "recommendation": {"product_id": "P_ALL_000", "product_name": "全场通用云产品活动"}
        }, ensure_ascii=False)
        
    return json.dumps({"status": "success", "data": results}, ensure_ascii=False)

@mcp.tool()
def get_promotion_materials(product_id: str, user_id: str = "") -> str:
    """
    根据【产品ID】获取对应的专属推广链接和返佣活动信息。
    必须先调用 search_product_catalog 获得精确的 product_id 后再调用此工具。
    
    Args:
        product_id: 必须是标准的产品 ID，如 "P_ECS_G8A_XLARGE", "P_GPU_GN7I" 等。
        user_id: [系统注入] 当前用户的ID，用于生成专属的带参数返佣推广链接。
    """
    # 模拟从后台营销系统中获取的物料数据 (主键为 product_id)
    promotions = {
        "P_ECS_G8A_XLARGE": {
            "title": "ECS 第八代通用型 (g8a.xlarge) 开发者特惠",
            "desc": "基于 AMD EPYC 9004 处理器，4核16G。最高网络带宽10Gbps。首年立享 8.5 折优惠，企业上云核心精选！",
            "base_link": "https://promotion.cloud.com/ecs-g8a-special",
            "commission_rate": "15%"
        },
        "P_ECS_C7_8XLARGE": {
            "title": "ECS 第七代计算型 (c7.8xlarge) 大促",
            "desc": "32核64G，最高网络带宽40Gbps，支持1200万PPS！专为高并发 Web 应用打造，购买包年套餐即赠 ESSD PL1 云盘 100G！",
            "base_link": "https://promotion.cloud.com/ecs-c7-high-concurrency",
            "commission_rate": "18%"
        },
        "P_GPU_GN7I": {
            "title": "GPU 算力特惠 (gn7i-c8g1.2xlarge)",
            "desc": "搭载 1 块 NVIDIA A10 GPU (24GB显存)。专为深度学习推理、AIGC 生成设计。现在下单享首月半价，搭配 ESSD PL2 启动无压力！",
            "base_link": "https://promotion.cloud.com/gpu-a10-aigc",
            "commission_rate": "25%"
        },
        "P_RDS_MYSQL_HA": {
            "title": "RDS MySQL 高可用版 同城双活首选",
            "desc": "一主一备双节点架构，支持 30 秒内自动故障转移。保障 99.99% 可用性。开通即享免费读写分离代理！",
            "base_link": "https://promotion.cloud.com/rds-mysql-ha",
            "commission_rate": "12%"
        },
        "P_ALL_000": {
            "title": "云上全家桶 满减活动",
            "desc": "全场云产品（含 ECS、RDS、云盘）满 1000 减 100，买得多省得多。",
            "base_link": "https://promotion.cloud.com/all-in-one",
            "commission_rate": "10%"
        }
    }
    
    promo = promotions.get(product_id, promotions["P_ALL_000"])
    
    # 核心逻辑：使用注入的 user_id 生成专属裂变链接
    exclusive_link = f"{promo['base_link']}?inviter={user_id}&pid={product_id}" if user_id else promo['base_link']
    
    result = {
        "status": "success",
        "data": {
            "product_id": product_id,
            "activity_title": promo["title"],
            "selling_points": promo["desc"],
            "exclusive_link": exclusive_link,
            "commission_rate": promo["commission_rate"]
        }
    }
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
def generate_ai_poster(prompt: str) -> str:
    """
    调用千问文生图模型 qwen-image-2.0，根据提示词生成竖版推广海报。
    
    Args:
        prompt: 详细的生图提示词（如：赛博朋克风格的服务器机房，炫酷的蓝色霓虹灯，科技感，竖屏海报风格）。
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return json.dumps({"status": "error", "message": "未配置 DASHSCOPE_API_KEY"}, ensure_ascii=False)

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "qwen-image-2.0",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ]
        },
        "parameters": {
            "negative_prompt": "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，文字模糊，构图混乱",
            "prompt_extend": True,
            "watermark": False,
            "size": "1536*2688"
        }
    }

    last_error = "生成失败"
    for attempt in range(1, 3):
        try:
            sys.stderr.write(f"[AI-POSTER][QWEN] attempt={attempt} submit start\n")
            res = requests.post(url, json=payload, headers=headers, timeout=120)
            data = res.json()
            request_id = data.get("request_id", "")
            sys.stderr.write(f"[AI-POSTER][QWEN] attempt={attempt} status={res.status_code} request_id={request_id}\n")

            image_url = (
                data.get("output", {})
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", [{}])[0]
                .get("image")
            )
            if res.status_code == 200 and image_url:
                sys.stderr.write(f"[AI-POSTER][QWEN] attempt={attempt} success\n")
                return json.dumps({
                    "status": "success",
                    "data": {
                        "poster_url": image_url,
                        "message": "海报生成成功（Qwen-Image）",
                        "request_id": request_id
                    }
                }, ensure_ascii=False)

            last_error = data.get("message") or data.get("code") or f"HTTP {res.status_code}"
            sys.stderr.write(f"[AI-POSTER][QWEN] attempt={attempt} failed: {last_error}\n")
        except Exception as e:
            last_error = str(e)
            sys.stderr.write(f"[AI-POSTER][QWEN] attempt={attempt} exception: {last_error}\n")

    return json.dumps({"status": "error", "message": f"Qwen-Image 生成失败: {last_error}"}, ensure_ascii=False)

@mcp.tool()
def query_user_orders(user_id: str, limit: int = 5) -> str:
    """
    查询用户的云服务器订单和账单记录。
    
    Args:
        user_id: [系统注入] 用户的唯一标识符，不允许模型伪造。
        limit: [模型生成] 返回的最大记录数，默认为 5。
    """
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                SELECT order_id, product_name, billing_mode, amount, status, DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at
                FROM cloud_orders 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            """
            cursor.execute(sql, (user_id, limit))
            results = cursor.fetchall()
            
            if not results:
                return json.dumps({"status": "success", "message": "该用户目前没有任何订单记录。"}, ensure_ascii=False)
                
            for row in results:
                if 'amount' in row and row['amount'] is not None:
                    row['amount'] = float(row['amount'])
                    
            return json.dumps({"status": "success", "data": results}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"查询数据库失败: {str(e)}"}, ensure_ascii=False)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()

@mcp.tool()
def query_user_instances(user_id: str, limit: int = 5) -> str:
    """
    查询指定用户的服务器实例状态，返回实例ID、规格、公网IP、运行状态等信息。
    必须传入系统注入的 user_id。
    """
    sql = """
        SELECT instance_id, instance_type, region_id, zone_id, public_ip, status
        FROM cloud_instances
        WHERE user_id = %s
        ORDER BY instance_id DESC
        LIMIT %s
    """
    
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(sql, (user_id, limit))
            result = cursor.fetchall()
            
            if not result:
                return json.dumps({"status": "success", "message": f"未查询到您的服务器实例数据。"}, ensure_ascii=False)
            
            return json.dumps({"status": "success", "data": result}, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"status": "error", "message": f"查询数据库失败: {str(e)}"}, ensure_ascii=False)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()

@mcp.tool()
def analyze_instance_usage(instance_id: str, user_id: str = "") -> str:
    """
    根据实例ID，获取该实例过去 7 天的平均 CPU 利用率、内存利用率和峰值带宽。
    常用于架构诊断或成本优化 (FinOps) 场景，帮助判断资源是否闲置。
    
    Args:
        instance_id: 服务器实例的唯一ID，如 "i-bp1abcdefg"。必须先通过 query_user_instances 查出。
        user_id: [系统注入] 当前用户的ID，用于安全鉴权，防止越权查询他人监控数据。
    """
    if not instance_id:
        return json.dumps({"status": "error", "message": "必须提供实例 ID (instance_id)"}, ensure_ascii=False)
    
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            auth_sql = """
                SELECT instance_id
                FROM cloud_instances
                WHERE instance_id = %s AND user_id = %s
                LIMIT 1
            """
            cursor.execute(auth_sql, (instance_id, user_id))
            owned_instance = cursor.fetchone()
            if not owned_instance:
                return json.dumps({"status": "error", "message": "未找到该实例，或您无权查看该实例监控数据。"}, ensure_ascii=False)

            metrics_sql = """
                SELECT
                    ROUND(AVG(avg_cpu_usage_percent), 2) AS cpu_usage_percent,
                    ROUND(AVG(avg_memory_usage_percent), 2) AS memory_usage_percent,
                    ROUND(MAX(max_network_out_mbps), 2) AS network_out_bandwidth_mbps,
                    COUNT(*) AS days_count
                FROM instance_metrics_daily
                WHERE instance_id = %s
                  AND user_id = %s
                  AND metric_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            """
            cursor.execute(metrics_sql, (instance_id, user_id))
            agg = cursor.fetchone()

            if not agg or not agg.get("days_count"):
                return json.dumps({"status": "error", "message": "未查询到该实例近7天监控数据，请稍后再试。"}, ensure_ascii=False)

            cpu = float(agg["cpu_usage_percent"] or 0)
            memory = float(agg["memory_usage_percent"] or 0)
            bandwidth = float(agg["network_out_bandwidth_mbps"] or 0)

            if cpu < 10 and memory < 30:
                diagnosis = "RESOURCES_IDLE"
            elif cpu > 70 or memory > 80:
                diagnosis = "RESOURCES_TIGHT"
            else:
                diagnosis = "RESOURCES_NORMAL"

            result = {
                "instance_id": instance_id,
                "owner_id": user_id,
                "metrics_7d_avg": {
                    "cpu_usage_percent": cpu,
                    "memory_usage_percent": memory,
                    "network_out_bandwidth_mbps": bandwidth
                },
                "diagnosis": diagnosis
            }
            return json.dumps({"status": "success", "data": result}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"查询监控数据失败: {str(e)}"}, ensure_ascii=False)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()

@mcp.tool()
def get_promotion_materials(product_name: str, user_id: str = "") -> str:
    """
    根据产品名称获取对应的推广海报、专属推广链接和返佣活动信息。
    当用户说“我想要分享这款产品”、“有没有GPU相关的活动”时调用。
    
    Args:
        product_name: 需要推广或查询的产品名称，如 "ECS", "GPU", "RDS"。
        user_id: [系统注入] 当前用户的ID，用于生成专属的带参数返佣推广链接。
    """
    # 模拟从后台营销系统中获取的物料数据
    promotions = {
        "ecs": {
            "title": "云服务器 ECS 新人特惠分享",
            "desc": "标准型 2核4G 实例，首年仅需 99 元！企业上云首选，超高性价比。",
            "base_link": "https://promotion.cloud.com/ecs-new-user",
            "poster": "https://img.cloud.com/posters/ecs_2c4g_99.png",
            "commission_rate": "15%"
        },
        "gpu": {
            "title": "GPU 算力黑马特惠季",
            "desc": "A10/V100/A800 多款 GPU 实例按需释放，大模型训练/推理最佳搭档，首单立减 500 元！",
            "base_link": "https://promotion.cloud.com/gpu-ai-special",
            "poster": "https://img.cloud.com/posters/gpu_ai_500.png",
            "commission_rate": "20%"
        },
        "default": {
            "title": "云上全家桶 满减活动",
            "desc": "全场云产品满 1000 减 100，买得多省得多。",
            "base_link": "https://promotion.cloud.com/all-in-one",
            "poster": "https://img.cloud.com/posters/all_in_one.png",
            "commission_rate": "10%"
        }
    }
    
    product_lower = product_name.lower()
    key = "default"
    if "ecs" in product_lower or "服务器" in product_lower:
        key = "ecs"
    elif "gpu" in product_lower or "算力" in product_lower or "大模型" in product_lower:
        key = "gpu"
        
    promo = promotions[key]
    
    # 核心逻辑：使用注入的 user_id 生成专属裂变链接
    exclusive_link = f"{promo['base_link']}?inviter={user_id}" if user_id else promo['base_link']
    
    result = {
        "status": "success",
        "data": {
            "activity_title": promo["title"],
            "selling_points": promo["desc"],
            "exclusive_link": exclusive_link,
            "poster_url": promo["poster"],
            "commission_rate": promo["commission_rate"]
        }
    }
    return json.dumps(result, ensure_ascii=False)

# ==============================================================================
# 服务启动入口
# ==============================================================================
if __name__ == "__main__":
    import sys
    sys.stderr.write("🚀 正在启动 Cloud Platform MCP Server (stdio 模式)...\n")
    # FastMCP 默认通过标准输入/输出(stdio)与大模型 Agent 通信
    mcp.run()
