#!/bin/bash

# PDF 功能一键安装脚本
# 使用方法: bash setup_pdf.sh

echo "================================"
echo "PDF 功能安装脚本"
echo "================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_DIR="/Users/DevilDI/Desktop/projects/wiki"
cd "$PROJECT_DIR" || exit 1

echo -e "${YELLOW}步骤 1: 安装 Python 依赖${NC}"
echo "----------------------------------------"

# 尝试多个镜像源
MIRRORS=(
    "https://pypi.tuna.tsinghua.edu.cn/simple"
    "https://mirrors.aliyun.com/pypi/simple/"
    "https://pypi.douban.com/simple"
)

INSTALLED=false
for mirror in "${MIRRORS[@]}"; do
    echo "尝试镜像: $mirror"
    if pip3 install pdfplumber -i "$mirror" --quiet; then
        echo -e "${GREEN}✓ pdfplumber 安装成功！${NC}"
        INSTALLED=true
        break
    else
        echo -e "${RED}✗ 镜像失败，尝试下一个...${NC}"
    fi
done

if [ "$INSTALLED" = false ]; then
    echo -e "${RED}所有镜像失败，尝试直接安装...${NC}"
    if pip3 install pdfplumber; then
        echo -e "${GREEN}✓ pdfplumber 安装成功！${NC}"
        INSTALLED=true
    else
        echo -e "${RED}✗ pdfplumber 安装失败${NC}"
        echo "请手动安装: pip3 install pdfplumber"
        exit 1
    fi
fi

echo ""
echo -e "${YELLOW}步骤 2: 创建必要目录${NC}"
echo "----------------------------------------"
mkdir -p data/docs/uploads
mkdir -p data/chroma_db
echo -e "${GREEN}✓ 目录创建完成${NC}"

echo ""
echo -e "${YELLOW}步骤 3: 初始化数据库${NC}"
echo "----------------------------------------"
python3 -c "from backend.database.pdf_schema import init_pdf_tables; init_pdf_tables()" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 数据库初始化成功${NC}"
else
    echo -e "${YELLOW}⚠ 数据库初始化失败（可能在首次运行时自动初始化）${NC}"
fi

echo ""
echo -e "${YELLOW}步骤 4: 验证安装${NC}"
echo "----------------------------------------"
python3 -c "import pdfplumber; print(f'✓ pdfplumber 版本: {pdfplumber.__version__}')" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 依赖验证通过${NC}"
else
    echo -e "${RED}✗ pdfplumber 未正确安装${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✓ 安装完成！${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "下一步操作："
echo "1. 启动后端: cd backend/api && python3 main.py"
echo "2. 启动前端: cd frontend && npm run dev"
echo "3. 访问: http://localhost:3000/settings"
echo "   点击 'PDF Documents' 标签开始使用"
echo ""
echo -e "${YELLOW}提示: 如果遇到导入错误，请确保在项目根目录运行${NC}"
echo ""
