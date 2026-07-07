#!/bin/bash

# 一键初始化项目脚本
# 使用方法: bash init.sh

echo "========================================"
echo "🚀 开始初始化 Avid KB 项目..."
echo "========================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 检查 Python 版本
echo -e "${YELLOW}步骤 1: 检查系统环境...${NC}"
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "✓ 检测到 Python 3 (版本: $PYTHON_VERSION)"
else
    echo -e "${RED}✗ 未检测到 Python 3，请先安装 Python 3.9+${NC}"
    exit 1
fi

# 检查 Node.js
if command -v node &>/dev/null; then
    NODE_VERSION=$(node -v)
    echo "✓ 检测到 Node.js (版本: $NODE_VERSION)"
else
    echo -e "${RED}✗ 未检测到 Node.js，请先安装 Node.js 18+${NC}"
    exit 1
fi
echo ""

# 2. 初始化虚拟环境
echo -e "${YELLOW}步骤 2: 建立 Python 虚拟环境...${NC}"
if [ -d ".venv" ]; then
    echo "✓ .venv 虚拟环境已存在，跳过创建"
else
    # 优先使用高速的 uv，其次使用原生的 python3 -m venv
    if [ -f "/Users/DevilDI/.local/bin/uv" ]; then
        echo "检测到 uv 编译工具，正在使用 uv 创建虚拟环境..."
        /Users/DevilDI/.local/bin/uv venv --python 3.11
    else
        echo "正在使用原生 python3 创建虚拟环境..."
        python3 -m venv .venv
    fi
    echo -e "${GREEN}✓ 虚拟环境创建成功！${NC}"
fi
echo ""

# 3. 安装后端依赖
echo -e "${YELLOW}步骤 3: 安装后端 Python 依赖库...${NC}"
if [ -f "/Users/DevilDI/.local/bin/uv" ]; then
    /Users/DevilDI/.local/bin/uv pip install -r backend/requirements.txt
else
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r backend/requirements.txt
fi
echo -e "${GREEN}✓ 后端依赖安装完成！${NC}"
echo ""

# 4. 配置环境变量
echo -e "${YELLOW}步骤 4: 配置环境变量 (.env)...${NC}"
# 后端 env
if [ -f "backend/.env" ]; then
    echo "✓ backend/.env 已存在，跳过"
else
    cp backend/.env.example backend/.env
    echo -e "${GREEN}✓ 成功创建 backend/.env 配置文件${NC}"
fi

# 前端 env
if [ -f "frontend/.env.local" ]; then
    echo "✓ frontend/.env.local 已存在，跳过"
else
    cp frontend/.env.example frontend/.env.local
    echo -e "${GREEN}✓ 成功创建 frontend/.env.local 配置文件${NC}"
fi
echo ""

# 5. 初始化数据库
echo -e "${YELLOW}步骤 5: 初始化 SQLite 及 Vector 数据库...${NC}"
mkdir -p data/docs/uploads
mkdir -p data/chroma_db
# 运行数据库 schemas 构建
.venv/bin/python -c "
try:
    from backend.crawler.db_schema import init_db
    init_db()
    print('SQLite 数据库初始化成功')
except Exception as e:
    print('SQLite 数据库初始化跳过或失败:', e)
" 2>/dev/null

.venv/bin/python -c "
try:
    from backend.database.pdf_schema import init_pdf_tables
    init_pdf_tables()
    print('PDF 数据库表初始化成功')
except Exception as e:
    print('PDF 数据库表初始化跳过或失败:', e)
" 2>/dev/null
echo -e "${GREEN}✓ 数据库准备完毕！${NC}"
echo ""

# 6. 安装前端依赖
echo -e "${YELLOW}步骤 6: 安装前端 Node.js 依赖...${NC}"
cd frontend || exit 1
# 使用 nvm use (如果配置了 nvm 且有 .nvmrc)
if [ -f "$HOME/.nvm/nvm.sh" ]; then
    . "$HOME/.nvm/nvm.sh"
    nvm use 20 2>/dev/null || nvm use default 2>/dev/null
fi
npm install
cd ..
echo -e "${GREEN}✓ 前端依赖安装完成！${NC}"
echo ""

echo -e "${GREEN}========================================"
echo "🎉 项目初始化圆满完成！"
echo "========================================"
echo -e "${NC}"
echo "启动项目请运行以下命令："
echo -e "  🚀 ${GREEN}bash start.sh${NC}          (一键启动前后端服务)"
echo -e "  🛑 ${GREEN}bash stop.sh${NC}           (一键停止所有服务)"
echo ""
echo "也可以手动分窗启动："
echo -e "  - 后端: ${YELLOW}source .venv/bin/activate && python backend/api/main.py${NC}"
echo -e "  - 前端: ${YELLOW}cd frontend && npm run dev${NC}"
echo ""
