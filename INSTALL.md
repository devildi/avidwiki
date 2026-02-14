# 安装和配置指南

## 📋 前置要求

- Python 3.9+
- Node.js 18+
- Chrome/Chromium浏览器（用于Selenium爬虫）

## 🔧 后端设置

### 1. 安装Python依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

后端已经包含预配置的开发环境配置文件 `backend/.env`。

**开发环境（默认配置）:**
- 数据库: `backend/crawler/forums.db`
- 向量库: `data/chroma_db`
- CORS: 允许 `http://localhost:3000`
- LLM: 使用本地Ollama (`http://localhost:11434/v1`)

**生产环境配置:**

复制 `.env.example` 并修改：
```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件：
```bash
# 修改CORS白名单
CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com

# 配置OpenAI（如果使用）
OPENAI_API_KEY=sk-your-actual-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
```

### 3. 初始化数据库

```bash
cd backend/crawler
python db_schema.py
```

### 4. 启动后端服务

```bash
cd backend/api
python main.py
```

后端将运行在 `http://localhost:8000`

## 🎨 前端设置

### 1. 安装Node.js依赖

```bash
cd frontend
npm install
```

### 2. 配置环境变量（可选）

前端已有默认配置指向 `http://localhost:8000`。

**如需自定义API地址:**

```bash
cd frontend
cp .env.example .env.local
```

编辑 `.env.local`：
```
NEXT_PUBLIC_API_URL=https://your-api-backend.com
```

### 3. 启动前端服务

```bash
npm run dev
```

前端将运行在 `http://localhost:3000`

## 🚀 使用流程

1. **启动服务**
   ```bash
   # 终端1: 后端
   cd backend/api && python main.py

   # 终端2: 前端
   cd frontend && npm run dev
   ```

2. **抓取数据**
   - 访问 `http://localhost:3000/settings`
   - 选择数据源，点击 "Update Now"
   - 查看实时日志输出

3. **向量化数据**
   - 爬取完成后会自动触发向量化
   - 向量数据存储在 `data/chroma_db/`

4. **开始搜索**
   - 访问 `http://localhost:3000`
   - 输入问题进行语义搜索

## 🔍 故障排查

### 后端无法启动

**问题**: `ModuleNotFoundError: No module named 'dotenv'`
```bash
# 解决方案
pip install python-dotenv
```

**问题**: 数据库文件未找到
```bash
# 解决方案：初始化数据库
cd backend/crawler
python db_schema.py
```

### 前端无法连接后端

**问题**: Network Error / CORS Error
```bash
# 检查后端是否运行在 localhost:8000
# 检查 backend/.env 中的 CORS_ORIGINS 配置
```

### 搜索无结果

**问题**: 搜索返回空结果
```bash
# 解决方案：
# 1. 确认已经运行过爬虫并抓取数据
# 2. 检查 data/chroma_db/ 目录是否存在且有数据
# 3. 查看后端日志确认向量化是否完成
```

### LLM生成失败

**问题**: "Failed to generate AI summary"

**使用Ollama（推荐）:**
```bash
# 安装Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 下载模型
ollama pull llama3

# 启动Ollama服务
ollama serve
```

**使用OpenAI:**
```bash
# 在 backend/.env 中配置
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
```

## 📝 生产环境部署

### 安全检查清单

- [x] 修改 `CORS_ORIGINS` 为实际前端域名
- [x] 使用HTTPS部署
- [x] 配置API密钥（如使用OpenAI）
- [x] 设置防火墙规则
- [x] 配置日志轮转
- [x] 定期备份数据库

### 推荐部署架构

```
┌─────────────┐
│   Nginx     │ (反向代理 + SSL)
└──────┬──────┘
       │
       ├─────────────┬─────────────┐
       │             │             │
┌──────▼──────┐ ┌───▼────┐ ┌─────▼─────┐
│   Frontend  │ │ Backend │ │   Ollama  │
│  (Next.js)  │ │(FastAPI)│ │  (可选)   │
└─────────────┘ └─────────┘ └───────────┘
```

## 📚 更多信息

- 详细API文档: `http://localhost:8000/docs` (FastAPI自动生成)
- 查看日志: `backend/api/api.log`
- 数据库位置: `backend/crawler/forums.db`
- 向量库位置: `data/chroma_db/`
