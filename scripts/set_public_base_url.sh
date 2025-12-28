#!/bin/bash
# 设置 PUBLIC_BASE_URL 环境变量的帮助脚本

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== PUBLIC_BASE_URL 环境变量设置工具 ===${NC}\n"

# 如果提供了参数，使用参数值
if [ -n "$1" ]; then
    PUBLIC_BASE_URL_VALUE="$1"
else
    echo "请输入 PUBLIC_BASE_URL 的值（例如: https://xxx-6008.gradio.live 或 https://xxx.bjb1.seetacloud.com:8443）"
    echo -n "PUBLIC_BASE_URL: "
    read PUBLIC_BASE_URL_VALUE
fi

if [ -z "$PUBLIC_BASE_URL_VALUE" ]; then
    echo -e "${RED}错误: PUBLIC_BASE_URL 不能为空${NC}"
    exit 1
fi

echo ""
echo "设置 PUBLIC_BASE_URL = $PUBLIC_BASE_URL_VALUE"
echo ""

# 方法1: 修复 ~/.bashrc（如果之前错误添加了）
BASHRC_PATH="$HOME/.bashrc"
if [ -f "$BASHRC_PATH" ]; then
    # 检查是否已有 PUBLIC_BASE_URL
    if grep -q "export PUBLIC_BASE_URL=" "$BASHRC_PATH"; then
        echo -e "${YELLOW}检测到 ~/.bashrc 中已有 PUBLIC_BASE_URL 配置${NC}"
        echo "是否要更新它? (y/n)"
        read -r UPDATE_CHOICE
        if [ "$UPDATE_CHOICE" = "y" ] || [ "$UPDATE_CHOICE" = "Y" ]; then
            # 删除旧配置
            sed -i.bak '/^export PUBLIC_BASE_URL=/d' "$BASHRC_PATH"
            echo "已删除旧的配置"
        else
            echo "跳过 ~/.bashrc 更新"
        fi
    fi
    
    # 如果没有或用户选择更新，添加新配置
    if ! grep -q "export PUBLIC_BASE_URL=" "$BASHRC_PATH"; then
        echo "" >> "$BASHRC_PATH"
        echo "# PUBLIC_BASE_URL for TTS Story API" >> "$BASHRC_PATH"
        echo "export PUBLIC_BASE_URL=\"$PUBLIC_BASE_URL_VALUE\"" >> "$BASHRC_PATH"
        echo -e "${GREEN}✓ 已添加到 ~/.bashrc${NC}"
    fi
else
    # 创建 ~/.bashrc（如果不存在）
    echo "# PUBLIC_BASE_URL for TTS Story API" >> "$BASHRC_PATH"
    echo "export PUBLIC_BASE_URL=\"$PUBLIC_BASE_URL_VALUE\"" >> "$BASHRC_PATH"
    echo -e "${GREEN}✓ 已创建并添加到 ~/.bashrc${NC}"
fi

# 方法2: 创建或更新 .env 文件（推荐用于启动脚本）
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    if grep -q "^PUBLIC_BASE_URL=" "$ENV_FILE"; then
        # 更新现有值
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=\"$PUBLIC_BASE_URL_VALUE\"|" "$ENV_FILE"
        else
            # Linux
            sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=\"$PUBLIC_BASE_URL_VALUE\"|" "$ENV_FILE"
        fi
        echo -e "${GREEN}✓ 已更新 .env 文件${NC}"
    else
        echo "" >> "$ENV_FILE"
        echo "PUBLIC_BASE_URL=\"$PUBLIC_BASE_URL_VALUE\"" >> "$ENV_FILE"
        echo -e "${GREEN}✓ 已添加到 .env 文件${NC}"
    fi
else
    echo "PUBLIC_BASE_URL=\"$PUBLIC_BASE_URL_VALUE\"" > "$ENV_FILE"
    echo -e "${GREEN}✓ 已创建 .env 文件${NC}"
fi

# 方法3: 在当前 shell 中立即生效
export PUBLIC_BASE_URL="$PUBLIC_BASE_URL_VALUE"
echo -e "${GREEN}✓ 已在当前 shell 中设置（仅当前会话有效）${NC}"

echo ""
echo -e "${GREEN}=== 设置完成 ===${NC}"
echo ""
echo "已通过以下方式设置 PUBLIC_BASE_URL:"
echo "  1. ✓ ~/.bashrc（新终端会话中生效）"
echo "  2. ✓ .env 文件（启动脚本会自动读取）"
echo "  3. ✓ 当前 shell（仅当前会话有效）"
echo ""
echo "注意:"
echo "  - 如果使用启动脚本 (start_all_services.py)，它会自动从 .env 文件或 ~/.bashrc 读取"
echo "  - 如果直接启动 Python 应用，需要在启动前运行: source ~/.bashrc"
echo "  - 或者重新打开终端窗口"
echo ""
echo "验证设置:"
echo "  echo \$PUBLIC_BASE_URL"
echo "  应该输出: $PUBLIC_BASE_URL_VALUE"

