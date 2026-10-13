-- ==========================================================
-- 云平台用户订单与账单模拟数据初始化脚本
-- ==========================================================

-- 1. 创建订单表 (如果不存在)
CREATE TABLE IF NOT EXISTS cloud_orders (
    order_id VARCHAR(50) PRIMARY KEY COMMENT '订单唯一ID',
    user_id VARCHAR(50) NOT NULL COMMENT '用户ID',
    product_name VARCHAR(100) NOT NULL COMMENT '产品名称 (如: ecs.g8a.xlarge)',
    billing_mode VARCHAR(20) NOT NULL COMMENT '计费模式 (包年包月, 按量付费)',
    amount DECIMAL(10, 2) NOT NULL COMMENT '订单金额',
    status VARCHAR(20) NOT NULL COMMENT '订单状态 (Paid, Unpaid, Refunded)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='云产品订单表';

-- 2. 清空旧数据 (方便重复测试)
TRUNCATE TABLE cloud_orders;

-- 3. 插入测试数据 (为两个不同的用户生成数据，用于验证权限隔离)

-- 用户 user_1001 的数据 (高净值客户，买了企业级实例)
INSERT INTO cloud_orders (order_id, user_id, product_name, billing_mode, amount, status, created_at) VALUES
('ORD-1001-001', 'user_1001', 'ecs.g8a.4xlarge', '包年包月', 12500.00, 'Paid', '2023-10-01 10:00:00'),
('ORD-1001-002', 'user_1001', 'rds.mysql.c1.large', '包年包月', 3600.00, 'Paid', '2023-10-05 14:30:00'),
('ORD-1001-003', 'user_1001', '共享带宽 100Mbps', '按量付费', 150.50, 'Paid', '2023-11-01 08:15:00');

-- 用户 user_1002 的数据 (个人开发者，买了便宜的实例)
INSERT INTO cloud_orders (order_id, user_id, product_name, billing_mode, amount, status, created_at) VALUES
('ORD-1002-001', 'user_1002', 'ecs.c7.large', '按量付费', 45.20, 'Paid', '2023-11-15 09:00:00'),
('ORD-1002-002', 'user_1002', '云盘 ESSD PL0 40G', '包年包月', 120.00, 'Paid', '2023-11-15 09:05:00'),
('ORD-1002-003', 'user_1002', 'ecs.c7.large', '按量付费', 12.80, 'Unpaid', '2023-11-16 10:00:00'); -- 模拟一笔未支付的账单

-- 4. 创建资源实例表 (模拟云平台控制台看到的真实机器)
CREATE TABLE IF NOT EXISTS cloud_instances (
    instance_id VARCHAR(50) PRIMARY KEY COMMENT '实例唯一ID',
    user_id VARCHAR(50) NOT NULL COMMENT '所属用户',
    order_id VARCHAR(50) NOT NULL COMMENT '关联的购买订单',
    instance_type VARCHAR(100) NOT NULL COMMENT '实例规格',
    region_id VARCHAR(50) NOT NULL COMMENT '所在地域',
    zone_id VARCHAR(50) NOT NULL COMMENT '所在可用区',
    status VARCHAR(20) NOT NULL COMMENT '实例运行状态 (Running, Stopped)',
    public_ip VARCHAR(20) COMMENT '公网 IP',
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='云资源实例表';

TRUNCATE TABLE cloud_instances;

INSERT INTO cloud_instances (instance_id, user_id, order_id, instance_type, region_id, zone_id, status, public_ip) VALUES
('i-bp1_user1001_ecs', 'user_1001', 'ORD-1001-001', 'ecs.g8a.4xlarge', 'cn-beijing', 'cn-beijing-k', 'Running', '47.100.1.1'),
('rm-bp1_user1001_rds', 'user_1001', 'ORD-1001-002', 'rds.mysql.c1.large', 'cn-beijing', 'cn-beijing-l', 'Running', NULL),
('i-bp1_user1002_ecs', 'user_1002', 'ORD-1002-001', 'ecs.c7.large', 'cn-hangzhou', 'cn-hangzhou-h', 'Stopped', '114.55.2.2');

CREATE TABLE IF NOT EXISTS instance_metrics_daily (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '自增主键',
    instance_id VARCHAR(50) NOT NULL COMMENT '实例ID',
    user_id VARCHAR(50) NOT NULL COMMENT '所属用户ID',
    metric_date DATE NOT NULL COMMENT '统计日期',
    avg_cpu_usage_percent DECIMAL(5,2) NOT NULL COMMENT '当日平均CPU利用率',
    avg_memory_usage_percent DECIMAL(5,2) NOT NULL COMMENT '当日平均内存利用率',
    max_network_out_mbps DECIMAL(8,2) NOT NULL COMMENT '当日出口带宽峰值(Mbps)',
    INDEX idx_instance_date (instance_id, metric_date),
    INDEX idx_user_instance (user_id, instance_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实例日级监控指标表';

TRUNCATE TABLE instance_metrics_daily;

INSERT INTO instance_metrics_daily (instance_id, user_id, metric_date, avg_cpu_usage_percent, avg_memory_usage_percent, max_network_out_mbps) VALUES
('i-bp1_user1001_ecs', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 6 DAY), 2.10, 18.50, 1.20),
('i-bp1_user1001_ecs', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 5 DAY), 2.50, 19.10, 1.60),
('i-bp1_user1001_ecs', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 4 DAY), 3.20, 20.40, 2.00),
('i-bp1_user1001_ecs', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 3 DAY), 1.90, 17.90, 1.00),
('i-bp1_user1001_ecs', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 2 DAY), 2.80, 18.20, 1.40),
('i-bp1_user1001_ecs', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 1 DAY), 2.40, 19.00, 1.30),
('i-bp1_user1001_ecs', 'user_1001', CURDATE(), 2.00, 18.70, 1.10),
('i-bp1_user1002_ecs', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 6 DAY), 36.50, 62.10, 42.00),
('i-bp1_user1002_ecs', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 5 DAY), 41.20, 65.00, 51.00),
('i-bp1_user1002_ecs', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 4 DAY), 38.40, 63.50, 48.00),
('i-bp1_user1002_ecs', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 3 DAY), 44.00, 67.30, 55.00),
('i-bp1_user1002_ecs', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 2 DAY), 39.10, 60.80, 47.00),
('i-bp1_user1002_ecs', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 1 DAY), 42.80, 64.20, 53.00),
('i-bp1_user1002_ecs', 'user_1002', CURDATE(), 40.30, 61.90, 49.00);
