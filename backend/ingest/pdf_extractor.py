"""
PDF 文档提取器 - MVP 版本 (基于 PyMuPDF)
"""
import os
import hashlib
import re
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    logger.error("PyMuPDF not installed. Run: pip install pymupdf")
    raise


class PDFExtractor:
    """PDF 文本提取和分块"""

    def __init__(self, pdf_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        初始化 PDF 提取器

        Args:
            pdf_path: PDF 文件路径
            chunk_size: 每块字符数
            chunk_overlap: 块之间重叠字符数
        """
        self.pdf_path = pdf_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.filename = os.path.basename(pdf_path)

    def extract_text(self) -> List[Dict]:
        """
        提取 PDF 文本并分块

        Returns:
            包含文本块和元数据的字典列表
        """
        chunks = []

        try:
            doc = fitz.open(self.pdf_path)
            total_pages = doc.page_count
            logger.info(f"Processing PDF with PyMuPDF: {self.filename} ({total_pages} pages)")

            current_chunk_id = 0

            for page_num, page in enumerate(doc, 1):
                # 提取页面文本
                text = page.get_text()

                if not text or len(text.strip()) < 10:
                    logger.warning(f"Page {page_num} has little or no text, skipping")
                    continue

                # 清理文本
                text = self._clean_text(text)

                # 分块
                page_chunks = self._split_text(text)

                # 为每个块添加元数据
                for i, chunk_text in enumerate(page_chunks):
                    chunk_id = self._generate_chunk_id(self.filename, page_num, i)

                    chunks.append({
                        "id": chunk_id,
                        "content": chunk_text,
                        "metadata": {
                            "source": "pdf",
                            "filename": self.filename,
                            "page": page_num,
                            "chunk_index": i,
                            "total_pages": total_pages,
                            "doc_type": "manual"
                        }
                    })

                    current_chunk_id += 1

                if page_num % 10 == 0:
                    logger.info(f"Processed {page_num}/{total_pages} pages")
            
            doc.close()

            logger.info(f"Extraction complete: {len(chunks)} chunks created")
            return chunks

        except Exception as e:
            logger.error(f"Error extracting PDF {self.pdf_path}: {e}", exc_info=True)
            raise

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除页码等噪音（简单模式）
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        return text.strip()

    def _split_text(self, text: str) -> List[str]:
        """
        简单文本分块（固定大小）

        Args:
            text: 输入文本

        Returns:
            文本块列表
        """
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.chunk_size

            # 如果不是最后一块，尝试在句子边界切分
            if end < text_length:
                # 寻找最近的句号、问号、感叹号
                for delimiter in ['。', '！', '？', '. ', '! ', '? ', '\n\n']:
                    delimiter_pos = text.rfind(delimiter, start, end)
                    if delimiter_pos != -1:
                        end = delimiter_pos + len(delimiter)
                        break

            chunk = text[start:end].strip()

            if len(chunk) > 50:  # 只保留有意义的块
                chunks.append(chunk)

            # 移动到下一个块（考虑重叠）
            start = end - self.chunk_overlap if end < text_length else end

        return chunks

    def _generate_chunk_id(self, filename: str, page_num: int, chunk_index: int) -> str:
        """生成唯一的 chunk ID"""
        unique_string = f"{filename}_{page_num}_{chunk_index}"
        hash_obj = hashlib.md5(unique_string.encode())
        return f"pdf_{hash_obj.hexdigest()}"

    def get_pdf_info(self) -> Dict:
        """获取 PDF 基本信息"""
        try:
            doc = fitz.open(self.pdf_path)
            info = {
                "filename": self.filename,
                "total_pages": doc.page_count,
                "file_size": os.path.getsize(self.pdf_path)
            }
            doc.close()
            return info
        except Exception as e:
            logger.error(f"Error getting PDF info: {e}")
            return None


def test_extraction(pdf_path: str):
    """测试 PDF 提取"""
    extractor = PDFExtractor(pdf_path)

    # 获取信息
    info = extractor.get_pdf_info()
    print(f"PDF Info: {info}")

    # 提取文本
    chunks = extractor.extract_text()

    print(f"\nTotal chunks: {len(chunks)}")
    if chunks:
        print(f"\nFirst chunk preview:")
        print(chunks[0]['content'][:200])
        print(f"\nMetadata: {chunks[0]['metadata']}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor.py <pdf_file>")
        sys.exit(1)

    test_extraction(sys.argv[1])
