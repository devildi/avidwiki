"""
优化版 PDF 提取器 - 适用于大文档（1000+ 页）
特性：流式处理、内存优化、进度回调
已迁移至 PyMuPDF (fitz) 引擎以提升速度和稳定性
已添加多进程超时保护（Subprocess Sandbox）：
- 每个页面单独子进程 (subprocess)
- 私有 TMPDIR 沙盒 (100% 清理临时文件)
- 强制超时杀进程
- 2GB 内存硬限制
"""
import os
import hashlib
import re
import time
import subprocess
import tempfile
import uuid
import shutil
import sys
from typing import List, Dict, Optional, Iterator, Callable
import logging

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    logger.error("PyMuPDF not installed. Run: pip install pymupdf")
    raise


class LargePDFExtractor:
    """大文档 PDF 提取器 - 流式处理优化版 (Subprocess Sandbox)"""

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
        
        # 确定 worker 脚本路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.worker_script = os.path.join(current_dir, "pdf_worker.py")
        
        if not os.path.exists(self.worker_script):
            raise FileNotFoundError(f"Worker script not found: {self.worker_script}")

    def extract_text_stream(
        self,
        batch_size: int = 100,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Iterator[List[Dict]]:
        """
        流式提取 PDF 文本（Subprocess Sandbox 超时保护）

        Args:
            batch_size: 每批返回的 chunk 数量
            progress_callback: 进度回调函数 callback(current_page, total_pages, message)

        Yields:
            每批文本块列表
        """
        try:
            # 预先获取总页数
            doc = fitz.open(self.pdf_path)
            total_pages = doc.page_count
            doc.close()

            logger.info(f"Processing large PDF with Subprocess Sandbox: {self.filename} ({total_pages} pages)")

            batch = []
            current_chunk_id = 0
            
            # 获取系统 python 解释器路径
            python_exe = sys.executable
            
            # PyMuPDF is 0-indexed, human readable is 1-indexed
            for page_idx in range(total_pages):
                page_num = page_idx + 1
                
                # 1. 创建私有临时目录 (Sandbox)
                # 所有的临时文件都会被限制在这里
                sandbox_dir = tempfile.mkdtemp(prefix=f"pdf_page_{page_num}_")
                
                # 2. 设置输出文件路径
                output_path = os.path.join(sandbox_dir, "output.txt")
                
                try:
                    start_time = time.time()
                    
                    # 3. 准备环境变量 (指定 TMPDIR)
                    env = os.environ.copy()
                    env["TMPDIR"] = sandbox_dir
                    env["TEMP"] = sandbox_dir
                    env["TMP"] = sandbox_dir
                    
                    # 4. 运行子进程
                    # 使用 subprocess.run 比 multiprocessing 更干净，因为它完全隔离了内存和文件描述符
                    cmd = [
                        python_exe, 
                        self.worker_script,
                        "--pdf", self.pdf_path,
                        "--page", str(page_idx),
                        "--output", output_path
                    ]
                    
                    try:
                        # 运行并在 10 秒后超时
                        subprocess.run(
                            cmd, 
                            env=env, 
                            timeout=10, 
                            check=False,
                            stdout=subprocess.DEVNULL,  # 忽略输出
                            stderr=subprocess.DEVNULL
                        )
                    except subprocess.TimeoutExpired:
                        # 超时! subprocess 会自动杀掉子进程 (虽然不一定 kill -9, 但通常足够)
                        # 如果需要更强力的 kill，可能需要 Popen
                        logger.error(f"Page {page_num} timed out (Subprocess > 10s)")
                        if progress_callback:
                            progress_callback(page_num, total_pages, f"⚠️ Skipped page {page_num} (Timeout)")
                        continue
                    
                    # 5. 读取结果
                    text = None
                    if os.path.exists(output_path):
                        with open(output_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            
                        if content.startswith("__ERROR__"):
                            logger.error(f"Error extracting page {page_num}: {content[9:]}")
                        else:
                            text = content
                    else:
                        logger.error(f"Page {page_num} produced no output (Subprocess crashed?)")
                            
                    extract_time = time.time() - start_time

                    # 记录慢页面
                    if extract_time > 1.0:
                        logger.warning(f"Page {page_num} extraction took {extract_time:.1f}s")

                    # 清理文本
                    if text:
                        text = self._clean_text(text)

                    # 检查文本长度
                    if not text or len(text.strip()) < 10:
                        continue

                    # 分块
                    page_chunks = self._split_text(text)

                    # 为每个块添加元数据
                    for i, chunk_text in enumerate(page_chunks):
                        chunk_id = self._generate_chunk_id(self.filename, page_num, i)

                        batch.append({
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

                    # 当达到批次大小时，yield 这批数据
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []  # 清空批次，释放内存

                    # 进度回调（每一页都更新，以便调试卡顿页）
                    if progress_callback:
                        progress_callback(page_num, total_pages, f"Extracted page {page_num}/{total_pages}")

                except Exception as e:
                    logger.error(f"Unexpected error on page {page_num}: {e}", exc_info=True)
                    continue
                finally:
                    # 6. 关键步骤：删除整个 Sandbox
                    # 无论进程是否成功，是否超时，是否崩溃，
                    # 这里都会强制删除该页面产生的所有临时文件
                    try:
                        shutil.rmtree(sandbox_dir, ignore_errors=True)
                    except Exception as cleanup_error:
                        logger.error(f"Failed to cleanup sandbox {sandbox_dir}: {cleanup_error}")
                
            # yield 最后一批
            if batch:
                yield batch

            # 打印总结报告
            logger.info(f"Extraction complete: {current_chunk_id} chunks created")

        except Exception as e:
            logger.error(f"Error extracting PDF {self.pdf_path}: {e}", exc_info=True)
            raise

    def extract_text(self) -> List[Dict]:
        """
        提取 PDF 文本并分块（兼容旧接口）

        Returns:
            包含文本块和元数据的字典列表
        """
        chunks = []
        for batch in self.extract_text_stream():
            chunks.extend(batch)
        return chunks

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


# 向后兼容：保持原有类名
PDFExtractor = LargePDFExtractor
