# PDF 功能 MVP 安装说明

## 📦 安装 Python 依赖

```bash
# 进入项目根目录
cd /Users/DevilDI/Desktop/projects/wiki

# 安装 PDF 处理所需的依赖
pip install pdfplumber==0.10.3
```

## 🔧 修复导入路径

由于项目结构的原因，需要确保 Python 可以正确导入模块。

### 1. 创建 `backend/__init__.py`

```bash
touch backend/__init__.py
touch backend/database/__init__.py
```

### 2. 修改 `backend/api/main.py` 的导入

将这行：
```python
from backend.database.pdf_schema import init_pdf_tables
```

改为：
```python
import sys
sys.path.append(os.path.join(os.getcwd(), 'backend', 'database'))
from pdf_schema import init_pdf_tables

# 同样修改其他 backend.* 的导入
```

## 🚀 启动服务

### 1. 启动后端

```bash
cd /Users/DevilDI/Desktop/projects/wiki
python3 backend/api/main.py
```

### 2. 启动前端

```bash
cd /Users/DevilDI/Desktop/projects/wiki/frontend
npm run dev
```

## 📄 使用 PDF 功能

1. 打开浏览器访问 `http://localhost:3000/settings`
2. 点击 "PDF Documents" 标签
3. 拖拽或点击上传 PDF 文件
4. 点击 "Index" 按钮开始向量化
5. 等待索引完成后，可以在搜索页面搜索 PDF 内容

## 🎯 功能特性

- ✅ PDF 文件上传
- ✅ 自动文本提取（pdfplumber）
- ✅ 智能分块（1000 字符/块，200 字符重叠）
- ✅ 向量化存储（ChromaDB）
- ✅ 实时索引进度（SSE）
- ✅ 搜索结果显示 PDF 来源和页码
- ✅ 删除 PDF（同时删除文件、数据库、向量）

## 📊 数据库结构

新的 PDF 表会自动创建在 `backend/crawler/forums.db`：

- `pdf_documents`: PDF 元数据
- `pdf_indexing_progress`: 索引进度（预留）

## ⚠️ 已知限制

- 仅支持文字版 PDF（不支持扫描版）
- 固定分块大小（1000 字符）
- 无 OCR 功能
- 无表格识别

## 🔍 故障排查

### 1. 导入错误

如果看到 `ModuleNotFoundError: No module named 'backend'`：

```bash
# 方法1：设置 PYTHONPATH
export PYTHONPATH=/Users/DevilDI/Desktop/projects/wiki:$PYTHONPATH

# 方法2：使用 -m 参数运行
cd /Users/DevilDI/Desktop/projects/wiki
python3 -m backend.api.main
```

### 2. pdfplumber 未安装

```bash
pip3 install pdfplumber
```

### 3. 权限问题

确保 `data/docs/` 目录可写：

```bash
chmod -R 755 data/
```

## 📝 下一步优化建议

1. 支持扫描版 PDF（OCR）
2. 使用 langchain 智能分块
3. 添加章节识别
4. 批量上传
5. PDF 预览功能
