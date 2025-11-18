import os
from huggingface_hub import hf_hub_download

# 设置环境变量确保离线模式和使用镜像源
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_DATASETS_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

# 创建缓存目录
cache_dir = "/root/autodl-tmp/index-tts/checkpoints/hf_cache"
os.makedirs(cache_dir, exist_ok=True)

print("开始下载必要的模型文件...")

try:
    # 下载w2v-bert-2.0模型文件
    print("下载facebook/w2v-bert-2.0模型...")
    hf_hub_download(
        repo_id="facebook/w2v-bert-2.0",
        filename="config.json",
        cache_dir=cache_dir
    )
    print("成功下载facebook/w2v-bert-2.0模型")
except Exception as e:
    print(f"下载facebook/w2v-bert-2.0模型时出错: {e}")

try:
    # 下载amphion/MaskGCT模型文件
    print("下载amphion/MaskGCT模型...")
    hf_hub_download(
        repo_id="amphion/MaskGCT",
        filename="semantic_codec/model.safetensors",
        cache_dir=cache_dir
    )
    print("成功下载amphion/MaskGCT模型")
except Exception as e:
    print(f"下载amphion/MaskGCT模型时出错: {e}")

try:
    # 下载funasr/campplus模型文件
    print("下载funasr/campplus模型...")
    hf_hub_download(
        repo_id="funasr/campplus",
        filename="campplus_cn_common.bin",
        cache_dir=cache_dir
    )
    print("成功下载funasr/campplus模型")
except Exception as e:
    print(f"下载funasr/campplus模型时出错: {e}")

print("模型下载完成")
