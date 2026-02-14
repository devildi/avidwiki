#!/bin/bash

# 停止所有服务
# 使用方法: bash stop.sh

echo "================================"
echo "停止 Avid KB 服务"
echo "================================"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 停止后端
BACKEND_PID=$(lsof -ti:8000)
if [ ! -z "$BACKEND_PID" ]; then
    echo -e "${YELLOW}停止后端 (PID: $BACKEND_PID)...${NC}"
    kill -9 "$BACKEND_PID"
    echo -e "${GREEN}✓ 后端已停止${NC}"
else
    echo -e "${YELLOW}⚠ 后端未运行${NC}"
fi

# 停止前端
FRONTEND_PID=$(lsof -ti:3000)
if [ ! -z "$FRONTEND_PID" ]; then
    echo -e "${YELLOW}停止前端 (PID: $FRONTEND_PID)...${NC}"
    kill -9 "$FRONTEND_PID"
    echo -e "${GREEN}✓ 前端已停止${NC}"
else
    echo -e "${YELLOW}⚠ 前端未运行${NC}"
fi

echo ""
echo -e "${GREEN}✓ 所有服务已停止${NC}"
echo ""
