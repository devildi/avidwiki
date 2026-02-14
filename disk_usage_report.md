# 硬盘空间占用分析报告

生成时间: 2026-02-14 22:37

## 🚨 问题诊断

**结论**: 项目本身**没有**在"疯狂占据硬盘空间"。项目目录总计约 **676MB**，属于正常范围。

## 📊 完整空间占用分布

### 1. **项目目录** - 676MB（正常）

| 目录/文件 | 大小 | 说明 | 是否问题 |
|-----------|------|------|----------|
| `frontend/node_modules/` | 476MB | npm依赖包 | ✅ 正常 |
| `frontend/.next/` | 149MB | Next.js构建缓存 | ✅ 正常 |
| `test_pdfs/` | 30MB | 测试PDF文件 | ✅ 正常 |
| `data/chroma_db/` | 13MB | 向量数据库（515个向量） | ✅ 正常 |
| `.venv/` | 70MB | Python虚拟环境 | ✅ 正常 |
| `backend/` | 1.7MB | 后端代码和缓存 | ✅ 正常 |
| 日志文件 | <1MB | 各种日志文件 | ✅ 正常 |

**项目目录总大小**: ~676MB

### 2. **Conda环境** - 6.8GB（主要占用源）⚠️

| 目录 | 大小 | 说明 | 建议 |
|------|------|------|------|
| `~/anaconda3/pkgs/` | **4.9GB** | Conda包缓存 | 🔴 **可清理** |
| `~/anaconda3/` (其他) | 1.9GB | 已安装的包和程序 | ✅ 保留 |

**conda包缓存详情**:
```
503MB  mysql-5.7.24-h1a8d504_2
244MB  kaleido-core-0.2.1-hb664fd8_0
224MB  qt-main-5.15.2-h1076e38_9
191MB  libboost-1.73.0-h3fa6bed_12
... (共4.9GB)
```

### 3. **系统级缓存** - 4.8GB

| 目录 | 大小 | 说明 | 建议 |
|------|------|------|------|
| `~/Library/Caches/Google` | 1.3GB | Chrome/Google缓存 | 可清理 |
| `~/Library/Caches/pip` | 890MB | pip包缓存 | 可清理 |
| `~/Library/Caches/Homebrew` | 601MB | Homebrew缓存 | 可清理 |
| 其他 | ~2GB | 各种应用缓存 | 可清理 |

### 4. **其他缓存** - 92MB

| 目录 | 大小 | 说明 |
|------|------|------|
| `~/.cache/huggingface/` | 87MB | sentence-transformers模型 |
| Python缓存（__pycache__） | ~200KB | 89个目录，722个.pyc文件 |

---

## ✅ 项目运行状态检查

### 当前运行的进程:
- ✅ Backend API: 正常运行（PID 3018，11MB内存）
- ✅ ChromaDB: 正常（12MB，515个向量）
- ✅ 论坛数据库: 正常（908KB）
- ❌ **没有**发现大量写入或日志增长

### 日志文件状态:
- `backend/api/api.log`: 315KB（正常）
- `backend/crawler/crawler.log`: 6.9KB（正常）
- 其他日志: <10KB（正常）

### 数据库状态:
- ChromaDB: 12MB，515个向量 ✅
- Forums DB: 908KB ✅
- **无WAL或journal文件**（说明没有正在进行的长时间写入）

---

## 🔧 立即清理方案（可释放 ~5-8GB）

### 方案1: 清理Conda包缓存（释放 ~4.9GB）⭐ **推荐**

```bash
# 清理所有未使用的包和缓存
conda clean --all -y

# 或者只清理缓存
conda clean --pkg-cache -y
```

**效果**: 立即释放约 **4.9GB**

### 方案2: 清理pip缓存（释放 ~890MB）

```bash
pip cache purge
```

**效果**: 释放约 **890MB**

### 方案3: 清理系统级缓存（可选，释放 ~2-3GB）

```bash
# 清理Chrome/Google缓存（谨慎）
rm -rf ~/Library/Caches/Google/Chrome/*

# 清理Homebrew缓存
brew cleanup

# 清理pip缓存（如果上面没执行）
pip cache purge
```

**效果**: 释放约 **2-3GB**

### 方案4: 清理Next.js构建缓存（可选，释放 ~150MB）

```bash
cd frontend
rm -rf .next
```

**注意**: 下次启动会重新构建，需要等待几分钟

---

## 🎯 推荐操作顺序

1. **立即执行**（低风险，高收益）:
   ```bash
   conda clean --all -y
   pip cache purge
   ```
   **预计释放**: ~5.8GB

2. **可选执行**（中风险，中等收益）:
   ```bash
   brew cleanup
   rm -rf ~/Library/Caches/Google/Chrome/*
   ```
   **预计释放**: ~2GB

3. **最后手段**（仅当你确定不需要这些）:
   ```bash
   cd frontend && rm -rf .next
   ```
   **预计释放**: ~150MB

---

## 💡 日常维护建议

### 自动清理脚本（添加到crontab）

创建 `~/clean_cache.sh`:
```bash
#!/bin/bash
# 每周清理一次缓存

# 清理conda
conda clean --all -y

# 清理pip
pip cache purge

# 清理brew
brew cleanup

echo "Cache cleaned on $(date)" >> ~/cache_clean.log
```

设置每周运行:
```bash
chmod +x ~/clean_cache.sh
crontab -e
# 添加: 0 0 * * 0 ~/clean_cache.sh
```

---

## ❌ 排除的问题

经过检查，**以下都不是问题**:

1. ✅ 项目日志文件 - 都很小（<1MB）
2. ✅ ChromaDB数据库 - 只有12MB
3. ✅ PDF上传临时文件 - 没有发现
4. ✅ 向量化缓存 - 正常范围（87MB）
5. ✅ Python __pycache__ - 只有200KB

---

## 📋 总结

**问题根源**: anaconda的包缓存（4.9GB）和系统缓存（~2-3GB）

**项目本身占用**: 仅676MB，完全正常

**建议操作**:
```bash
# 一键清理（最安全）
conda clean --all -y && pip cache purge && brew cleanup

# 预计释放: ~6GB
```

---

生成工具: Bash + System Analysis
报告版本: 1.0
