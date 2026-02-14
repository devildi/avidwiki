#!/usr/bin/env python3
"""
PDF 功能测试脚本
测试 PDF 上传、索引和搜索的完整流程
"""

import os
import sys
import time
import requests

# 配置
API_BASE = "http://localhost:8000"
TEST_PDF_PATH = "test_sample.pdf"  # 需要用户提供测试 PDF

# 颜色输出
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.NC}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.NC}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.NC}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.NC}")

def test_backend_connection():
    """测试后端连接"""
    print_info("测试 1: 后端连接")
    try:
        response = requests.get(f"{API_BASE}/sources", timeout=5)
        if response.status_code == 200:
            print_success("后端连接正常")
            return True
        else:
            print_error(f"后端返回错误: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"无法连接后端: {e}")
        print_warning("请确保后端正在运行: python3 backend/api/main.py")
        return False

def test_pdf_list():
    """测试 PDF 列表接口"""
    print_info("\n测试 2: PDF 列表接口")
    try:
        response = requests.get(f"{API_BASE}/pdf/list")
        if response.status_code == 200:
            pdfs = response.json()
            print_success(f"PDF 列表接口正常，当前有 {len(pdfs)} 个 PDF")
            return pdfs
        else:
            print_error(f"PDF 列表返回错误: {response.status_code}")
            return []
    except Exception as e:
        print_error(f"PDF 列表请求失败: {e}")
        return []

def test_pdf_upload(pdf_path):
    """测试 PDF 上传"""
    print_info(f"\n测试 3: PDF 上传 ({pdf_path})")

    if not os.path.exists(pdf_path):
        print_error(f"文件不存在: {pdf_path}")
        print_warning("请将测试 PDF 文件放在项目根目录，命名为 test_sample.pdf")
        return None

    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            response = requests.post(f"{API_BASE}/pdf/upload", files=files)

        if response.status_code == 200:
            result = response.json()
            print_success(f"PDF 上传成功！")
            print_info(f"  - PDF ID: {result['pdf_id']}")
            print_info(f"  - 文件名: {result['filename']}")
            print_info(f"  - 文件大小: {result['file_size']} bytes")
            return result['pdf_id']
        else:
            print_error(f"上传失败: {response.status_code}")
            print_error(f"错误信息: {response.text}")
            return None
    except Exception as e:
        print_error(f"上传请求失败: {e}")
        return None

def test_pdf_indexing(pdf_id):
    """测试 PDF 索引"""
    print_info(f"\n测试 4: PDF 索引 (PDF ID: {pdf_id})")

    try:
        # 启动索引
        response = requests.post(f"{API_BASE}/pdf/{pdf_id}/index")
        if response.status_code != 200:
            print_error(f"索引启动失败: {response.status_code}")
            return False

        print_success("索引任务已启动")

        # 监控进度（简化版，不使用 SSE）
        print_info("等待索引完成...")
        for i in range(30):  # 最多等待 30 秒
            time.sleep(1)
            pdfs = requests.get(f"{API_BASE}/pdf/list").json()
            pdf = next((p for p in pdfs if p['id'] == pdf_id), None)

            if pdf and pdf['status'] == 'completed':
                print_success(f"索引完成！")
                print_info(f"  - 总页数: {pdf['total_pages']}")
                print_info(f"  - 总 chunks: {pdf['total_chunks']}")
                return True
            elif pdf and pdf['status'] == 'failed':
                print_error(f"索引失败: {pdf.get('error', 'Unknown error')}")
                return False

        print_warning("索引超时（30秒），请检查日志")
        return False

    except Exception as e:
        print_error(f"索引请求失败: {e}")
        return False

def test_search():
    """测试搜索功能"""
    print_info("\n测试 5: 搜索功能")

    try:
        response = requests.post(f"{API_BASE}/search", json={
            "query": "test search",
            "limit": 5
        })

        if response.status_code == 200:
            result = response.json()
            print_success(f"搜索成功，找到 {len(result['sources'])} 个结果")

            # 检查是否有 PDF 来源的结果
            pdf_sources = [s for s in result['sources'] if 'filename' in str(s)]
            if pdf_sources:
                print_success("搜索结果包含 PDF 内容！")
                print_info(f"  - 示例: {pdf_sources[0].get('title', 'N/A')}")
            else:
                print_warning("搜索结果中没有 PDF 内容（可能还未索引）")

            return True
        else:
            print_error(f"搜索失败: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"搜索请求失败: {e}")
        return False

def test_pdf_delete(pdf_id):
    """测试 PDF 删除"""
    print_info(f"\n测试 6: PDF 删除 (PDF ID: {pdf_id})")

    try:
        response = requests.delete(f"{API_BASE}/pdf/{pdf_id}")
        if response.status_code == 200:
            print_success("PDF 删除成功")
            return True
        else:
            print_error(f"删除失败: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"删除请求失败: {e}")
        return False

def main():
    print(f"\n{Colors.BLUE}{'='*50}{Colors.NC}")
    print(f"{Colors.BLUE}PDF 功能测试脚本{Colors.NC}")
    print(f"{Colors.BLUE}{'='*50}{Colors.NC}\n")

    # 测试流程
    if not test_backend_connection():
        print_error("\n测试失败：后端未运行")
        print_info("请先启动后端: bash start.sh")
        return

    pdfs = test_pdf_list()

    # 如果有测试文件，测试上传和索引
    if os.path.exists(TEST_PDF_PATH):
        pdf_id = test_pdf_upload(TEST_PDF_PATH)

        if pdf_id:
            if test_pdf_indexing(pdf_id):
                test_search()

            # 清理测试数据
            cleanup = input(f"\n{Colors.YELLOW}是否删除测试 PDF? (y/n): {Colors.NC}")
            if cleanup.lower() == 'y':
                test_pdf_delete(pdf_id)
    else:
        print_warning(f"\n未找到测试 PDF 文件 ({TEST_PDF_PATH})")
        print_info("跳过上传和索引测试")
        print_info(f"如需完整测试，请将测试 PDF 放在项目根目录并命名为 {TEST_PDF_PATH}")

        # 如果已有 PDF，测试搜索
        if pdfs:
            print_info(f"\n发现 {len(pdfs)} 个已上传的 PDF，测试搜索...")
            test_search()

    print(f"\n{Colors.GREEN}{'='*50}{Colors.NC}")
    print(f"{Colors.GREEN}测试完成！{Colors.NC}")
    print(f"{Colors.GREEN}{'='*50}{Colors.NC}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\n测试被用户中断")
    except Exception as e:
        print_error(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
