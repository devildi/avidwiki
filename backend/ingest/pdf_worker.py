"""
独立 PDF 页面提取脚本
被 LargePDFExtractor 通过 subprocess 调用
用于实现完全的进程隔离和临时文件沙盒化
"""
import sys
import os
import argparse
import time

# 尝试导入 fitz
try:
    import fitz  # PyMuPDF
except ImportError:
    print("__ERROR__PyMuPDF not installed", file=sys.stderr)
    sys.exit(1)

# 尝试导入 resource (仅 Unix)
try:
    import resource
except ImportError:
    resource = None

def extract_page(pdf_path, page_num, output_path):
    """提取单页文本并写入文件"""
    try:
        # 1. 设置内存限制 (2GB)
        if resource:
            try:
                limit = 2 * 1024 * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            except Exception:
                pass

        # 2. 打开文档
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = fitz.open(pdf_path)
        
        # 3. 获取页面
        if page_num < 0 or page_num >= doc.page_count:
            raise ValueError(f"Page number {page_num} out of range (0-{doc.page_count-1})")
            
        page = doc[page_num]
        
        # 4. 提取文本
        # 使用 text 模式，最快且内存最少
        text = page.get_text("text")
        
        doc.close()
        
        # 5. 写入结果
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text if text else "")
            
    except MemoryError:
        # 内存超限
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("__ERROR__MemoryError: Page exceeded 2GB limit")
        sys.exit(2)
        
    except Exception as e:
        # 其他错误
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"__ERROR__{str(e)}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Extract text from a single PDF page")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--page", type=int, required=True, help="Page number (0-indexed)")
    parser.add_argument("--output", required=True, help="Path to output text file")
    
    args = parser.parse_args()
    
    extract_page(args.pdf, args.page, args.output)

if __name__ == "__main__":
    main()
