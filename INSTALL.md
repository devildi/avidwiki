# 安装和配置指南

## 📋 前置要求

- Python 3.9+
- Node.js 18+
- Chrome/Chromium浏览器（用于Selenium爬虫）

## ⚡️ 快速初始化（推荐）

从 GitHub 克隆到本地后，你可以直接使用项目根目录下的 **`init.sh`** 脚本进行一键自动初始化：

```bash
bash init.sh
```

该脚本将自动执行以下任务：
1. 检测系统中的 Python 3 和 Node.js 环境。
2. 自动构建独立的 `.venv` 虚拟环境。
3. 一键安装后端所有的 Python 依赖包。
4. 复制和配置前端与后端的 `.env` 环境变量配置文件。
5. 自动创建数据库文件目录，并初始化 SQLite 和 Vector 数据库架构。
6. 自动进入前端目录安装所有的 Node.js 依赖包。

完成初始化后，直接运行 **`bash start.sh`** 即可一键启动前后端服务！

---

## 🔧 手动安装与配置指南（备用）

如果你不希望使用一键初始化脚本，也可以按照以下步骤手动设置项目：

### 后端设置

#### 1. 创建并激活 Python 虚拟环境
为了防止包依赖冲突，强烈建议在项目根目录下使用虚拟环境：
```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate
```

#### 2. 安装 Python 依赖
在激活虚拟环境的状态下，安装后端核心依赖库：
```bash
pip install -r backend/requirements.txt
```

#### 3. 配置环境变量
复制并创建后端的环境变量配置文件：
```bash
cp backend/.env.example backend/.env
```
（开发环境默认即可，生产环境可以根据 `.env` 内的注释自行配置跨域 `CORS_ORIGINS` 或 OpenAI Key。）

#### 4. 初始化数据库
```bash
# 激活虚拟环境的状态下
python backend/crawler/db_schema.py
```

#### 5. 启动后端服务
```bash
# 激活虚拟环境的状态下
python backend/api/main.py
```
后端服务将运行在 `http://localhost:8000`

### 前端设置

#### 1. 配置环境变量
复制并创建前端的环境变量配置文件：
```bash
cp frontend/.env.example frontend/.env.local
```

#### 2. 安装 Node.js 依赖
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
