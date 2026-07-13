#!/usr/bin/env python3
import os
import sys
import argparse
import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.text import Text

API_BASE = "http://127.0.0.1:8000"
console = Console()

def print_banner():
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                 AvidWiki 知识检索命令行工具                   ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(Panel(Text(banner.strip(), style="bold purple", justify="center"), border_style="purple"))
    console.print("💡 输入查询内容直接检索。输入 [bold cyan]/exit[/] 退出，输入 [bold cyan]/help[/] 查看更多指令。\n")

def print_help():
    table = Table(title="命令行指令说明", show_header=True, header_style="bold magenta")
    table.add_column("指令", style="cyan")
    table.add_column("说明", style="white")
    table.add_row("/exit, /quit, exit, quit", "退出程序")
    table.add_row("/help, help", "显示此帮助菜单")
    table.add_row("/filter pdf", "过滤检索来源：仅限 PDF 文档")
    table.add_row("/filter forum", "过滤检索来源：仅限 论坛数据")
    table.add_row("/filter all", "不过滤（默认检索所有来源）")
    table.add_row("/limit <数字>", "设置返回的相关文档条数上限 (例如 /limit 10)")
    console.print(table)

def handle_search(query: str, limit: int, source_filter: str):
    payload = {
        "query": query,
        "limit": limit,
    }
    if source_filter and source_filter != "all":
        payload["source_filter"] = source_filter

    try:
        with console.status("[bold purple]正在检索知识库并思考回答...", spinner="dots"):
            response = requests.post(f"{API_BASE}/search", json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "")
            sources = data.get("sources", [])

            # 显示 AI 回答
            console.print(Panel(Markdown(answer), title="[bold green]AvidWiki 助手智能回答[/bold green]", border_style="green"))

            # 显示引用来源
            if sources:
                table = Table(title="📖 引用来源", show_header=True, header_style="bold blue", border_style="blue")
                table.add_column("序号", justify="center", style="cyan")
                table.add_column("来源类型", style="magenta")
                table.add_column("标题/位置", style="green")
                table.add_column("摘要内容", style="white")

                for idx, src in enumerate(sources, 1):
                    src_type = "📄 PDF 文档" if 'filename' in src else "💬 论坛问答"
                    title = src.get('filename') if 'filename' in src else src.get('title', 'Unknown')
                    if 'page' in src:
                        title += f" (第 {src['page']} 页)"
                    snippet = src.get('snippet', '')
                    table.add_row(str(idx), src_type, title, snippet[:120] + "...")
                
                console.print(table)
            else:
                console.print("[yellow]⚠️ 未找到相关引用的参考文档。[/yellow]")
        else:
            console.print(f"[red]✗ 检索失败，后端返回错误 ({response.status_code}): {response.text}[/red]")
    except requests.exceptions.ConnectionError:
        console.print(Panel(
            "[red]✗ 无法连接到后端服务。请确保后端服务正常运行中！[/red]\n\n"
            "💡 [bold]如何启动后端？[/bold]\n"
            "请在项目根目录下新开终端运行：\n"
            "   [bold cyan]source .venv/bin/activate[/]\n"
            "   [bold cyan]python backend/api/main.py[/]",
            title="[bold red]服务连接失败[/bold red]",
            border_style="red"
        ))
    except Exception as e:
        console.print(f"[red]✗ 发生异常错误: {str(e)}[/red]")

def main():
    parser = argparse.ArgumentParser(description="AvidWiki 知识检索命令行交互工具")
    parser.add_argument("query", nargs="?", default=None, help="可选：直接输入查询词进行检索，检索完将自动退出")
    parser.add_argument("-l", "--limit", type=int, default=5, help="检索返回的文档上限数 (默认: 5)")
    parser.add_argument("-f", "--filter", choices=["all", "pdf", "forum"], default="all", help="过滤来源类型：all (全部), pdf (仅文档), forum (仅论坛) (默认: all)")
    args = parser.parse_args()

    limit = args.limit
    source_filter = args.filter

    # 如果有直接传入查询词，则进行单次检索并退出
    if args.query:
        handle_search(args.query, limit, source_filter)
        sys.exit(0)

    # 否则，进入交互模式
    print_banner()
    while True:
        try:
            filter_desc = {
                "all": "全部来源",
                "pdf": "仅 PDF",
                "forum": "仅论坛"
            }.get(source_filter, source_filter)
            
            prompt_text = f"AvidWiki ({filter_desc}, limit:{limit}) > "
            user_input = Prompt.ask(prompt_text).strip()

            if not user_input:
                continue

            # 处理指令
            if user_input.lower() in ["/exit", "/quit", "exit", "quit"]:
                console.print("[purple]再见！感谢使用 AvidWiki 命令行工具。[/purple]")
                break
            elif user_input.lower() in ["/help", "help", "?", "？"]:
                print_help()
                continue
            elif user_input.startswith("/filter"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1] in ["all", "pdf", "forum"]:
                    source_filter = parts[1]
                    console.print(f"[green]✓ 已将检索来源过滤设为：{source_filter}[/green]")
                else:
                    console.print("[red]❌ 无效的过滤类型，请选择: all, pdf, forum[/red]")
                continue
            elif user_input.startswith("/limit"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].isdigit():
                    limit = int(parts[1])
                    console.print(f"[green]✓ 已将检索返回文档数限制设为：{limit}[/green]")
                else:
                    console.print("[red]❌ 无效的 limit 值，请输入一个正整数，例如: /limit 10[/red]")
                continue
            elif user_input.startswith("/"):
                console.print(f"[red]❌ 未知指令: {user_input}。输入 /help 查看指令列表。[/red]")
                continue

            # 执行查询
            handle_search(user_input, limit, source_filter)
            console.print()

        except KeyboardInterrupt:
            # 捕获 Ctrl+C
            console.print("\n[purple]再见！感谢使用 AvidWiki 命令行工具。[/purple]")
            break
        except Exception as e:
            console.print(f"[red]错误: {str(e)}[/red]")

if __name__ == "__main__":
    main()
