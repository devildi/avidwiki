# Python 虚拟环境使用指南 (Python Virtual Environment Guide)

为了保证项目的依赖隔离和稳定运行，本项目推荐并默认使用 **Python 虚拟环境 (Virtual Environment)**。本篇文档将详细介绍为什么需要使用虚拟环境、以及如何在本项目中进行日常开发与管理。

---

## 1. 什么是虚拟环境？

Python 虚拟环境（在本项目中对应的文件夹为 `.venv`）是一个**独立且隔离的 Python 运行环境**。它拥有自己独立的 Python 解释器、二进制文件（如 `pip`、`uvicorn` 等）以及独立的第三方库目录（`site-packages`）。

---

## 2. 为什么在此项目中使用虚拟环境？

在本规范化项目中，使用虚拟环境有以下几个核心原因：

1. **依赖隔离，避免冲突**：
   本项目使用了如 `FastAPI` (Web框架)、`ChromaDB` (向量数据库)、`torch`/`sentence-transformers` (AI/嵌入模型) 以及 `selenium`/`pdfplumber` 等大量的第三方依赖。
   * 如果直接安装在全局系统 Python 中，可能会与系统其他软件或你的其他 Python 项目的依赖版本产生冲突。
2. **解决系统 Python 版本过旧的问题**：
   * macOS 系统自带的 Python 版本（如 `/usr/bin/python3`）通常为较旧的版本（例如 3.8.9），它无法满足本项目要求的 `Python 3.9+` 运行环境（很多现代 AI 库和 FastAPI 特性不支持 3.8）。
   * 本项目通过虚拟环境将 Python 升级到了稳定的 **Python 3.11** 运行环境。
3. **免除系统管理员权限**：
   * 在全局环境下安装包经常需要 `sudo pip install`，这会带来安全风险并可能破坏操作系统的基础组件。虚拟环境允许你在自己的项目文件夹内无需任何高权限即可自由安装包。

---

## 3. 如何使用虚拟环境？

### 方法一：激活虚拟环境进行开发（最推荐）

在运行任何 Python 命令或启动后端服务前，建议先在终端中**激活**虚拟环境：

```bash
# 在项目根目录下执行
source .venv/bin/activate
```

**激活后的变化：**
* 你的终端命令行前缀会出现 `(.venv)` 标识（例如：`(.venv) user@mac wiki %`）。
* 此时在终端里运行 `python` 或 `pip` 命令，会自动指向当前项目目录下的虚拟环境。

**退出虚拟环境：**
当你开发完毕想切换回系统全局环境时，只需输入：
```bash
deactivate
```

---

### 方法二：不激活环境直接调用（适用于脚本/快捷启动）

如果你不想执行 `source` 激活命令，也可以使用**绝对/相对路径**直接调用虚拟环境的 Python 解释器。

例如，在根目录下启动后端服务：
```bash
.venv/bin/python backend/api/main.py
```
这与激活虚拟环境后运行 `python backend/api/main.py` 的效果完全相同。

*(注意：我们已经对项目中的一键启动脚本 `start.sh` 和 `restart_backend.sh` 进行了升级，它们会自动检测并调用 `.venv/bin/python`，因此你可以直接运行 `bash start.sh`，无需手动激活虚拟环境。)*

---

## 4. 虚拟环境下的常用依赖管理

当你在虚拟环境中开发时，可以通过以下方式管理第三方库：

### 1) 查看当前虚拟环境已安装的包
```bash
# 激活状态下：
pip list

# 未激活状态下：
.venv/bin/python -m pip list
```

### 2) 安装新的第三方库
如果你需要引入新的 Python 库，请使用以下命令：
```bash
# 推荐使用超快速的 uv 工具安装（已在你的环境配置完毕）
/Users/DevilDI/.local/bin/uv pip install <库名>

# 也可以使用传统的 pip 安装
.venv/bin/python -m pip install <库名>
```

### 3) 更新项目的 `requirements.txt`
当你为项目新增了依赖库，需要更新 requirements 列表以便其他协作者同步时，建议手动将新增的包和版本写入以下文件：
* [backend/requirements.txt](file:///Users/DevilDI/Desktop/projects/wiki/backend/requirements.txt)

---

## 5. 常见问题排查 (FAQ)

### ❓ 报错 `zsh: command not found: python`
* **原因**：macOS 默认移除了全局的 `python` 指向，只保留了 `python3`。
* **解决办法**：请运行 `source .venv/bin/activate` 激活虚拟环境。激活后虚拟环境会自动创建一个 `python` 的软链接，你就可以直接使用 `python` 命令了。

### ❓ 报错 `ModuleNotFoundError: No module named 'fastapi'`
* **原因**：你的终端在运行 `python3 backend/api/main.py` 时使用的是系统自带的全局 Python，而不是本项目构建的虚拟环境。
* **解决办法**：
  * **方式 A**：使用 `.venv/bin/python backend/api/main.py` 运行。
  * **方式 B**：先执行 `source .venv/bin/activate`，然后再执行 `python backend/api/main.py`。
