import json
from mcp_server import query_user_orders, query_user_instances

def test_db_tools():
    print("="*50)
    print("🚀 正在测试 MCP 数据库查询工具...")
    print("="*50)
    
    print("\n[测试 1] 模拟系统注入 user_1001 查询订单 (高净值客户)")
    result1 = query_user_orders(user_id="user_1001", limit=10)
    parsed_res1 = json.loads(result1)
    if parsed_res1.get("status") == "success":
        print(f"✅ 成功查询到 user_1001 的订单数: {len(parsed_res1['data'])}")
        print(json.dumps(parsed_res1['data'][:1], ensure_ascii=False, indent=2))
    else:
        print(f"❌ 查询失败: {parsed_res1.get('message')}")
        
    print("\n[测试 2] 模拟系统注入 user_1002 查询全部实例状态 (无需提供机器ID)")
    result2 = query_user_instances(user_id="user_1002")
    parsed_res2 = json.loads(result2)
    if parsed_res2.get("status") == "success":
        print(f"✅ 成功查询到 user_1002 的实例状态数: {len(parsed_res2['data'])}")
        print(json.dumps(parsed_res2['data'], ensure_ascii=False, indent=2))
    else:
        print(f"❌ 查询失败: {parsed_res2.get('message')}")

    print("\n[测试 3] 模拟防越权测试 (查询一个不存在的用户 user_9999)")
    result3 = query_user_instances(user_id="user_9999")
    parsed_res3 = json.loads(result3)
    print(f"✅ 防越权结果 (应返回空): {parsed_res3.get('message')}")

if __name__ == "__main__":
    test_db_tools()