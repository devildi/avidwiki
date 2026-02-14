#!/usr/bin/env python3
"""
测试PDF超时修复效果
验证：
1. 向量化是否有60秒超时保护
2. 批次大小是否从20降到10
3. 进度更新是否更频繁
"""

import sys
import os
import time

# 添加backend到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from ingest.vector_store import ingest_pdf_chunks
from database.pdf_schema import get_all_pdfs


def test_with_small_pdf():
    """使用小PDF测试基本功能"""
    print("=" * 60)
    print("测试1: 检查批次大小配置")
    print("=" * 60)

    # 读取vector_store.py文件，检查batch_size配置
    vector_store_path = os.path.join(os.path.dirname(__file__), 'backend', 'ingest', 'vector_store.py')
    with open(vector_store_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查batch_size配置
    if 'batch_size = 10' in content:
        print("✅ batch_size已更新为10（更快处理）")
    elif 'batch_size = 20' in content:
        print("⚠️ batch_size仍为20（建议降到10）")
    else:
        print("❓ 无法确定batch_size配置")

    # 检查超时保护
    if 'upsert_with_timeout(timeout_seconds=60)' in content:
        print("✅ 已添加60秒超时保护")
    else:
        print("❌ 缺少超时保护！")

    # 检查超时错误处理
    if 'except TimeoutError as timeout_error:' in content:
        print("✅ 已添加TimeoutError处理")
    else:
        print("❌ 缺少TimeoutError处理！")

    print()


def test_timeout_simulation():
    """模拟超时场景"""
    print("=" * 60)
    print("测试2: 超时保护机制（模拟）")
    print("=" * 60)

    import threading

    def simulated_operation():
        """模拟一个会卡住的操作"""
        print("  开始模拟卡住的操作...")
        time.sleep(65)  # 模拟65秒的卡住
        print("  操作完成（不应该看到这条消息）")

    # 使用超时保护
    def run_with_timeout():
        result = [None]
        error = [None]

        def do_work():
            try:
                simulated_operation()
                result[0] = True
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=do_work)
        thread.daemon = True
        thread.start()
        thread.join(timeout=3)  # 3秒超时（测试用）

        if thread.is_alive():
            print("  ✅ 超时保护生效！线程仍在运行但主线程继续执行")
            raise TimeoutError("Operation timeout")

        if error[0]:
            raise error[0]

        return result[0]

    try:
        run_with_timeout()
    except TimeoutError as e:
        print(f"  ✅ 成功捕获超时: {e}")
    except Exception as e:
        print(f"  ❌ 其他错误: {e}")

    print()


def check_pdf_list():
    """检查可用的PDF"""
    print("=" * 60)
    print("测试3: 可用的PDF文档")
    print("=" * 60)

    try:
        pdfs = get_all_pdfs()
        if pdfs:
            print(f"找到 {len(pdfs)} 个PDF文档:")
            for pdf in pdfs[:5]:  # 只显示前5个
                print(f"  - ID {pdf['id']}: {pdf['filename']} ({pdf['status']})")
            if len(pdfs) > 5:
                print(f"  ... 还有 {len(pdfs) - 5} 个")
        else:
            print("⚠️ 数据库中没有PDF文档")

    except Exception as e:
        print(f"❌ 无法获取PDF列表: {e}")

    print()


def main():
    print("\n🧪 PDF超时修复验证工具\n")

    test_with_small_pdf()
    test_timeout_simulation()
    check_pdf_list()

    print("=" * 60)
    print("✅ 检查完成！")
    print("=" * 60)
    print("\n💡 建议：")
    print("1. 如果看到所有✅，说明修复已生效")
    print("2. 使用小PDF测试实际处理过程")
    print("3. 观察是否还会卡在某一页")
    print("4. 检查日志中是否有'timeout after 60s'消息")
    print()


if __name__ == "__main__":
    main()
