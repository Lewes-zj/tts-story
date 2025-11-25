# DeepFilterNet + Denoiser 部署指南 - 服务器 374

## 部署目标

在服务器 374 的 `/root/autodl-tmp/extract-vocals` 目录下部署 DeepFilterNet 和 Denoiser，实现两步音频处理流程（降噪 + 去混响）。

## 前置条件

- 服务器：374
- 部署路径：`/root/autodl-tmp/extract-vocals`
- GPU：RTX 5090（需要特殊处理兼容性）

---

## 部署步骤

### 步骤 1: 检查环境

```bash
# 检查当前目录
cd /root/autodl-tmp/extract-vocals
pwd

# 检查 Python 版本
python3 --version

# 检查 GPU 信息
nvidia-smi

# 检查 CUDA 版本
nvcc --version 2>/dev/null || echo "nvcc not found"
```

**预期结果**：

- Python 3.12+
- CUDA 12.4+
- RTX 5090 可用

---

### 步骤 2: 创建虚拟环境

```bash
cd /root/autodl-tmp/extract-vocals

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 验证虚拟环境
which python3
python3 --version
```

**预期结果**：

- 虚拟环境创建成功
- Python 路径指向 `venv/bin/python3`

---

### 步骤 3: 安装 PyTorch（支持 RTX 5090）

```bash
# 确保在虚拟环境中
source venv/bin/activate

# 卸载可能存在的旧版本
pip uninstall -y torch torchvision torchaudio

# 安装 PyTorch 2.5.0（稳定版，通过兼容模式支持 RTX 5090）
pip install torch==2.5.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 验证安装
python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

**注意**：

- 虽然会显示 sm_120 不兼容警告，但可以通过兼容模式正常运行
- 测试 GPU 计算功能是否正常

**预期结果**：

- PyTorch 2.5.0+cu124 安装成功
- CUDA 可用
- GPU 计算测试通过

---

### 步骤 4: 安装基础依赖

```bash
source venv/bin/activate

# 安装音频处理相关库
pip install soundfile librosa numpy scipy
```

**预期结果**：

- 所有依赖安装成功

---

### 步骤 5: 安装 DeepFilterNet

```bash
source venv/bin/activate

# 通过 pip 安装
pip install deepfilternet

# 验证安装
python3 -c "import df.enhance; print('DeepFilterNet installed successfully')"
```

**预期结果**：

- DeepFilterNet 安装成功
- 可以正常导入

---

### 步骤 6: 安装 Denoiser

```bash
source venv/bin/activate

# 通过 pip 安装
pip install denoiser

# 验证安装
python3 -c "from denoiser import pretrained; print('Denoiser installed successfully')"
```

**预期结果**：

- Denoiser 安装成功
- 可以正常导入

---

### 步骤 7: 下载 DeepFilterNet3 模型

```bash
cd /root/autodl-tmp/extract-vocals

# 创建模型目录
mkdir -p models/DeepFilterNet3

# 下载模型
cd models/DeepFilterNet3
wget --progress=bar:force -O DeepFilterNet3.zip "https://github.com/Rikorose/DeepFilterNet/raw/main/models/DeepFilterNet3.zip"

# 解压模型
unzip -q DeepFilterNet3.zip

# 清理 zip 文件
rm -f DeepFilterNet3.zip

# 验证模型文件
ls -lh
# 应该看到: checkpoints/ 和 config.ini
```

**预期结果**：

- 模型文件下载成功
- 解压后包含 `checkpoints/` 和 `config.ini`

---

### 步骤 8: 测试模型加载

```bash
source venv/bin/activate
cd /root/autodl-tmp/extract-vocals

python3 << 'PYEOF'
from df import init_df
from df.modules import get_device

print("测试模型加载...")
model_path = "/root/autodl-tmp/extract-vocals/models/DeepFilterNet3"

try:
    model, df_state, suffix = init_df(
        model_base_dir=model_path,
        post_filter=True,
        log_level="INFO",
        config_allow_defaults=True,
    )
    device = get_device()
    model = model.to(device)
    print(f"✅ 模型加载成功！")
    print(f"   设备: {device}")
    print(f"   模型后缀: {suffix}")
except Exception as e:
    print(f"❌ 模型加载失败: {e}")
    import traceback
    traceback.print_exc()
PYEOF
```

**预期结果**：

- 模型可以正常加载
- 无错误信息

---

### 步骤 9: 测试 Denoiser 模型

```bash
source venv/bin/activate

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
PYEOF
```

**预期结果**：

- Denoiser 模型可以正常加载
- 模型会自动下载到 `~/.cache/torch/hub/checkpoints/`

---

### 步骤 10: 创建处理脚本

创建 `process_audio.py`：

```bash
cd /root/autodl-tmp/extract-vocals
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
```

---

### 步骤 11: 创建音频处理服务脚本

创建 `audio_processor_service.py`：

```bash
cd /root/autodl-tmp/extract-vocals
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
```

---

### 步骤 12: 验证安装

```bash
source venv/bin/activate
cd /root/autodl-tmp/extract-vocals

# 环境检查
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
PYEOF
```

**预期结果**：

- 所有模块都可以正常导入
- 无错误信息

---

### 步骤 13: 测试处理脚本

```bash
source venv/bin/activate
cd /root/autodl-tmp/extract-vocals

# 如果有测试音频文件
if [ -f "test_audio.wav" ]; then
    python3 process_audio.py test_audio.wav test_output.wav
    echo "处理完成，检查 test_output.wav"
else
    echo "没有测试文件，跳过测试"
fi
```

---

## 项目结构

部署完成后的目录结构：

```
/root/autodl-tmp/extract-vocals/
├── venv/                          # Python 虚拟环境
│   └── lib/python3.12/site-packages/
│       ├── torch/                 # PyTorch 2.5.0
│       ├── df/                    # DeepFilterNet
│       └── denoiser/              # Denoiser
├── models/
│   └── DeepFilterNet3/            # DeepFilterNet3 模型
│       ├── checkpoints/
│       └── config.ini
├── process_audio.py               # 两步处理脚本
├── audio_processor_service.py    # 音频处理服务脚本
└── README.md                      # 使用说明（可选）
```

---

## 使用方法

### 基本用法

```bash
# 激活虚拟环境
source /root/autodl-tmp/extract-vocals/venv/bin/activate

# 运行处理脚本
python3 process_audio.py input.wav output.wav
```

### 通过服务脚本调用

```bash
python3 /root/autodl-tmp/extract-vocals/audio_processor_service.py input.wav output.wav
```

---

## RTX 5090 兼容性说明

- **PyTorch 版本**：2.5.0+cu124（稳定版）
- **兼容模式**：虽然显示 sm_120 不兼容警告，但可以通过兼容模式正常运行
- **性能**：可能不是最优性能（使用 sm_90 兼容代码），但功能正常
- **测试结果**：GPU 计算功能正常，模型可以正常加载和运行

---

## 故障排除

### 问题 1: PyTorch 不支持 RTX 5090

**现象**：显示 "sm_120 is not compatible" 警告

**解决**：

- 这是正常的，PyTorch 2.5.0 通过兼容模式可以运行
- 测试 GPU 计算功能是否正常
- 如果仍有问题，可以尝试使用 CPU 模式：`--device cpu`

### 问题 2: 模型下载失败

**解决**：

- 检查网络连接
- 手动下载模型文件（见步骤 7）
- 模型会下载到 `~/.cache/torch/hub/checkpoints/` 目录

### 问题 3: 虚拟环境 Python 找不到

**解决**：

- 确认虚拟环境已创建：`ls -la venv/bin/python3`
- 重新创建虚拟环境：`python3 -m venv venv`

---

## 验证清单

- [ ] 虚拟环境创建成功
- [ ] PyTorch 2.5.0 安装并测试通过
- [ ] DeepFilterNet 安装并测试通过
- [ ] Denoiser 安装并测试通过
- [ ] DeepFilterNet3 模型下载并可以加载
- [ ] 处理脚本创建并可以运行
- [ ] 服务脚本创建并可以调用
- [ ] 环境检查全部通过

---

## 部署完成

部署完成后，系统已具备：

- ✅ DeepFilterNet 降噪功能
- ✅ Denoiser 去混响功能
- ✅ 两步处理流程脚本
- ✅ 可被其他项目调用的服务脚本

---

**部署日期**：2025 年 11 月 24 日  
**服务器**：374  
**部署路径**：`/root/autodl-tmp/extract-vocals`

---

## 快速部署（推荐）

使用自动化脚本一键部署：

```bash
# 上传 complete_deployment_script.sh 到服务器374
# 在服务器上执行：
cd /root/autodl-tmp/extract-vocals
bash complete_deployment_script.sh
```

脚本会自动完成所有步骤，包括：

- 创建虚拟环境
- 安装所有依赖
- 下载模型
- 创建处理脚本
- 验证安装

---

## 执行记录

### 执行方式

**方法 1：使用自动化脚本（推荐）**

```bash
cd /root/autodl-tmp/extract-vocals
bash complete_deployment_script.sh
```

**方法 2：手动执行**
按照上述步骤 1-13 逐步执行

### 执行结果记录

请在执行后填写以下信息：

- [ ] **步骤 1-2**：环境检查和虚拟环境创建

  - Python 版本：\***\*\_\_\_\*\***
  - GPU 信息：\***\*\_\_\_\*\***
  - 虚拟环境创建：✅ / ❌

- [ ] **步骤 3**：PyTorch 安装

  - PyTorch 版本：\***\*\_\_\_\*\***
  - CUDA 可用：✅ / ❌
  - GPU 计算测试：✅ / ❌

- [ ] **步骤 4-6**：依赖安装

  - DeepFilterNet：✅ / ❌
  - Denoiser：✅ / ❌
  - 其他依赖：✅ / ❌

- [ ] **步骤 7**：模型下载

  - 模型下载：✅ / ❌
  - 模型路径：\***\*\_\_\_\*\***

- [ ] **步骤 8-9**：模型测试

  - DeepFilterNet3 加载：✅ / ❌
  - Denoiser 加载：✅ / ❌

- [ ] **步骤 10-11**：脚本创建

  - process_audio.py：✅ / ❌
  - audio_processor_service.py：✅ / ❌

- [ ] **步骤 12-13**：最终验证
  - 环境检查：✅ / ❌
  - 脚本验证：✅ / ❌

### 遇到的问题及解决方案

**问题 1**：\***\*\_\_\_\*\***

- 解决方案：\***\*\_\_\_\*\***

**问题 2**：\***\*\_\_\_\*\***

- 解决方案：\***\*\_\_\_\*\***

---

## 部署验证

部署完成后，执行以下命令验证：

```bash
cd /root/autodl-tmp/extract-vocals
source venv/bin/activate

# 测试处理脚本
python3 process_audio.py --help

# 测试服务脚本
python3 audio_processor_service.py --help
```

如果两个脚本都能正常显示帮助信息，说明部署成功。
