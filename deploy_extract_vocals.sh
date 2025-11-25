#!/bin/bash
# DeepFilterNet + Denoiser 自动化部署脚本
# 用于服务器374
# 部署路径: /root/autodl-tmp/extract-vocals

set -e  # 遇到错误立即退出

echo "============================================================"
echo "DeepFilterNet + Denoiser 自动化部署脚本"
echo "============================================================"
echo ""

# 配置
DEPLOY_DIR="/root/autodl-tmp/extract-vocals"
MODEL_DIR="$DEPLOY_DIR/models/DeepFilterNet3"

# 步骤 1: 检查环境
echo "步骤 1: 检查环境..."
cd "$DEPLOY_DIR" || mkdir -p "$DEPLOY_DIR" && cd "$DEPLOY_DIR"
pwd

echo "检查 Python 版本..."
python3 --version

echo "检查 GPU 信息..."
nvidia-smi || echo "警告: nvidia-smi 不可用"

echo ""

# 步骤 2: 创建虚拟环境
echo "步骤 2: 创建虚拟环境..."
if [ -d "venv" ]; then
    echo "虚拟环境已存在，跳过创建"
else
    python3 -m venv venv
    echo "✅ 虚拟环境创建成功"
fi

# 激活虚拟环境
source venv/bin/activate
echo "✅ 虚拟环境已激活"
which python3
echo ""

# 步骤 3: 安装 PyTorch
echo "步骤 3: 安装 PyTorch 2.5.0..."
pip uninstall -y torch torchvision torchaudio 2>/dev/null || true
pip install torch==2.5.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
echo "✅ PyTorch 安装完成"

# 验证 PyTorch
python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')" || {
    echo "❌ PyTorch 验证失败"
    exit 1
}
echo ""

# 步骤 4: 安装基础依赖
echo "步骤 4: 安装基础依赖..."
pip install soundfile librosa numpy scipy
echo "✅ 基础依赖安装完成"
echo ""

# 步骤 5: 安装 DeepFilterNet
echo "步骤 5: 安装 DeepFilterNet..."
pip install deepfilternet
echo "✅ DeepFilterNet 安装完成"

# 验证 DeepFilterNet
python3 -c "import df.enhance; print('DeepFilterNet 导入成功')" || {
    echo "❌ DeepFilterNet 验证失败"
    exit 1
}
echo ""

# 步骤 6: 安装 Denoiser
echo "步骤 6: 安装 Denoiser..."
pip install denoiser
echo "✅ Denoiser 安装完成"

# 验证 Denoiser
python3 -c "from denoiser import pretrained; print('Denoiser 导入成功')" || {
    echo "❌ Denoiser 验证失败"
    exit 1
}
echo ""

# 步骤 7: 下载模型
echo "步骤 7: 下载 DeepFilterNet3 模型..."
mkdir -p "$MODEL_DIR"
cd "$MODEL_DIR"

if [ -f "config.ini" ]; then
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
    echo "✅ 模型下载并解压完成"
fi

cd "$DEPLOY_DIR"
echo ""

# 步骤 8: 测试模型加载
echo "步骤 8: 测试模型加载..."
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
except Exception as e:
    print(f"❌ 模型加载失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYEOF

echo ""

# 步骤 9: 创建处理脚本
echo "步骤 9: 创建处理脚本..."
cd "$DEPLOY_DIR"

# 这里需要从之前创建的文档中复制 process_audio.py 的内容
# 由于脚本较长，建议手动创建或使用其他方式

echo "✅ 部署脚本执行完成！"
echo ""
echo "============================================================"
echo "部署完成"
echo "============================================================"
echo "部署路径: $DEPLOY_DIR"
echo "模型路径: $MODEL_DIR"
echo ""
echo "下一步:"
echo "1. 创建 process_audio.py 脚本"
echo "2. 创建 audio_processor_service.py 脚本"
echo "3. 运行环境检查验证"
echo "============================================================"


