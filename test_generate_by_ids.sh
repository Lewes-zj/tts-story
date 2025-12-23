#!/bin/bash
# 测试脚本：验证 ID-based 音频生成 API

echo "========================================="
echo "测试 ID-based 音频生成 API"
echo "========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# API 基础地址
API_URL="http://localhost:8000"

echo -e "${YELLOW}步骤 1: 检查 FastAPI 服务是否运行${NC}"
if curl -s "${API_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ FastAPI 服务正在运行${NC}"
else
    echo -e "${RED}✗ FastAPI 服务未运行${NC}"
    echo "请先启动服务: cd tts-story && uvicorn app.main:app --reload"
    exit 1
fi

echo ""
echo -e "${YELLOW}步骤 2: 测试有效请求${NC}"
echo "发送请求: POST /api/generate_by_ids"
echo '{"story_id": 1, "user_id": 101, "role_id": 5}'
echo ""

RESPONSE=$(curl -s -X POST "${API_URL}/api/generate_by_ids" \
  -H "Content-Type: application/json" \
  -d '{"story_id": 1, "user_id": 101, "role_id": 5}')

echo "响应:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# 检查响应是否包含 task_id
if echo "$RESPONSE" | grep -q "task_id"; then
    TASK_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['task_id'])" 2>/dev/null)
    echo -e "${GREEN}✓ 任务创建成功! task_id: $TASK_ID${NC}"
    
    echo ""
    echo -e "${YELLOW}步骤 3: 查询任务状态${NC}"
    sleep 2
    curl -s "${API_URL}/api/task/${TASK_ID}" | python3 -m json.tool
else
    echo -e "${RED}✗ 任务创建失败${NC}"
    echo ""
    echo -e "${YELLOW}可能的原因:${NC}"
    echo "1. 配置文件 tts-story/config/story_library_1.json 不存在或格式错误"
    echo "2. 数据库中没有 user_id=101, role_id=5 的音频记录"
    echo "3. 配置文件缺少必需字段 (json_db, emo_audio_folder, bgm_path, script_json)"
fi

echo ""
echo -e "${YELLOW}步骤 4: 测试错误场景 - 配置文件不存在${NC}"
echo "发送请求: story_id=999 (不存在)"
RESPONSE=$(curl -s -X POST "${API_URL}/api/generate_by_ids" \
  -H "Content-Type: application/json" \
  -d '{"story_id": 999, "user_id": 101, "role_id": 5}')

if echo "$RESPONSE" | grep -q "未找到故事配置"; then
    echo -e "${GREEN}✓ 正确返回 404 错误${NC}"
else
    echo -e "${RED}✗ 错误处理不正确${NC}"
fi
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

echo ""
echo -e "${YELLOW}步骤 5: 测试错误场景 - 用户音频不存在${NC}"
echo "发送请求: user_id=999, role_id=999 (不存在)"
RESPONSE=$(curl -s -X POST "${API_URL}/api/generate_by_ids" \
  -H "Content-Type: application/json" \
  -d '{"story_id": 1, "user_id": 999, "role_id": 999}')

if echo "$RESPONSE" | grep -q "请先生成"; then
    echo -e "${GREEN}✓ 正确返回 400 错误${NC}"
else
    echo -e "${RED}✗ 错误处理不正确${NC}"
fi
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

echo ""
echo "========================================="
echo "测试完成"
echo "========================================="
