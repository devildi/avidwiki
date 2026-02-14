#!/bin/bash
# 一键清理磁盘空间
# 预计释放: ~6GB

echo "🧹 开始清理磁盘空间..."
echo ""

# 1. 清理conda缓存（最大收益 ~4.9GB）
echo "1️⃣ 清理 Conda 缓存..."
conda clean --all -y 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Conda 缓存清理完成"
else
    echo "   ⚠️ Conda 未安装或清理失败（跳过）"
fi
echo ""

# 2. 清理pip缓存（~890MB）
echo "2️⃣ 清理 pip 缓存..."
pip cache purge 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ pip 缓存清理完成"
else
    echo "   ⚠️ pip 缓存清理失败（跳过）"
fi
echo ""

# 3. 清理Homebrew缓存（~600MB）
echo "3️⃣ 清理 Homebrew 缓存..."
brew cleanup 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Homebrew 缓存清理完成"
else
    echo "   ⚠️ Homebrew 未安装或清理失败（跳过）"
fi
echo ""

# 4. 清理npm缓存（可选）
echo "4️⃣ 清理 npm 缓存..."
npm cache clean --force 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ npm 缓存清理完成"
else
    echo "   ⚠️ npm 缓存清理失败（跳过）"
fi
echo ""

# 5. 清理项目Python缓存（可选，很小）
echo "5️⃣ 清理 Python __pycache__..."
find /Users/DevilDI/Desktop/projects/wiki -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "   ✅ Python 缓存清理完成"
echo ""

# 显示清理后的空间
echo "📊 清理完成！磁盘使用情况："
df -h | grep -E "(/$|/System)" | head -3
echo ""

echo "✅ 全部清理完成！"
echo "💡 预计释放空间: ~5-6GB"
echo "📝 详细报告请查看: disk_usage_report.md"
