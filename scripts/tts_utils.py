"""
TTS工具模块
包含与TTS相关的通用工具函数
"""

try:
    from indextts.infer_v2 import IndexTTS2
    TTS_AVAILABLE = True
except ImportError:
    print("警告: 未找到 indextts 包，TTS 功能将不可用")
    IndexTTS2 = None
    TTS_AVAILABLE = False


def initialize_tts_model(cfg_path=None, model_dir=None):
    """
    初始化TTS模型
    
    Args:
        cfg_path (str, optional): 配置文件路径
        model_dir (str, optional): 模型目录路径
        
    Returns:
        IndexTTS2: 初始化的TTS模型实例，如果初始化失败则返回None
    """
    if not TTS_AVAILABLE:
        print("错误: TTS 功能不可用，请确保已正确安装 indextts 包")
        return None
        
    # 使用默认路径，如果未提供参数
    if cfg_path is None:
        cfg_path = "/root/autodl-tmp/index-tts/checkpoints/config.yaml"
    if model_dir is None:
        model_dir = "/root/autodl-tmp/index-tts/checkpoints"
        
    try:
        tts = IndexTTS2(
            cfg_path=cfg_path,
            model_dir=model_dir,
            use_fp16=False,
            use_cuda_kernel=False,
            use_deepspeed=False,
        )
        return tts
    except Exception as e:
        print(f"初始化TTS模型时出错: {e}")
        return None