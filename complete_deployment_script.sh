#!/bin/bash
# DeepFilterNet + Denoiser 完整部署脚本
# 服务器: 374
# 部署路径: /root/autodl-tmp/extract-vocals
# 日期: 2025-11-24

set -e  # 遇到错误立即退出

echo "============================================================"
echo "DeepFilterNet + Denoiser 完整部署脚本"
echo "服务器: 374"
echo "============================================================"
echo ""

# ==================== 配置 ====================
DEPLOY_DIR="/root/autodl-tmp/extract-vocals"
MODEL_DIR="$DEPLOY_DIR/models/DeepFilterNet3"
VENV_PYTHON="$DEPLOY_DIR/venv/bin/python3"

# ==================== 步骤 1: 检查环境 ====================
echo "[1/13] 检查环境..."
cd "$DEPLOY_DIR" 2>/dev/null || mkdir -p "$DEPLOY_DIR" && cd "$DEPLOY_DIR"
echo "当前目录: $(pwd)"

echo "Python 版本:"
python3 --version

echo "GPU 信息:"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || echo "警告: nvidia-smi 不可用"

echo ""

# ==================== 步骤 2: 创建虚拟环境 ====================
echo "[2/13] 创建虚拟环境..."
if [ -d "venv" ]; then
    echo "虚拟环境已存在，跳过创建"
else
    python3 -m venv venv
    echo "✅ 虚拟环境创建成功"
fi

source venv/bin/activate
echo "✅ 虚拟环境已激活: $(which python3)"
echo ""

# ==================== 步骤 3: 安装 PyTorch ====================
echo "[3/13] 安装 PyTorch 2.5.0..."
pip uninstall -y torch torchvision torchaudio 2>/dev/null || true
pip install torch==2.5.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
echo "✅ PyTorch 安装完成"

echo "验证 PyTorch..."
python3 << 'PYEOF'
import torch
print(f"PyTorch 版本: {torch.__version__}")
print(f"CUDA 可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"计算能力: {torch.cuda.get_device_capability(0)}")
    # 测试 GPU 计算
    x = torch.randn(100, 100).cuda()
    y = torch.randn(100, 100).cuda()
    z = torch.matmul(x, y)
    print(f"GPU 计算测试: SUCCESS")
PYEOF
echo ""

# ==================== 步骤 4: 安装基础依赖 ====================
echo "[4/13] 安装基础依赖..."
pip install soundfile librosa numpy scipy
echo "✅ 基础依赖安装完成"
echo ""

# ==================== 步骤 5: 安装 DeepFilterNet ====================
echo "[5/13] 安装 DeepFilterNet..."
pip install deepfilternet
echo "✅ DeepFilterNet 安装完成"

echo "验证 DeepFilterNet..."
python3 -c "import df.enhance; print('✅ DeepFilterNet 导入成功')" || {
    echo "❌ DeepFilterNet 验证失败"
    exit 1
}
echo ""

# ==================== 步骤 6: 安装 Denoiser ====================
echo "[6/13] 安装 Denoiser..."
pip install denoiser
echo "✅ Denoiser 安装完成"

echo "验证 Denoiser..."
python3 -c "from denoiser import pretrained; print('✅ Denoiser 导入成功')" || {
    echo "❌ Denoiser 验证失败"
    exit 1
}
echo ""

# ==================== 步骤 7: 下载模型 ====================
echo "[7/13] 下载 DeepFilterNet3 模型..."
mkdir -p "$MODEL_DIR"
cd "$MODEL_DIR"

if [ -f "config.ini" ] && [ -d "checkpoints" ]; then
    echo "模型已存在，跳过下载"
else
    echo "下载模型文件..."
    wget --progress=bar:force -O DeepFilterNet3.zip "https://github.com/Rikorose/DeepFilterNet/raw/main/models/DeepFilterNet3.zip" || {
        echo "❌ 模型下载失败，请检查网络连接"
        exit 1
    }
    
    echo "解压模型文件..."
    unzip -q DeepFilterNet3.zip
    rm -f DeepFilterNet3.zip
    
    if [ -f "config.ini" ]; then
        echo "✅ 模型下载并解压完成"
    else
        echo "❌ 模型解压失败"
        exit 1
    fi
fi

cd "$DEPLOY_DIR"
echo ""

# ==================== 步骤 8: 测试模型加载 ====================
echo "[8/13] 测试 DeepFilterNet3 模型加载..."
python3 << 'PYEOF'
from df import init_df
from df.modules import get_device

print("测试 DeepFilterNet3 模型加载...")
try:
    model_path = "/root/autodl-tmp/extract-vocals/models/DeepFilterNet3"
    model, df_state, suffix = init_df(
        model_base_dir=model_path,
        post_filter=True,
        log_level="INFO",
        config_allow_defaults=True,
    )
    device = get_device()
    model = model.to(device)
    print(f"✅ DeepFilterNet3 模型加载成功！")
    print(f"   设备: {device}")
    print(f"   模型后缀: {suffix}")
except Exception as e:
    print(f"❌ 模型加载失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYEOF
echo ""

# ==================== 步骤 9: 测试 Denoiser 模型 ====================
echo "[9/13] 测试 Denoiser 模型加载..."
python3 << 'PYEOF'
from denoiser import pretrained
import torch

print("测试 Denoiser 模型加载...")
try:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = pretrained.dns64(pretrained=True)
    model = model.to(device)
    print(f"✅ Denoiser 模型加载成功！")
    print(f"   设备: {device}")
except Exception as e:
    print(f"❌ Denoiser 模型加载失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYEOF
echo ""

# ==================== 步骤 10: 创建处理脚本 ====================
echo "[10/13] 创建 process_audio.py 脚本..."
cd "$DEPLOY_DIR"

cat > process_audio.py << 'SCRIPT_EOF'
#!/usr/bin/env python3
"""
方案 A: DeepFilterNet -> Denoiser 两步处理流程
第一步: DeepFilterNet (主攻降噪)
第二步: Denoiser (主攻去混响)
"""

import sys
import os
import argparse
import torch
import soundfile as sf
import numpy as np
import tempfile

# 导入 DeepFilterNet
try:
    from df import init_df, enhance as df_enhance
    from df.io import load_audio, save_audio, resample
    from df.modules import get_device
    DEEPFILTERNET_AVAILABLE = True
except ImportError as e:
    print(f"错误: DeepFilterNet 导入失败: {e}")
    DEEPFILTERNET_AVAILABLE = False

# 导入 Denoiser
try:
    from denoiser import pretrained
    DENOISER_AVAILABLE = True
except ImportError as e:
    print(f"错误: Denoiser 导入失败: {e}")
    DENOISER_AVAILABLE = False


def process_with_deepfilternet(input_path, output_path, model=None, df_state=None, device=None):
    """第一步: 使用 DeepFilterNet 进行降噪"""
    if not DEEPFILTERNET_AVAILABLE:
        raise ImportError("DeepFilterNet 不可用")
    
    print("=" * 60)
    print("第一步: DeepFilterNet (主攻降噪)")
    print("=" * 60)
    
    if device is None:
        device = get_device()
    
    if model is None or df_state is None:
        print("加载 DeepFilterNet 模型...")
        model_path = "/root/autodl-tmp/extract-vocals/models/DeepFilterNet3"
        model, df_state, suffix = init_df(
            model_base_dir=model_path,
            post_filter=True,
            log_level="INFO",
            config_allow_defaults=True,
        )
        model = model.to(device)
        print(f"模型已加载到设备: {device}")
    
    print(f"加载音频文件: {input_path}")
    audio, meta = load_audio(input_path, sr=48000)
    audio = audio.to(device)
    
    print("正在进行降噪处理...")
    with torch.no_grad():
        enhanced = df_enhance(
            model, 
            df_state, 
            audio, 
            pad=True,
            atten_lim_db=None
        )
    
    print(f"保存第一步处理结果: {output_path}")
    save_audio(output_path, enhanced, sr=48000)
    print("第一步完成！\n")
    
    return enhanced, model, df_state, device


def process_with_denoiser(input_path, output_path, model=None, device=None):
    """第二步: 使用 Denoiser 进行去混响"""
    if not DENOISER_AVAILABLE:
        raise ImportError("Denoiser 不可用")
    
    print("=" * 60)
    print("第二步: Denoiser (主攻去混响)")
    print("=" * 60)
    
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    if model is None:
        print("加载 Denoiser 模型...")
        model = pretrained.dns64(pretrained=True)
        model = model.to(device)
        print(f"模型已加载到设备: {device}")
    
    print(f"加载音频文件: {input_path}")
    wav, orig_sr = sf.read(input_path)
    
    if len(wav.shape) > 1:
        wav = wav[:, 0]
    
    wav_tensor = torch.from_numpy(wav).float()
    
    target_sr = 16000
    if orig_sr != target_sr:
        print(f"重采样: {orig_sr} Hz -> {target_sr} Hz")
        from torchaudio.transforms import Resample
        resampler = Resample(orig_sr, target_sr)
        wav_tensor = resampler(wav_tensor)
    
    if wav_tensor.dim() == 1:
        wav_tensor = wav_tensor.unsqueeze(0)
    
    wav_tensor = wav_tensor.to(device)
    
    print("正在进行去混响处理...")
    with torch.no_grad():
        enhanced = model(wav_tensor[None])[0]
    
    enhanced_np = enhanced.cpu().numpy()
    if enhanced_np.shape[0] == 1:
        enhanced_np = enhanced_np[0]
    
    print(f"保存最终处理结果: {output_path}")
    sf.write(output_path, enhanced_np, target_sr)
    print("第二步完成！\n")
    
    return enhanced_np, model, device


def process_audio_two_stage(input_path, output_path, device=None):
    """两步处理流程: DeepFilterNet -> Denoiser"""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    print("=" * 60)
    print("方案 A: DeepFilterNet -> Denoiser 两步处理流程")
    print("=" * 60)
    print(f"输入文件: {input_path}")
    print(f"输出文件: {output_path}")
    print(f"使用设备: {device}")
    print()
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"输入文件不存在: {input_path}")
    
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"df_temp_{os.path.basename(input_path)}")
    
    try:
        enhanced_df, model_df, df_state, device = process_with_deepfilternet(
            input_path, temp_path, device=device
        )
        
        enhanced_final, model_denoiser, device = process_with_denoiser(
            temp_path, output_path, device=device
        )
        
        print("=" * 60)
        print("处理完成！")
        print("=" * 60)
        print(f"最终结果已保存到: {output_path}")
        
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print(f"\n已清理临时文件: {temp_path}")


def main():
    parser = argparse.ArgumentParser(
        description="方案 A: DeepFilterNet -> Denoiser 两步音频处理流程"
    )
    parser.add_argument("input", type=str, help="输入音频文件路径")
    parser.add_argument("output", type=str, help="输出音频文件路径")
    parser.add_argument("--device", type=str, default=None, 
                       help="设备 (cuda/cpu)，默认自动选择")
    
    args = parser.parse_args()
    
    if args.device:
        device = torch.device(args.device)
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    try:
        process_audio_two_stage(args.input, args.output, device=device)
        return 0
    except Exception as e:
        print(f"\n错误: 处理过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
SCRIPT_EOF

chmod +x process_audio.py
echo "✅ process_audio.py 创建完成"
echo ""

# ==================== 步骤 11: 创建服务脚本 ====================
echo "[11/13] 创建 audio_processor_service.py 脚本..."
cat > audio_processor_service.py << 'SERVICE_EOF'
#!/usr/bin/env python3
"""
音频处理服务脚本
可以被其他项目调用，使用 DeepFilterNet -> Denoiser 两步处理流程
"""

import sys
import os
import argparse
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(SCRIPT_DIR, "venv", "bin", "python3")
PROCESS_SCRIPT = os.path.join(SCRIPT_DIR, "process_audio.py")


def process_audio(input_path, output_path=None, device=None):
    """处理音频文件"""
    if not os.path.exists(input_path):
        logger.error(f"输入文件不存在: {input_path}")
        return None
    
    if output_path is None:
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_dir = os.path.dirname(input_path)
        output_path = os.path.join(output_dir, f"{base_name}_clean.wav")
    
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    cmd = [VENV_PYTHON, PROCESS_SCRIPT, input_path, output_path]
    if device:
        cmd.extend(["--device", device])
    
    logger.info(f"开始处理音频: {input_path} -> {output_path}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            if os.path.exists(output_path):
                logger.info(f"音频处理成功: {output_path}")
                return output_path
            else:
                logger.error(f"处理完成但输出文件不存在: {output_path}")
                return None
        else:
            logger.error(f"音频处理失败，返回码: {result.returncode}")
            logger.error(f"错误输出: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error("音频处理超时（超过5分钟）")
        return None
    except Exception as e:
        logger.error(f"执行处理脚本时出错: {str(e)}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="音频处理服务 - DeepFilterNet -> Denoiser 两步处理"
    )
    parser.add_argument("input", type=str, help="输入音频文件路径")
    parser.add_argument("output", type=str, nargs="?", default=None, 
                       help="输出音频文件路径（可选）")
    parser.add_argument("--device", type=str, default=None,
                       help="设备 (cuda/cpu)，默认自动选择")
    
    args = parser.parse_args()
    
    result = process_audio(args.input, args.output, args.device)
    
    if result:
        print(result)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
SERVICE_EOF

chmod +x audio_processor_service.py
echo "✅ audio_processor_service.py 创建完成"
echo ""

# ==================== 步骤 12: 环境检查 ====================
echo "[12/13] 最终环境检查..."
python3 << 'PYEOF'
import sys
print("=" * 60)
print("环境检查")
print("=" * 60)

try:
    import torch
    print(f"✅ PyTorch: {torch.__version__}")
    print(f"   CUDA 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
except Exception as e:
    print(f"❌ PyTorch: {e}")

try:
    import df.enhance
    print("✅ DeepFilterNet: 可用")
except Exception as e:
    print(f"❌ DeepFilterNet: {e}")

try:
    from denoiser import pretrained
    print("✅ Denoiser: 可用")
except Exception as e:
    print(f"❌ Denoiser: {e}")

try:
    import soundfile
    print("✅ soundfile: 可用")
except Exception as e:
    print(f"❌ soundfile: {e}")

try:
    import librosa
    print("✅ librosa: 可用")
except Exception as e:
    print(f"❌ librosa: {e}")

print("=" * 60)
print("环境检查完成")
print("=" * 60)
PYEOF
echo ""

# ==================== 步骤 13: 验证脚本 ====================
echo "[13/13] 验证脚本..."
if [ -f "process_audio.py" ] && [ -f "audio_processor_service.py" ]; then
    echo "✅ 所有脚本创建成功"
    echo ""
    echo "脚本列表:"
    ls -lh process_audio.py audio_processor_service.py
else
    echo "❌ 脚本创建失败"
    exit 1
fi

echo ""
echo "============================================================"
echo "部署完成！"
echo "============================================================"
echo "部署路径: $DEPLOY_DIR"
echo "模型路径: $MODEL_DIR"
echo ""
echo "使用方法:"
echo "  source venv/bin/activate"
echo "  python3 process_audio.py input.wav output.wav"
echo ""
echo "服务调用:"
echo "  python3 audio_processor_service.py input.wav output.wav"
echo "============================================================"


