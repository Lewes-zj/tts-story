"""
Story Director - AI 有声书生产管线的中控台 (V2.0 Auto-Casting版)
功能：
1. 加载剧本 (Story JSON)
2. 加载角色映射 (Character Map)
3. 自动装载音频库 (Audio Libs)
4. 调度 AudioMatcher 进行全剧本匹配
5. 输出生产列表 (Production List)
"""

import json
import logging
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import Counter

# 引入核心匹配引擎
try:
    from audio_matcher import AudioMatcher
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).parent.parent))
    from audio_matcher import AudioMatcher
# ============================================================================
# LOGGING CONFIG (输出到屏幕 + 文件)
# ============================================================================

# 1. 定义统一的日志格式
log_formatter = logging.Formatter(
    "%(asctime)s - [Director] %(levelname)s - %(message)s", datefmt="%H:%M:%S"
)

# 2. 获取根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 清除可能存在的旧 handlers (防止在某些环境下重复打印)
root_logger.handlers = []

# 3. 添加控制台输出 (Console Handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# 4. 添加文件输出 (File Handler)
# mode='w': 每次运行覆盖旧日志; mode='a': 追加到旧日志后面
file_handler = logging.FileHandler("story_director.log", mode="w", encoding="utf-8")
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

# 获取当前模块的 logger
logger = logging.getLogger(__name__)

# ============================================================================
# STORY DIRECTOR CLASS
# ============================================================================


class StoryDirector:
    def __init__(self, lib_base_dir: str):
        """
        初始化总导演。
        Args:
            lib_base_dir: 存放所有 *_lib.json 音频库的文件夹路径
        """
        self.lib_base_dir = Path(lib_base_dir)
        self.cast_config: Dict[str, Dict[str, str]] = {}
        self.matchers: Dict[str, AudioMatcher] = {}
        self.loaded_libraries: Dict[str, Any] = {}

    def load_character_map(
        self, map_path: str, fallback_lib_name: str = "xiongda_lib.json"
    ):
        """
        [核心功能] 解析角色映射文件，自动构建演员表
        增加了“替身机制”：如果专属库不存在，自动使用 fallback_lib_name
        """
        logger.info(f"📜 正在解析选角表: {map_path}")

        # 1. 确定替身库的路径
        fallback_path = self.lib_base_dir / fallback_lib_name
        if not fallback_path.exists():
            logger.warning(f"⚠️ 替身库也找不到: {fallback_path}，后续可能会报错！")

        with open(map_path, "r", encoding="utf-8") as f:
            map_data = json.load(f)

        characters = map_data.get("character_assets_db", [])

        for char in characters:
            story_role_id = char["character_id"]  # e.g., CHAR_SCOUT_FROG
            source_id = char["meta_info"]["source_mapping_id"]  # e.g., xiaosongshu

            # 推断标准库文件名
            target_lib_filename = f"{source_id}_lib.json"
            target_lib_path = self.lib_base_dir / target_lib_filename

            # === 替身逻辑 ===
            if target_lib_path.exists():
                # A. 正常签约：有专属库
                self._sign_actor(story_role_id, str(target_lib_path), source_id)
            else:
                # B. 替身签约：没有专属库，用熊大顶替
                if fallback_path.exists():
                    logger.warning(
                        f"  🎭 角色 [{story_role_id}] 缺席 ({target_lib_filename} 未找到)，启用替身！"
                    )
                    self._sign_actor(
                        story_role_id, str(fallback_path), f"{source_id}(替身)"
                    )
                else:
                    logger.error(
                        f"  ❌ 角色 [{story_role_id}] 无法签约且无替身，将被跳过"
                    )

        # 同样处理默认旁白
        if "narrator" not in self.cast_config:
            narrator_lib = self.lib_base_dir / "narrator_lib.json"
            if narrator_lib.exists():
                self._sign_actor("narrator", str(narrator_lib), "narrator")
            elif fallback_path.exists():
                logger.info("  🎭 旁白缺席，启用替身")
                self._sign_actor("narrator", str(fallback_path), "narrator(替身)")

    def _sign_actor(self, story_role_id: str, lib_path: str, source_id: str):
        """签约单个演员：加载库、探测角色名、实例化Matcher"""

        # 1. 加载库 (带缓存)
        if lib_path not in self.loaded_libraries:
            try:
                with open(lib_path, "r", encoding="utf-8") as f:
                    library_data = json.load(f)
                self.loaded_libraries[lib_path] = library_data
            except Exception as e:
                logger.error(f"  ❌ 无法加载库 {lib_path}: {e}")
                return

        library_data = self.loaded_libraries[lib_path]

        # 2. [智能探测] 自动找出库里占比最高的 role 标签
        # 这样用户就不用手动配置 "adult_male_rough" 了
        roles = [item.get("role", "unknown") for item in library_data]
        if roles:
            most_common_role = Counter(roles).most_common(1)[0][0]
        else:
            most_common_role = "narrator"  # 兜底

        # 3. 注册配置
        self.cast_config[story_role_id] = {
            "lib_path": lib_path,
            "lib_role": most_common_role,
        }

        # 4. 实例化 Matcher
        self.matchers[story_role_id] = AudioMatcher(library_data)

        logger.info(
            f"  ✅ 签约成功: [{story_role_id}] -> 演员: {source_id} (库角色: {most_common_role})"
        )

    def direct_story(self, story_path: str, output_path: str):
        """开始执导"""
        if not self.matchers:
            logger.error("❌ 剧组为空！请先调用 load_character_map 加载演员。")
            return

        logger.info(f"🎥 Action! 开始处理剧本: {Path(story_path).name}")

        with open(story_path, "r", encoding="utf-8") as f:
            story_slices = json.load(f)

        production_list = []
        stats = {"sfx": 0, "speech": 0, "fallback": 0}

        for i, slice_data in enumerate(story_slices):
            slice_type = slice_data.get("type", "unknown")

            # === 1. 音效 (SFX) ===
            if slice_type == "sfx":
                prod_item = {
                    "seq": i,
                    "type": "sfx",
                    "content": slice_data.get("content"),
                    "duration_est": 3.0,
                }
                production_list.append(prod_item)
                stats["sfx"] += 1
                continue

            # === 2. 对白/旁白 (Speech) ===
            if slice_type in ["narrator", "dialogue"]:
                # 确定剧本角色
                story_role = (
                    slice_data.get("role", "narrator")
                    if slice_type == "dialogue"
                    else "narrator"
                )

                # 查找签约演员
                if story_role not in self.matchers:
                    # 尝试找旁白兜底
                    if "narrator" in self.matchers:
                        # logger.warning(f"[{i}] 角色 {story_role} 缺席，旁白替身")
                        story_role = "narrator"
                    else:
                        logger.error(
                            f"[{i}] 严重: 角色 {story_role} 未找到且无旁白，跳过"
                        )
                        continue

                matcher = self.matchers[story_role]
                lib_role = self.cast_config[story_role]["lib_role"]

                # 构造查询请求
                target_node = slice_data.copy()
                target_node["text"] = slice_data.get("content", "")
                target_node["role_tag"] = lib_role  # 强制替换为库里的角色名，通过L1门禁

                # Match!
                match_result = matcher.get_best_match(target_node)

                # 结果封装
                prod_item = {
                    "seq": i,
                    "type": "speech",
                    "role": story_role,  # 保持原始剧本角色名
                    "actor_role": lib_role,  # 实际配音的库角色
                    "text": target_node["text"],
                    "ref_audio": {
                        "path": match_result.get(
                            "file_path", match_result.get("audio_path", "")
                        ),
                        "id": match_result.get("id"),
                        "score": match_result.get("total_score", 0),
                        "match_level": match_result.get("match_level", "unknown"),
                        "semantic_desc": slice_data.get("semantic_vector_desc", ""),
                    },
                    # 传递情感参数给TTS
                    "tts_params": {
                        "speed": 1.0,
                        "emotion": slice_data.get("timbral", {}).get(
                            "vocal_mode", "neutral"
                        ),
                    },
                }

                if "Anchor" in str(match_result.get("match_level", "")):
                    stats["fallback"] += 1

                production_list.append(prod_item)
                stats["speech"] += 1

                # 实时日志
                score = match_result.get("total_score", 0)
                icon = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
                snippet = target_node["text"][:10].replace("\n", "")
                logger.info(
                    f"[{i:03d}] {icon} {story_role} -> {match_result.get('id')} ({score:.1f}) | {snippet}"
                )

        # 输出文件
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(production_list, f, ensure_ascii=False, indent=2)

        logger.info(f"\n🎬 杀青! 列表已保存: {output_path}")
        logger.info(
            f"📊 统计: 对白 {stats['speech']} (兜底 {stats['fallback']}) | 音效 {stats['sfx']}"
        )


# ============================================================================
# MAIN ENTRY
# ============================================================================

if __name__ == "__main__":
    import argparse

    # 设定默认路径 (根据你的环境)
    BASE_PATH = Path("/Users/xinliu/Documents/xxx/story-project")
    DEFAULT_LIB_DIR = "."  # 假设你就在当前目录下运行
    DEFAULT_MAP_FILE = BASE_PATH / "story/role_mapping.json"
    DEFAULT_STORY_FILE = BASE_PATH / "story/ToyRoomDefender_Ep01.json"
    DEFAULT_OUTPUT = "story/production_playlist_Ep01.json"

    # 1. 初始化导演 (指定音频库目录)
    # 注意：这里假设你的 xiongda_lib.json 等文件都在当前目录，或者你可以改为绝对路径
    director = StoryDirector(lib_base_dir=BASE_PATH / "role_audio_clip_lib")

    # 2. 加载角色映射 (自动构建演员表)
    if DEFAULT_MAP_FILE.exists():
        director.load_character_map(str(DEFAULT_MAP_FILE))
    else:
        logger.error(f"找不到角色映射文件: {DEFAULT_MAP_FILE}")
        exit(1)

    # 3. 开始导戏
    if DEFAULT_STORY_FILE.exists():
        director.direct_story(str(DEFAULT_STORY_FILE), DEFAULT_OUTPUT)
    else:
        logger.error(f"找不到剧本文件: {DEFAULT_STORY_FILE}")
