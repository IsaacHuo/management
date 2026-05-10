# 图书馆管理系统

一个适合课程设计演示的图书馆管理系统，包含 FastAPI 后端、SQLite 数据库、原生 HTML/CSS/JS 管理后台、数据库初始化脚本和本机/服务器部署脚本。项目依赖和运行统一使用 `uv` 管理。

## 功能

- 单管理员登录，默认账号：`admin / Admin@123456`
- 仪表盘统计：图书种类、可借册数、有效读者、借出记录、逾期记录
- 图书管理：新增、编辑、查询、软删除、库存维护
- 读者管理：新增、编辑、查询、软删除、状态维护
- 借阅归还：登记借书、库存扣减、归还入库
- 逾期管理：按到期日自动识别逾期未还记录

> 首次部署后请修改默认管理员密码或重新生成管理员密码哈希后更新数据库。

## 项目结构

```text
.
├── app/
│   ├── main.py          # FastAPI 路由和业务逻辑
│   ├── database.py      # SQLite 连接和初始化工具
│   ├── security.py      # 密码哈希和会话 token
│   └── static/          # 原生 HTML/CSS/JS 管理后台
├── db/
│   ├── schema.sql       # 建表、索引、约束
│   └── seed.sql         # 管理员和演示数据
├── scripts/
│   ├── init_db.py       # 初始化 SQLite 数据库
│   ├── deploy.sh        # uv 同步依赖、初始化并启动服务
│   └── smoke_test.sh    # 本地启动后的最小冒烟测试
└── tests/
    └── test_api.py      # API 自动化测试
```

## 本地运行

```bash
cd /Users/isaachuo/软件工程课设/code
uv sync
uv run python scripts/init_db.py --reset
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000`，使用 `admin / Admin@123456` 登录。

## 部署

```bash
cd /Users/isaachuo/软件工程课设/code
chmod +x scripts/deploy.sh
HOST=0.0.0.0 PORT=8000 ./scripts/deploy.sh
```

部署脚本会：

- 使用 `uv sync --frozen --no-dev` 创建或复用 `.venv`
- 初始化 `data/library.db`
- 启动 Uvicorn

默认数据库路径是 `data/library.db`。如需指定路径：

```bash
LIBRARY_DB_PATH=/opt/library/library.db ./scripts/deploy.sh
```

## 数据库脚本

重建数据库并写入演示数据：

```bash
uv run python scripts/init_db.py --reset
```

只建表，不写入演示数据：

```bash
uv run python scripts/init_db.py --reset --no-seed
```

## 测试

```bash
uv run pytest
./scripts/smoke_test.sh
```

API 测试覆盖登录、仪表盘、图书 CRUD、读者 CRUD、借书、库存不足拒绝、归还和逾期查询。

## 主要 API

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/dashboard/stats`
- `GET /api/books`
- `POST /api/books`
- `PUT /api/books/{id}`
- `DELETE /api/books/{id}`
- `GET /api/readers`
- `POST /api/readers`
- `PUT /api/readers/{id}`
- `DELETE /api/readers/{id}`
- `GET /api/loans`
- `POST /api/loans`
- `POST /api/loans/{id}/return`
- `GET /api/loans/overdue`
