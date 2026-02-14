#!/bin/bash
echo "🔄 重启后端服务..."

# 停止所有运行的后端进程
pkill -f "python.*main.py" 2>/dev/null
sleep 2

# 确认进程已停止
if pgrep -f "python.*main.py" > /dev/null; then
    echo "⚠️  进程仍在运行，强制停止..."
    pkill -9 -f "python.*main.py"
    sleep 1
fi

echo "✅ 后端服务已停止"
echo "🚀 正在启动后端服务..."

cd backend/api
python main.py &
echo "✅ 后端服务已在新窗口启动"
