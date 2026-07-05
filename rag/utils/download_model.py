"""
独立脚本：从 Hugging Face 镜像下载指定模型到本地文件夹
运行一次即可，后续无需联网
"""

import os
import sys

# 设置镜像（必须）
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

def download_model(model_id: str, save_dir: str):
    """
    使用 huggingface_hub 下载完整模型（包括 LFS 大文件）
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("请先安装 huggingface_hub: pip install huggingface_hub")
        sys.exit(1)

    print(f"开始下载模型: {model_id}")
    print(f"保存路径: {save_dir}")
    print("大文件下载可能较慢，请耐心等待...\n")

    # 下载所有文件到本地目录
    snapshot_download(
        repo_id=model_id,
        local_dir=save_dir,
        local_dir_use_symlinks=False,   # Windows 下避免软链接问题
        resume_download=True,            # 支持断点续传
        max_workers=4,                  # 并发下载数
    )

    print("\n✅ 模型下载完成！")

if __name__ == "__main__":
    # 要下载的模型
    MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # 保存到当前目录下的 models 文件夹
    SAVE_DIR = "./models/paraphrase-multilingual-MiniLM-L12-v2"

    # 确保保存目录存在
    os.makedirs(SAVE_DIR, exist_ok=True)

    download_model(MODEL_ID, SAVE_DIR)