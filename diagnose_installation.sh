#!/bin/bash
# 诊断脚本：检查DeepFilterNet + Denoiser安装失败的原因

echo "============================================================"
echo "DeepFilterNet + Denoiser 安装诊断脚本"
echo "============================================================"
echo ""

DEPLOY_DIR="/root/autodl-tmp/extract-vocals"
LOG_FILE="$DEPLOY_DIR/installation_diagnosis.log"

# 创建日志文件
mkdir -p "$DEPLOY_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "诊断开始时间: $(date)"
echo ""

# 1. 检查系统信息
echo "=== 1. 系统信息 ==="
echo "操作系统: $(uname -a)"
echo "Python版本: $(python3 --version 2>&1 || echo '未安装')"
echo "pip版本: $(pip3 --version 2>&1 || echo '未安装')"
echo ""

# 2. 检查GPU
echo "=== 2. GPU信息 ==="
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi
else
    echo "❌ nvidia-smi 不可用"
fi
echo ""

# 3. 检查CUDA
echo "=== 3. CUDA信息 ==="
if command -v nvcc &> /dev/null; then
    nvcc --version
else
    echo "❌ nvcc 不可用"
fi
echo ""

# 4. 检查虚拟环境
echo "=== 4. 虚拟环境检查 ==="
if [ -d "$DEPLOY_DIR/venv" ]; then
    echo "✅ 虚拟环境存在"
    if [ -f "$DEPLOY_DIR/venv/bin/python3" ]; then
        echo "✅ Python可执行文件存在"
        echo "Python版本: $($DEPLOY_DIR/venv/bin/python3 --version)"
    else
        echo "❌ Python可执行文件不存在"
    fi
else
    echo "❌ 虚拟环境不存在"
fi
echo ""

# 5. 检查已安装的包
echo "=== 5. 已安装的Python包 ==="
if [ -f "$DEPLOY_DIR/venv/bin/pip" ]; then
    source "$DEPLOY_DIR/venv/bin/activate"
    echo "PyTorch: $(pip show torch 2>/dev/null | grep Version || echo '未安装')"
    echo "DeepFilterNet: $(pip show deepfilternet 2>/dev/null | grep Version || echo '未安装')"
    echo "Denoiser: $(pip show denoiser 2>/dev/null | grep Version || echo '未安装')"
    echo "soundfile: $(pip show soundfile 2>/dev/null | grep Version || echo '未安装')"
    echo "librosa: $(pip show librosa 2>/dev/null | grep Version || echo '未安装')"
else
    echo "❌ pip不可用"
fi
echo ""

# 6. 检查模型文件
echo "=== 6. 模型文件检查 ==="
MODEL_DIR="$DEPLOY_DIR/models/DeepFilterNet3"
if [ -d "$MODEL_DIR" ]; then
    echo "✅ 模型目录存在"
    if [ -f "$MODEL_DIR/config.ini" ]; then
        echo "✅ config.ini 存在"
    else
        echo "❌ config.ini 不存在"
    fi
    if [ -d "$MODEL_DIR/checkpoints" ]; then
        echo "✅ checkpoints 目录存在"
        echo "checkpoints文件数: $(find $MODEL_DIR/checkpoints -type f | wc -l)"
    else
        echo "❌ checkpoints 目录不存在"
    fi
else
    echo "❌ 模型目录不存在"
fi
echo ""

# 7. 测试导入
echo "=== 7. Python模块导入测试 ==="
if [ -f "$DEPLOY_DIR/venv/bin/python3" ]; then
    source "$DEPLOY_DIR/venv/bin/activate"
    
    echo "测试PyTorch导入..."
    python3 -c "import torch; print(f'✅ PyTorch {torch.__version__}')" 2>&1 || echo "❌ PyTorch导入失败"
    
    echo "测试DeepFilterNet导入..."
    python3 -c "import df.enhance; print('✅ DeepFilterNet')" 2>&1 || echo "❌ DeepFilterNet导入失败"
    
    echo "测试Denoiser导入..."
    python3 -c "from denoiser import pretrained; print('✅ Denoiser')" 2>&1 || echo "❌ Denoiser导入失败"
else
    echo "❌ 无法测试导入（虚拟环境不存在）"
fi
echo ""

# 8. 检查网络连接
echo "=== 8. 网络连接测试 ==="
echo "测试GitHub连接..."
curl -I https://github.com 2>&1 | head -1 || echo "❌ GitHub连接失败"
echo "测试PyPI连接..."
curl -I https://pypi.org 2>&1 | head -1 || echo "❌ PyPI连接失败"
echo ""

# 9. 检查磁盘空间
echo "=== 9. 磁盘空间 ==="
df -h "$DEPLOY_DIR" | tail -1
echo ""

# 10. 检查最近的错误日志
echo "=== 10. 最近的错误日志 ==="
if [ -f "$LOG_FILE" ]; then
    echo "最后50行日志:"
    tail -50 "$LOG_FILE" | grep -i "error\|fail\|❌" || echo "未找到错误信息"
else
    echo "日志文件不存在"
fi
echo ""

echo "============================================================"
echo "诊断完成！"
echo "日志文件: $LOG_FILE"
echo "============================================================"

