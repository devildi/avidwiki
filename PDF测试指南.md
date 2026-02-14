# PDF 大文档测试指南

## 📁 测试文件存放位置

### 方式 1: 通过 API 上传（推荐）

将你的 PDF 文件放在任意位置，然后通过 API 或前端上传：

```bash
# 启动后端
python3 backend/api/main.py

# 上传 PDF（文件会自动保存到 data/docs/uploads/）
curl -X POST http://localhost:8000/pdf/upload \
     -F "file=@/path/to/your/large_document.pdf"
```

### 方式 2: 直接测试（无需上传）

如果你只是想测试性能，可以直接使用测试脚本：

```bash
# 创建测试目录
mkdir -p test_pdfs

# 将你的大PDF文件复制到测试目录
cp /path/to/your/large_document.pdf test_pdfs/

# 运行性能测试
python3 test_large_pdf.py test_pdfs/large_document.pdf
```

---

## 🚀 完整测试流程

### 步骤 1: 准备测试文件

```bash
# 在项目根目录执行
mkdir -p test_pdfs
cp /path/to/your/1300page_document.pdf test_pdfs/
```

### 步骤 2: 运行性能测试

```bash
# 测试提取性能（不需要后端运行）
python3 test_large_pdf.py test_pdfs/1300page_document.pdf
```

**测试输出示例：**
```
============================================================
开始测试: 1300page_document.pdf
============================================================
初始内存使用: 45.23 MB

[步骤 1] 导入模块...
✓ 模块导入完成 (0.15s)

[步骤 2] 获取 PDF 基本信息...
✓ PDF 信息获取完成 (0.32s)
  - 文件名: 1300page_document.pdf
  - 文件大小: 125.67 MB
  - 总页数: 1342
  - 当前内存: 48.12 MB (增加 2.89 MB)

[步骤 3] 提取文本和分块...
✓ 文本提取完成 (23.45s)
  - 总 chunks 数: 3842
  - 总字符数: 3,842,156
  - 平均 chunk 大小: 1000 字符
  - 处理速度: 57.2 页/秒

[性能指标]
  - 处理速度: 57.2 页/秒
  - 预计 1300 页耗时: 22.7 秒
  - 每页平均: 0.017 秒

[步骤 4] 向量化测试（仅前 100 chunks）...
  测试 100 个 chunks...
✓ 向量化完成 (8.34s)
  - 速度: 12.0 chunks/秒
  - 预计全部 3842 chunks 耗时: 320.2 秒 (5.3 分钟)

[内存使用总结]
  - 初始: 45.23 MB
  - 峰值: 156.78 MB
  - 增长: 111.55 MB

============================================================
✓ 测试完成
============================================================
```

### 步骤 3: 完整流程测试（可选）

如果你想测试完整的上传+索引流程：

```bash
# 1. 启动后端
python3 backend/api/main.py

# 2. 在另一个终端上传 PDF
curl -X POST http://localhost:8000/pdf/upload \
     -F "file=@test_pdfs/1300page_document.pdf"

# 返回: {"pdf_id": 1, "filename": "1300page_document_20250214_172345.pdf", ...}

# 3. 触发索引
curl -X POST http://localhost:8000/pdf/1/index

# 4. 查看索引进度（可选）
curl http://localhost:8000/pdf/indexing/progress/1
```

---

## 📊 预期性能参考

| PDF 大小 | 页数 | 提取时间 | 向量化时间 | 总时间 | 内存峰值 |
|---------|------|---------|-----------|--------|---------|
| 10 MB   | 100  | 2-3 s   | 30-60 s   | 1 min  | 60 MB   |
| 50 MB   | 500  | 8-12 s  | 2-3 min   | 3 min  | 100 MB  |
| 125 MB  | 1300 | 20-30 s | 5-8 min   | 8 min  | 160 MB  |
| 500 MB  | 5000 | 90-120s| 20-30 min  | 30 min | 400 MB  |

*基于 Intel i5/i7 CPU 的估算值*

---

## ⚠️ 注意事项

### 1. 内存限制
如果你的机器内存 < 4GB，建议：
- 使用 `pdf_extractor_large.py` 的流式处理
- 减小批处理大小：`batch_size=50`

### 2. 磁盘空间
确保有足够空间：
- PDF 文件大小
- ChromaDB 向量存储（约为文本大小的 2-3 倍）
- 建议：至少预留 PDF 文件大小的 5 倍空间

### 3. 处理时间
对于 1300+ 页的文档：
- 文本提取：约 30 秒
- 向量化：约 5-10 分钟
- 请耐心等待，不要中断进程

---

## 🔧 故障排查

### 问题 1: "File too large" 错误
**解决**: 在 `backend/api/main.py` 中增加上传大小限制：
```python
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    # ...
)
# 增加到 1GB
from fastapi.middleware.cors import CORSMiddleware
# 在启动参数中添加: --limit-upload-size 1048576000
```

### 问题 2: 内存不足
**解决**: 使用流式处理版本
```python
# 在 backend/ingest/vector_store.py 中修改
from pdf_extractor_large import LargePDFExtractor

def ingest_pdf_chunks(pdf_id: int, log_callback=None):
    # ...
    extractor = LargePDFExtractor(pdf_record['file_path'])

    # 使用流式处理
    for batch in extractor.extract_text_stream(batch_size=50):
        collection.upsert(...)
```

### 问题 3: 向量化太慢
**解决**:
1. 使用 GPU（如果有）：
   ```python
   ef = embedding_functions.SentenceTransformerEmbeddingFunction(
       model_name="all-MiniLM-L6-v2",
       device="cuda"  # 添加这行
   )
   ```
2. 减小 chunk_size：从 1000 改为 500

---

## 📞 需要帮助？

如果遇到问题，请提供：
1. PDF 文件大小和页数
2. 错误信息完整日志
3. 系统配置（CPU、内存、磁盘空间）
