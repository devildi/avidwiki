import os
import shutil
import random
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def prepare_dataset():
    """
    自动将 data/camera/body_dataset/labeled/ 里的分类标注数据
    随机划分为 80% 训练集 (train) 和 20% 验证集 (val)，并输出到 split 目录中。
    """
    base_dir = Path("data/camera/body_dataset")
    labeled_dir = base_dir / "labeled"
    split_dir = base_dir / "split"
    
    if not labeled_dir.exists():
        logger.error(f"标注数据文件夹不存在: {labeled_dir.resolve()}")
        logger.error("请先创建对应的类别目录（如: data/camera/body_dataset/labeled/吴迪/）并将收集裁剪的图片分类放入其中！")
        return False
        
    # 清理并重新创建划分目录
    if split_dir.exists():
        shutil.rmtree(split_dir)
        
    train_dir = split_dir / "train"
    val_dir = split_dir / "val"
    
    categories = [d for d in labeled_dir.iterdir() if d.is_dir()]
    if not categories:
        logger.error(f"在 {labeled_dir.resolve()} 下未找到任何类别子目录！")
        return False
        
    logger.info(f"检测到标注类别: {[c.name for c in categories]}")
    
    total_train = 0
    total_val = 0
    
    for cat in categories:
        cat_name = cat.name
        # 英文命名检查以防 YOLO 训练日志路径乱码，可使用拼音或英文命名
        images = [f for f in cat.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png']]
        
        if len(images) < 5:
            logger.warning(f"类别 '{cat_name}' 的样本数过少 ({len(images)} 张)，训练可能不稳定，建议每个类别至少准备 15-20 张图！")
            
        random.shuffle(images)
        if len(images) == 1:
            train_images = images
            val_images = images
        else:
            split_idx = int(len(images) * 0.8)
            # 确保训练集和验证集都至少包含 1 张图片，防止 YOLO/torchvision 报空目录错误
            if split_idx == 0:
                split_idx = 1
            elif split_idx == len(images):
                split_idx = len(images) - 1
            train_images = images[:split_idx]
            val_images = images[split_idx:]
        
        cat_train_dir = train_dir / cat_name
        cat_val_dir = val_dir / cat_name
        cat_train_dir.mkdir(parents=True, exist_ok=True)
        cat_val_dir.mkdir(parents=True, exist_ok=True)
        
        for img in train_images:
            shutil.copy(img, cat_train_dir / img.name)
        for img in val_images:
            shutil.copy(img, cat_val_dir / img.name)
            
        total_train += len(train_images)
        total_val += len(val_images)
        logger.info(f"类别 '{cat_name}': 划分 {len(train_images)} 张至训练集，{len(val_images)} 张至验证集。")
        
    logger.info(f"数据集划分完成！总训练样本: {total_train} 张，总验证样本: {total_val} 张。")
    return True

def train_model():
    """使用 Ultralytics YOLOv8-Cls 训练体态分类模型"""
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("未找到 ultralytics 依赖包，请先在终端运行 'pip install ultralytics' 安装！")
        return
        
    split_dir = Path("data/camera/body_dataset/split")
    if not split_dir.exists():
        logger.error("未找到划分数据集，请确认已成功准备数据！")
        return
        
    logger.info("开始加载预训练模型 yolov8n-cls.pt ...")
    model = YOLO("yolov8n-cls.pt")
    
    # 硬件加速检测：对于 macOS 统一使用 CPU 训练，防止 Apple Silicon 的 MPS autocast 报错以及老款 Intel Mac (AMD GPU) 的 Metal 命令通道崩溃问题。
    # 对于带有 NVIDIA 显卡的 Windows/Linux 系统，继续支持 CUDA 加速。
    import torch
    device = "cpu"
    if torch.cuda.is_available():
        device = "0"
        logger.info("检测到 NVIDIA CUDA 显卡可用，将使用 GPU 进行训练。")
    else:
        logger.info("将使用 CPU 进行训练（小分类模型在 CPU 下训练非常稳定且快速，耗时约 30 秒）。")
        
    logger.info("🚀 开始启动 YOLOv8-Cls 训练...")
    # epochs=80: 增加迭代周期以在小样本数据集上充分收敛，防止训练不足
    # imgsz=224: 使用 ImageNet 默认分辨率 224x224 像素，保留人脸细节及衣着纹理，显著提升准确率
    model.train(
        data=str(split_dir.resolve()),
        epochs=80,
        imgsz=224,
        device=device,
        amp=False,  # 禁用混合精度训练以解决 macOS Apple Silicon MPS autocast 报错问题
        project="runs/classify",
        name="person_body_train",
        exist_ok=True
    )
    
    # 查找并保存训练好的最佳权重 (动态适配 YOLOv8 在不同版本下对 project 和 name 的路径拼接规则差异)
    best_weights = None
    candidate_paths = [
        Path("runs/classify/runs/classify/person_body_train/weights/best.pt"),
        Path("runs/classify/person_body_train/weights/best.pt"),
        Path("runs/person_body_train/weights/best.pt"),
    ]
    for cp in candidate_paths:
        if cp.exists():
            best_weights = cp
            break
            
    # 如果候选路径均不存在，进行递归搜索兜底
    if not best_weights:
        runs_dir = Path("runs")
        if runs_dir.exists():
            found_paths = list(runs_dir.glob("**/person_body_train/weights/best.pt"))
            if found_paths:
                best_weights = found_paths[0]

    if best_weights and best_weights.exists():
        dest_model_dir = Path("data/camera/models")
        dest_model_dir.mkdir(parents=True, exist_ok=True)
        dest_model_path = dest_model_dir / "body_classifier.pt"
        
        shutil.copy(best_weights, dest_model_path)
        logger.info(f"🎉 训练成功完成！")
        logger.info(f"最佳模型权重已保存至: {dest_model_path.resolve()}")
        logger.info("检测管道将会在 8 秒内自动检测并载入该分类器，开始进行体态兜底识别！")
        
        # 移除临时训练工程运行日志目录，保持项目整洁
        try:
            shutil.rmtree("runs")
        except Exception:
            pass
    else:
        logger.error("未在默认输出路径中找到训练模型权重，请检查 Ultralytics 训练日志！")

if __name__ == "__main__":
    if prepare_dataset():
        train_model()
