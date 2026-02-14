#!/usr/bin/env python3
"""
快速 PDF 性能测试 - 仅测试前 N 页
"""
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_first_n_pages(pdf_path: str, n_pages: int = 100):
    """测试前 N 页"""
    print(f"\n{'='*60}")
    print(f"快速测试: {os.path.basename(pdf_path)} (前 {n_pages} 页)")
    print(f"{'='*60}\n")

    start_time = time.time()

    try:
        from ingest.pdf_extractor import PDFExtractor

        # 初始化
        print(f"[1/3] 初始化提取器...")
        extractor = PDFExtractor(pdf_path)
        info = extractor.get_pdf_info()
        print(f"  ✓ PDF 总页数: {info['total_pages']}")
        print(f"  ✓ 文件大小: {info['file_size'] / 1024 / 1024:.2f} MB")

        # 修改：只处理前 N 页
        print(f"\n[2/3] 提取前 {n_pages} 页文本...")
        import pdfplumber

        chunks = []
        page_start = time.time()

        with pdfplumber.open(pdf_path) as pdf:
            total_to_process = min(n_pages, len(pdf.pages))

            for page_num, page in enumerate(pdf.pages[:total_to_process], 1):
                text = page.extract_text()

                if text and len(text.strip()) >= 10:
                    text = extractor._clean_text(text)
                    page_chunks = extractor._split_text(text)

                    for i, chunk_text in enumerate(page_chunks):
                        chunk_id = extractor._generate_chunk_id(info['filename'], page_num, i)
                        chunks.append({
                            "id": chunk_id,
                            "content": chunk_text,
                            "metadata": {
                                "source": "pdf",
                                "filename": info['filename'],
                                "page": page_num,
                                "chunk_index": i,
                                "total_pages": info['total_pages'],
                                "doc_type": "manual"
                            }
                        })

                if page_num % 10 == 0:
                    elapsed = time.time() - page_start
                    speed = page_num / elapsed
                    print(f"  进度: {page_num}/{total_to_process} 页 ({speed:.1f} 页/秒)")

        page_time = time.time() - page_start
        print(f"\n  ✓ 文本提取完成 ({page_time:.1f}s)")
        print(f"  ✓ 生成 chunks: {len(chunks)} 个")
        print(f"  ✓ 处理速度: {n_pages / page_time:.1f} 页/秒")

        # 估算
        print(f"\n[3/3] 性能估算:")
        total_pages = info['total_pages']
        estimated_time = (total_pages * page_time) / n_pages
        print(f"  • 预计文本提取总时间: {estimated_time:.1f} 秒 ({estimated_time/60:.1f} 分钟)")
        print(f"  • 预计总 chunks 数: {(len(chunks) * total_pages) // n_pages:,} 个")
        print(f"  • 预计向量化时间: {((len(chunks) * total_pages) // n_pages) / 30:.1f} 秒 ({((len(chunks) * total_pages) // n_pages) / 30 / 60:.1f} 分钟)")
        print(f"  • 预计总处理时间: {(estimated_time + ((len(chunks) * total_pages) // n_pages) / 30) / 60:.1f} 分钟")

        print(f"\n{'='*60}")
        print(f"✓ 测试完成")
        print(f"{'='*60}\n")

        return True

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 test_pdf_quick.py <pdf_file> [pages=100]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    n_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    test_first_n_pages(pdf_path, n_pages)
