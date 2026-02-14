# PDF 错误恢复和超时保护功能

## 问题背景
用户报告PDF处理总是卡在"⏳ Processed 24/273 pages"，然后连接中断。这说明某些页面包含复杂内容导致程序卡死。

## 问题原因分析

1. **复杂页面内容**：某些页面可能包含：
   - 大量高分辨率图片
   - 复杂的表格布局
   - 特殊字体或编码
   - 扫描文档（需要OCR）
   - 加密或损坏的页面

2. **向量化瓶颈**：
   - Embedding模型处理大文本时很慢
   - 某些chunks包含特殊字符导致异常
   - 批次太大导致单次处理时间过长

3. **缺少错误恢复**：
   - 单个页面出错导致整个处理失败
   - 没有超时机制，程序无限等待
   - 连接超时后任务中断，无法恢复

## 解决方案

### 1. 页面级超时保护 (pdf_extractor_large.py)

**超时提取**：
```python
def extract_with_timeout(page, timeout_seconds=8):
    """使用线程超时提取页面文本"""
    # 在单独线程中提取，8秒后超时
    thread = threading.Thread(target=extract)
    thread.daemon = True
    thread.start()
    thread.join(timeout=timeout_seconds)
```

**关键改进**：
- 每个页面提取最多8秒
- 超时后自动跳过该页面
- 记录跳过的页面列表

### 2. 页面级错误恢复 (pdf_extractor_large.py:112-120)

```python
except Exception as e:
    # 捕获单个页面的错误，继续处理其他页面
    logger.error(f"Error processing page {page_num}: {e}")
    skipped_pages.append(page_num)
    progress_callback and progress_callback(
        page_num, total_pages,
        f"⚠️ Skipped page {page_num} ({str(e)[:50]})"
    )
    continue  # 继续处理下一页
```

**关键改进**：
- 单个页面出错不影响整体处理
- 用户实时看到跳过的页面
- 最后提供完整的跳过页面报告

### 3. 批次级重试机制 (vector_store.py:199-235)

```python
# 向量化并存储（带重试机制）
batch_success = False
for attempt in range(max_retries + 1):
    try:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        batch_success = True
        break
    except Exception as batch_error:
        if attempt < max_retries:
            log(f"  🔄 Retrying in 2 seconds...")
            time.sleep(2)
        else:
            failed_batches.append((first_page, last_page, str(batch_error)))
```

**关键改进**：
- 每个批次最多重试2次
- 失败后等待2秒重试
- 记录失败的批次，不中断整体处理
- 提供详细的失败批次报告

### 4. 部分完成状态 (vector_store.py:255-259)

```python
status = 'completed' if not failed_batches else 'partial'
update_pdf_status(pdf_id, status,
                   total_pages=total_pages,
                   total_chunks=total_chunks)
```

**关键改进**：
- 新增'partial'状态表示部分完成
- 即使有页面失败，也能使用已索引的部分
- 用户清楚地知道索引状态

### 5. 前端状态显示 (PDFManager.tsx)

```typescript
status: 'pending' | 'processing' | 'completed' | 'failed' | 'partial';

case 'partial':
    return <AlertCircle className="text-orange-400" size={18} />;

<span className="text-orange-400">⚠️ Partially Indexed</span>
```

**关键改进**：
- 橙色警告图标表示部分完成
- 明确的状态文本提示
- 用户体验更清晰

## 功能对比

### 优化前：
- ❌ 单个页面卡住导致整个处理失败
- ❌ 无超时保护，可能无限等待
- ❌ 连接中断后无法恢复
- ❌ 用户不知道程序卡在哪里

### 优化后：
- ✅ 单个页面出错自动跳过，继续处理
- ✅ 8秒超时保护，不会无限等待
- ✅ 批次重试机制，提高成功率
- ✅ 实时显示跳过的页面和失败批次
- ✅ 部分完成状态，仍可使用已索引内容
- ✅ 详细的日志报告，便于调试

## 测试场景

### 场景1：页面包含大量图片
- **行为**：页面提取超时（>8秒）
- **结果**：跳过该页面，记录日志，继续处理
- **用户看到**：⚠️ Skipped page 24 (extraction timeout)

### 场景2：向量化批次失败
- **行为**：批次处理失败，自动重试
- **结果**：最多重试2次，失败后跳过该批次
- **用户看到**：⚠️ Batch 20-40 failed (attempt 1/3)...

### 场景3：网络连接中断
- **行为**：前端SSE连接断开
- **结果**：后端继续处理，前端刷新后看到最新状态
- **用户看到**：刷新页面后显示 'partial' 状态

### 场景4：部分页面失败
- **行为**：处理完成但有失败页面
- **结果**：标记为'partial'状态，显示详细报告
- **用户看到**：⚠️ Processing completed with 3 failed batches

## 日志示例

### 成功处理：
```
📄 Processing: large_document.pdf
  📊 File size: 45.67 MB
  📊 Total pages: 273
  🔄 Starting text extraction (streaming mode)...
  ⏳ Extracting text from page 5/273 (速度: 4.2页/秒, 剩余: 60秒)
  🔍 Vectorizing 20 chunks from pages 1-20...
  ✅ Vectorized 20 chunks (pages 1-20)
  ⏳ Processed 20/273 pages (速度: 4.2页/秒, 剩余: 60秒)
  ...
✅ PDF large_document.pdf indexing complete!
   📈 Total: 273 pages, 1450 chunks
```

### 有页面跳过：
```
📄 Processing: complex_document.pdf
  📊 Total pages: 273
  🔄 Starting text extraction (streaming mode)...
  🔍 Vectorizing 20 chunks from pages 20-40...
  ❌ Failed to vectorize batch 20-40 after 3 attempts
  ⚠️ Batch 20-40 failed: Input string too long...
  ...
⚠️ Processing completed with 2 failed batches:
   - Pages 20-40: Input string too long...
   - Pages 100-120: Connection timeout...
✅ PDF complex_document.pdf indexing complete!
   📈 Total: 273 pages, 1380 chunks
```

### 处理总结：
```
Extraction complete: 1380 chunks created
Skipped 3 pages: [24, 87, 156]
Slow pages detected (>3s): [(24, '7.2s'), (87, '5.8s')]
```

## 进一步优化建议

### 1. 跳过特定页面类型
```python
# 可选：配置跳过策略
SKIP_STRATEGIES = {
    'image_only': True,  # 跳过纯图片页面
    'very_slow': True,    # 跳过处理超过10秒的页面
    'low_text': True,    # 跳过文本少于10字符的页面
}
```

### 2. 使用更快的PDF库
```python
# pdfplumber 慢但准确
# PyPDF2 快但准确性低
# pdfminer.six 中等速度和准确性
# 可根据需求选择
```

### 3. GPU加速向量化
```python
# 使用CUDA加速的embedding模型
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2",
    device="cuda"  # 使用GPU
)
```

### 4. 增量索引
```python
# 支持从失败点恢复
# 避免重复处理已成功的页面
RESUME_FROM_PAGE = get_last_successful_page(pdf_id)
```

## 技术细节

### 为什么使用线程超时而不是signal.SIGALRM？
- **Windows不支持SIGALRM**
- **线程更轻量级**
- **守护线程会在主线程结束时自动退出**

### 为什么批次重试而不是跳过？
- **向量化失败可能是临时性的**（内存、网络）
- **重试2次可以成功**，避免不必要的跳过
- **重试间隔2秒**，给系统恢复时间

### 为什么有'partial'状态？
- **用户体验更好**：看到部分结果比完全失败好
- **实用价值**：大部分内容已可搜索
- **透明性**：明确告知有部分失败

## 监控和调试

### 查看详细日志：
```bash
# 后端日志
tail -f backend/logs/pdf_processing.log

# 查看特定页面处理情况
grep "Page 24" backend/logs/pdf_processing.log
```

### 性能指标：
- **正常页面提取**：< 1秒
- **慢页面提取**：3-8秒（会记录警告）
- **超时页面**：> 8秒（自动跳过）
- **向量化速度**：3-5页/秒（取决于文本量）

### 失败原因分类：
1. **提取失败**：页面格式复杂、加密
2. **向量化失败**：文本太长、特殊字符
3. **超时**：页面内容太多、I/O慢
4. **网络错误**：连接中断、超时

## 用户建议

### 如果处理频繁失败：
1. 检查PDF是否损坏（用PDF阅读器打开）
2. 尝试重新生成PDF（从源文件）
3. 考虑使用PDF修复工具
4. 分割大文档为小文档

### 如果处理速度慢：
1. 减小chunk_size（从1000到500）
2. 使用更快的embedding模型
3. 升级硬件（CPU/RAM）
4. 考虑使用GPU加速

### 如果需要所有页面：
1. 手动处理失败的页面（复制文本）
2. 使用其他PDF工具提取问题页面
3. 联系技术支持
