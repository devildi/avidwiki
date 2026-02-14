#!/bin/bash

# 一键启动前后端服务
# 使用方法: bash start.sh

echo "================================"
echo "启动 Avid KB 服务"
echo "================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_DIR="/Users/DevilDI/Desktop/projects/wiki"
cd "$PROJECT_DIR" || exit 1

# 检查后端进程
BACKEND_PID=$(lsof -ti:8000)
if [ ! -z "$BACKEND_PID" ]; then
    echo -e "${YELLOW}⚠ 后端已在运行 (PID: $BACKEND_PID)${NC}"
    echo "停止旧进程..."
    kill -9 "$BACKEND_PID" 2>/dev/null
    sleep 2
fi

# 检查前端进程
FRONTEND_PID=$(lsof -ti:3000)
if [ ! -z "$FRONTEND_PID" ]; then
    echo -e "${YELLOW}⚠ 前端已在运行 (PID: $FRONTEND_PID)${NC}"
    echo "停止旧进程..."
    kill -9 "$FRONTEND_PID" 2>/dev/null
    sleep 2
fi

echo -e "${GREEN}启动后端服务...${NC}"
# 启动后端（后台运行）
nohup python3 backend/api/main.py > backend_debug.log 2>&1 &
BACKEND_PID=$!

# 等待后端启动
echo "等待后端启动..."
sleep 5

# 检查后端是否成功启动
if ps -p $BACKEND_PID > /dev/null; then
    echo -e "${GREEN}✓ 后端启动成功 (PID: $BACKEND_PID)${NC}"
    echo -e "  后端地址: ${GREEN}http://localhost:8000${NC}"
else
    echo -e "${RED}✗ 后端启动失败${NC}"
    echo "查看日志: cat backend_debug.log"
    exit 1
fi

echo ""
echo -e "${GREEN}启动前端服务...${NC}"
# 启动前端（后台运行）
cd frontend
nohup npm run dev > ../frontend_debug.log 2>&1 &
FRONTEND_PID=$!
cd ..

# 等待前端启动
echo "等待前端启动..."
sleep 8

# 检查前端是否成功启动
if ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${GREEN}✓ 前端启动成功 (PID: $FRONTEND_PID)${NC}"
    echo -e "  前端地址: ${GREEN}http://localhost:3000${NC}"
else
    echo -e "${RED}✗ 前端启动失败${NC}"
    echo "查看日志: cat frontend_debug.log"
    exit 1
fi

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✓ 所有服务启动成功！${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "服务信息:"
echo "  - 后端: http://localhost:8000"
echo "  - 前端: http://localhost:3000"
echo "  - API 文档: http://localhost:8000/docs"
echo ""
echo "进程 ID:"
echo "  - 后端 PID: $BACKEND_PID"
echo "  - 前端 PID: $FRONTEND_PID"
echo ""
echo "日志文件:"
echo "  - 后端: backend_debug.log"
echo "  - 前端: frontend_debug.log"
echo ""
echo -e "${YELLOW}停止服务:${NC}"
echo "  kill $BACKEND_PID  # 停止后端"
echo "  kill $FRONTEND_PID # 停止前端"
echo "  或运行: bash stop.sh"
echo ""
echo -e "${GREEN}🚀 访问 http://localhost:3000 开始使用！${NC}"
echo ""
