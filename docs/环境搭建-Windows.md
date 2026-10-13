# CloudAgent Windows 环境搭建与启动

本文是 `环境搭建.docx` 的 Windows PowerShell 版本。以下命令均在 **PowerShell** 中执行，不要在 CMD 中执行。

## 0. 目录约定

本文把包含 `agent`、`app`、`cloudagent`、`front` 和 `mock_data` 的目录称为“项目根目录”。先进入项目根目录：

```powershell
Set-Location "E:\JavaCourse\LangChain\agent_projects\项目源码\cloud_agent"
```

如果项目被移动，请把上面的路径替换为新的实际路径。路径中包含中文时务必保留双引号。

## 1. 安装并检查基础软件

需要：

- Windows 10/11 64 位，启用硬件虚拟化；
- Docker Desktop，使用 WSL 2 后端并切换到 **Linux containers**；
- Miniconda 或 Anaconda；
- Node.js `20.19+` 或 `22.12+`（由前端 `package.json` 要求）。

首次安装 WSL 2 时，以管理员身份打开 PowerShell：

```powershell
wsl --install
wsl --update
```

安装并启动 Docker Desktop 后，在普通 PowerShell 检查：

```powershell
docker --version
docker compose version
docker info
conda --version
node --version
npm --version
```

`docker info` 必须能显示 Server 信息；如果报连接错误，先启动 Docker Desktop。

### Docker 镜像源（可选）

Windows 的 Docker Desktop 不使用 `/etc/docker/daemon.json`，所以原文中的 `sudo tee` 命令不能在 PowerShell 中执行。进入 Docker Desktop 的 **Settings → Docker Engine**，在现有 JSON 中加入可信镜像地址，然后点击 **Apply & restart**：

```json
{
  "registry-mirrors": [
    "https://<你的可信镜像加速地址>"
  ]
}
```

镜像加速地址可能失效，也会接触你拉取的镜像名称，不建议照搬来源不明的公共镜像列表。网络能正常拉取时可跳过本节。

## 2. 使用 Docker Compose 部署基础服务

本项目实际使用 Redis、MySQL、Milvus 和 Neo4j。当前 Windows 已安装本地 MySQL，因此 Compose 默认不再启动 MySQL；MySQL Docker 服务保留为可选 profile。原文中的 PostgreSQL 没有被源码引用，也设为可选服务。

### 2.1 创建本机容器配置

```powershell
Set-Location .\cloudagent
Copy-Item .\.env.docker.example .\.env.docker
notepad .\.env.docker
```

正式部署时请修改 `.env.docker` 中的容器密码，并确保后面的 `agent\.env` 使用相同的 Redis 和 Neo4j 密码。MySQL 密码以 Windows 本地 MySQL 中实际创建的用户密码为准；只有启用 `mysql-docker` profile 时才使用 `.env.docker` 的 MySQL 配置。

检查 Compose 文件：

```powershell
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml config
```

### 2.2 启动服务

```powershell
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml up -d
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml ps
```

默认命令会启动 Redis、Milvus、MinIO、etcd、Attu 和 Neo4j，不会占用本机 MySQL 的 `3306` 端口。如果以后决定改用 Docker MySQL，先停止 Windows 本地 MySQL，再执行：

```powershell
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml --profile mysql-docker up -d mysql
```

如确实还需要原文中的 PostgreSQL，再执行：

```powershell
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml --profile postgres up -d
```

本配置使用 Docker 命名卷，不需要执行 Linux 的 `mkdir -p`，也可避免 Windows 目录权限和路径转换问题。

服务地址：

| 服务 | Windows 主机地址 |
| --- | --- |
| Redis | `127.0.0.1:6379` |
| MySQL（当前使用 Windows 本地服务） | `127.0.0.1:3306` |
| PostgreSQL（可选） | `127.0.0.1:5432` |
| Milvus gRPC | `127.0.0.1:19530` |
| Milvus 健康检查 | `http://127.0.0.1:9091/healthz` |
| Attu | `http://127.0.0.1:8000` |
| MinIO 控制台 | `http://127.0.0.1:19001`（本机 9001 被 Windows 保留） |
| Neo4j Browser | `http://127.0.0.1:7474` |
| Neo4j Bolt | `bolt://127.0.0.1:7687` |

查看日志：

```powershell
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml logs -f
```

按 `Ctrl+C` 只退出日志查看，不会停止容器。

## 3. 初始化 Windows 本地 MySQL 测试数据

返回项目根目录，连接本机 MySQL。系统已安装的客户端位于 `D:\MySQL\MySQL Server 8.0\bin\mysql.exe`；如果 `mysql` 命令不在 PATH，可直接使用这个完整路径。

```powershell
Set-Location ..
mysql -u root -p
```

输入本机 MySQL root 密码后，在 MySQL 提示符中创建项目数据库和专用用户。请把示例密码改成自己的密码：

```sql
CREATE DATABASE IF NOT EXISTS mydb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'cloudagent'@'localhost' IDENTIFIED BY 'MySQLPass123';
CREATE USER IF NOT EXISTS 'cloudagent'@'127.0.0.1' IDENTIFIED BY 'MySQLPass123';
GRANT ALL PRIVILEGES ON mydb.* TO 'cloudagent'@'localhost';
GRANT ALL PRIVILEGES ON mydb.* TO 'cloudagent'@'127.0.0.1';
FLUSH PRIVILEGES;
EXIT;
```

在 PowerShell 中导入测试数据。这里通过 `cmd /c` 使用输入重定向，避免 Windows PowerShell 5.1 改变 SQL 文件的 UTF-8 编码：

```powershell
cmd /c 'mysql --default-character-set=utf8mb4 -u cloudagent -p mydb < "agent\database\init_mock_data.sql"'
```

验证表是否创建成功：

```powershell
mysql -u cloudagent -p -D mydb -e "SHOW TABLES;"
```

如果使用完整客户端路径，对应命令为：

```powershell
& "D:\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
cmd /c '"D:\MySQL\MySQL Server 8.0\bin\mysql.exe" --default-character-set=utf8mb4 -u cloudagent -p mydb < "agent\database\init_mock_data.sql"'
```

如果之前失败的 Compose 启动留下了一个未运行的 MySQL 容器，可安全删除该空容器；这不会删除 Windows 本地 MySQL：

```powershell
Set-Location .\cloudagent
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml --profile mysql-docker rm -sf mysql
Set-Location ..
```

## 4. 创建 Python 环境并安装依赖

项目原文要求 Python 3.10 及以上。建议使用与项目已有缓存一致的 Python 3.10 或 3.11：

```powershell
conda create --name multi_agent python=3.11 -y
conda activate multi_agent
python --version
python -m pip install --upgrade pip
python -m pip install -r .\agent\requirements-windows.txt
```

这里使用 `python -m pip`，可避免 Windows 上 `pip` 指向其他 Python 环境。

快速检查关键依赖：

```powershell
python -c "import fastapi, uvicorn, pymysql, redis, pymilvus, neo4j; print('Python dependencies OK')"
```

## 5. 配置 `agent\.env`

项目中已经有 `agent\.env` 时直接编辑，不要覆盖已有 API Key：

```powershell
notepad .\agent\.env
```

至少应包含以下内容。密码要与 `cloudagent\.env.docker` 保持一致：

```dotenv
DASHSCOPE_API_KEY=替换为真实的API_Key
MODEL=qwen-plus
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

REDIS_URL=redis://:RedisPass123@127.0.0.1:6379
REDIS_TTL=1800

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=cloudagent
MYSQL_PASSWORD=MySQLPass123
MYSQL_DATABASE=mydb

MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530

NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=Neo4jPass123
NEO4J_DATABASE=neo4j

LOG_LEVEL=INFO
```

这里连接的是 Windows 本地 MySQL。`MYSQL_PASSWORD` 必须填写第 3 节创建 `cloudagent` 用户时使用的实际密码。应用使用普通用户，不应使用 MySQL root 账户。

## 6. 初始化 Milvus 与 Neo4j 知识库

先确认容器处于运行或健康状态：

```powershell
Set-Location .\cloudagent
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml ps
Set-Location ..
```

Neo4j 导入脚本默认导入 `mock_data\ecs_product_info.md`：

```powershell
python .\agent\test\build_kg.py
```

也可以指定其他 Markdown 文件：

```powershell
python .\agent\test\build_kg.py .\mock_data\ecs_network_security.md
```

Milvus 第一次使用时，通过 `--ingest` 切分 `mock_data` 中的 Markdown、计算 Embedding 并覆盖写入集合：

```powershell
python .\agent\test\milvus_rag.py --ingest
```

以后只查询已有数据时不要加 `--ingest`，避免重复调用 Embedding API：

```powershell
python .\agent\test\milvus_rag.py --question "五天无理由退款有什么限制条件吗？"
```

这两个初始化脚本都会调用大模型/Embedding API，需要有效的 `DASHSCOPE_API_KEY` 和可用网络，并可能产生 API 费用。

## 7. 启动后端 API

新开一个 PowerShell，激活同一 Conda 环境，然后从 `app` 目录启动：

```powershell
Set-Location "E:\JavaCourse\LangChain\agent_projects\项目源码\cloud_agent\app"
conda activate multi_agent
python -m uvicorn app_main:app --host 0.0.0.0 --port 5000 --reload
```

打开 `http://127.0.0.1:5000/docs`。如果能看到 FastAPI Swagger 页面，说明后端已启动。

## 8. 启动前端

再新开一个 PowerShell：

```powershell
Set-Location "E:\JavaCourse\LangChain\agent_projects\项目源码\cloud_agent\front\cloud_agent"
npm install
npm run dev
```

根据终端提示打开地址，通常是 `http://127.0.0.1:5173`。前端源码已固定请求 `http://127.0.0.1:5000/api/chat`，因此后端端口应保持为 `5000`。

## 9. 日常启停命令

在项目根目录执行：

```powershell
Set-Location .\cloudagent

# 启动或恢复全部必需基础服务
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml up -d

# 重启
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml restart

# 查看状态
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml ps

# 停止并删除容器和网络，但保留数据库命名卷
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml down
```

只有确定要清空 Redis、MySQL、Milvus、Neo4j 等全部数据时，才使用下面的命令：

```powershell
docker compose --env-file .\.env.docker -f .\docker-compose.windows.yml down --volumes
```

## 10. 常见问题

### `docker info` 无法连接

启动 Docker Desktop，确认使用 Linux containers 和 WSL 2 后端，然后重新打开 PowerShell。

### 端口被占用

```powershell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -In 3306,6379,7474,7687,8000,9000,19001,9091,19530,5000,5173
```

停止占用端口的旧服务，或修改 `docker-compose.windows.yml` 左侧的主机端口。若修改 Redis、MySQL、Milvus 或 Neo4j 端口，也要同步修改 `agent\.env`。

### Docker Desktop 内存不足

Milvus、MySQL、Neo4j 同时运行占用较多资源。建议 Docker/WSL 至少可使用 8 GB 内存；资源不足时 Attu 和可选 PostgreSQL 可以不启动。

### 密码修改后仍无法登录

数据库初始化后，环境变量不会重置命名卷里的旧密码。开发环境中如确认数据可以删除，执行 `down --volumes` 后再重新 `up -d`；有重要数据时不要删除卷，应在数据库内部修改密码。
