#!/usr/bin/env python3
"""
大 PDF 文档性能测试脚本
测试处理 1300+ 页 PDF 的性能和内存使用
"""

import os
import sys
import time
import psutil
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_memory_usage():
    """获取当前进程内存使用（MB）"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def test_pdf_performance(pdf_path: str):
    """测试 PDF 处理性能"""
    if not os.path.exists(pdf_path):
        logger.error(f"PDF 文件不存在: {pdf_path}")
        return

    logger.info(f"{'='*60}")
    logger.info(f"开始测试: {os.path.basename(pdf_path)}")
    logger.info(f"{'='*60}")

    # 记录初始内存
    initial_memory = get_memory_usage()
    logger.info(f"初始内存使用: {initial_memory:.2f} MB")

    try:
        # 测试 1: 导入模块
        logger.info("\n[步骤 1] 导入模块...")
        import_time = time.time()
        from backend.ingest.pdf_extractor import PDFExtractor
        logger.info(f"✓ 模块导入完成 ({time.time() - import_time:.2f}s)")

        # 测试 2: 获取 PDF 信息
        logger.info("\n[步骤 2] 获取 PDF 基本信息...")
        info_time = time.time()
        extractor = PDFExtractor(pdf_path)
        info = extractor.get_pdf_info()
        logger.info(f"✓ PDF 信息获取完成 ({time.time() - info_time:.2f}s)")
        logger.info(f"  - 文件名: {info['filename']}")
        logger.info(f"  - 文件大小: {info['file_size'] / 1024 / 1024:.2f} MB")
        logger.info(f"  - 总页数: {info['total_pages']}")

        # 检查内存
        current_memory = get_memory_usage()
        logger.info(f"  - 当前内存: {current_memory:.2f} MB (增加 {current_memory - initial_memory:.2f} MB)")

        # 测试 3: 文本提取和分块
        logger.info("\n[步骤 3] 提取文本和分块...")
        extract_start = time.time()
        chunks = extractor.extract_text()
        extract_time = time.time() - extract_start

        logger.info(f"✓ 文本提取完成 ({extract_time:.2f}s)")
        logger.info(f"  - 总 chunks 数: {len(chunks)}")

        # 计算统计信息
        if chunks:
            total_chars = sum(len(c['content']) for c in chunks)
            avg_chars = total_chars / len(chunks)
            logger.info(f"  - 总字符数: {total_chars:,}")
            logger.info(f"  - 平均 chunk 大小: {avg_chars:.0f} 字符")

            # 显示第一个和最后一个 chunk 的信息
            logger.info(f"\n  第一个 chunk:")
            logger.info(f"    - 页码: {chunks[0]['metadata']['page']}")
            logger.info(f"    - 大小: {len(chunks[0]['content'])} 字符")
            logger.info(f"    - 预览: {chunks[0]['content'][:100]}...")

            logger.info(f"\n  最后一个 chunk:")
            logger.info(f"    - 页码: {chunks[-1]['metadata']['page']}")
            logger.info(f"    - 大小: {len(chunks[-1]['content'])} 字符")

        # 检查内存
        current_memory = get_memory_usage()
        logger.info(f"  - 当前内存: {current_memory:.2f} MB (增加 {current_memory - initial_memory:.2f} MB)")

        # 测试 4: 计算性能指标
        logger.info("\n[性能指标]")
        total_pages = info['total_pages']
        pages_per_second = total_pages / extract_time if extract_time > 0 else 0
        logger.info(f"  - 处理速度: {pages_per_second:.1f} 页/秒")
        logger.info(f"  - 预计 1300 页耗时: {1300 / pages_per_second:.1f} 秒 ({1300 / pages_per_second / 60:.1f} 分钟)" if pages_per_second > 0 else "")
        logger.info(f"  - 每页平均: {extract_time / total_pages:.3f} 秒")

        # 测试 5: 向量化测试（可选，仅测试前 100 个 chunks）
        logger.info("\n[步骤 4] 向量化测试（仅前 100 chunks）...")
        if len(chunks) > 100:
            test_chunks = chunks[:100]
            logger.info(f"  测试 {len(test_chunks)} 个 chunks...")

            embedding_start = time.time()
            try:
                from backend.ingest.vector_store import setup_chroma
                collection = setup_chroma()

                ids = [c['id'] for c in test_chunks]
                documents = [c['content'] for c in test_chunks]
                metadatas = [c['metadata'] for c in test_chunks]

                collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
                embedding_time = time.time() - embedding_start

                logger.info(f"✓ 向量化完成 ({embedding_time:.2f}s)")
                logger.info(f"  - 速度: {len(test_chunks) / embedding_time:.1f} chunks/秒")

                # 预估全部向量化时间
                estimated_total = (len(chunks) / embedding_time) * embedding_time
                logger.info(f"  - 预计全部 {len(chunks)} chunks 耗时: {estimated_total:.1f} 秒 ({estimated_total/60:.1f} 分钟)")

            except Exception as e:
                logger.error(f"✗ 向量化失败: {e}")

        # 最终内存检查
        final_memory = get_memory_usage()
        logger.info(f"\n[内存使用总结]")
        logger.info(f"  - 初始: {initial_memory:.2f} MB")
        logger.info(f"  - 峰值: {current_memory:.2f} MB")
        logger.info(f"  - 增长: {final_memory - initial_memory:.2f} MB")

        logger.info(f"\n{'='*60}")
        logger.info(f"✓ 测试完成")
        logger.info(f"{'='*60}\n")

    except Exception as e:
        logger.error(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    if len(sys.argv) < 2:
        print("用法: python3 test_large_pdf.py <pdf_file_path>")
        print("\n示例:")
        print("  python3 test_large_pdf.py backend/data/pdfs/large_document.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    test_pdf_performance(pdf_path)


if __name__ == "__main__":
    main()
