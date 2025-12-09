"""
Story Director - AI 有声书生产管线的中控台 (V2.1 Multi-File Support)
功能：
1. 加载剧本 (Story JSON)
2. 加载角色映射 (Character Map)
3. 自动装载音频库 (支持单文件 .json 或 文件夹多 .json 模式)
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
# LOGGING CONFIG (动态配置函数)
# ============================================================================


def setup_logging(log_file_path: str):
    """
    配置日志：同时输出到屏幕和指定的文件
    """
    # 确保日志目录存在
    log_path_obj = Path(log_file_path)
    log_path_obj.parent.mkdir(parents=True, exist_ok=True)

    # 1. 定义格式
    log_formatter = logging.Formatter(
        "%(asctime)s - [Director] %(levelname)s - %(message)s", datefmt="%H:%M:%S"
    )

    # 2. 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清除旧的 handlers (避免重复打印)
    root_logger.handlers = []

    # 3. 添加控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

    # 4. 添加文件输出 (使用传入的动态路径)
    file_handler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)


# 获取当前模块 logger
logger = logging.getLogger(__name__)

# ============================================================================
# STORY DIRECTOR CLASS
# ============================================================================


class StoryDirector:
    def __init__(self, lib_base_dir: str):
        """
        初始化总导演。
        Args:
            lib_base_dir: 存放音频库的根目录 (可以是 .json 文件或包含 .json 的子文件夹)
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
        支持：单文件库 (xiongda_lib.json) 和 文件夹库 (narrator_lib/)
        """
        logger.info(f"📜 正在解析选角表: {map_path}")

        # 1. 确定替身库的路径
        fallback_path = self.lib_base_dir / fallback_lib_name
        if not fallback_path.exists():
            # 尝试看看是不是文件夹格式的替身
            fallback_dir = self.lib_base_dir / fallback_lib_name.replace(".json", "")
            if fallback_dir.exists() and fallback_dir.is_dir():
                fallback_path = fallback_dir
            else:
                logger.warning(
                    f"⚠️ 替身库也找不到: {fallback_lib_name}，后续可能会报错！"
                )

        with open(map_path, "r", encoding="utf-8") as f:
            map_data = json.load(f)

        characters = map_data.get("character_assets_db", [])

        for char in characters:
            story_role_id = char["character_id"]  # e.g., CHAR_SCOUT_FROG
            source_id = char["meta_info"]["source_mapping_id"]  # e.g., narrator

            # === [修改点] 智能探测路径 (优先找文件夹，再找文件) ===
            # 1. 尝试找文件夹: role_audio_clip_lib/narrator_lib/
            target_lib_dir = self.lib_base_dir / f"{source_id}_lib"
            # 2. 尝试找文件: role_audio_clip_lib/narrator_lib.json
            target_lib_file = self.lib_base_dir / f"{source_id}_lib.json"

            final_target_path = None

            if target_lib_dir.exists() and target_lib_dir.is_dir():
                final_target_path = target_lib_dir
            elif target_lib_file.exists() and target_lib_file.is_file():
                final_target_path = target_lib_file

            # === 签约逻辑 ===
            if final_target_path:
                # A. 正常签约：找到专属库
                self._sign_actor(story_role_id, str(final_target_path), source_id)
            else:
                # B. 替身签约：没有专属库，用替身
                if fallback_path.exists():
                    logger.warning(
                        f"  🎭 角色 [{story_role_id}] 缺席 (库未找到)，启用替身！"
                    )
                    self._sign_actor(
                        story_role_id, str(fallback_path), f"{source_id}(替身)"
                    )
                else:
                    logger.error(
                        f"  ❌ 角色 [{story_role_id}] 无法签约且无替身，将被跳过"
                    )

        # 同样处理默认旁白 (如果没有在 map 中显式定义)
        if "narrator" not in self.cast_config:
            # 同样尝试找文件夹或文件
            narrator_dir = self.lib_base_dir / "narrator_lib"
            narrator_file = self.lib_base_dir / "narrator_lib.json"

            if narrator_dir.exists() and narrator_dir.is_dir():
                self._sign_actor("narrator", str(narrator_dir), "narrator")
            elif narrator_file.exists():
                self._sign_actor("narrator", str(narrator_file), "narrator")
            elif fallback_path.exists():
                logger.info("  🎭 旁白缺席，启用替身")
                self._sign_actor("narrator", str(fallback_path), "narrator(替身)")

    def _sign_actor(self, story_role_id: str, lib_path: str, source_id: str):
        """
        签约单个演员：加载库(支持目录或文件)、探测角色名、实例化Matcher
        """
        path_obj = Path(lib_path)
        library_data = []

        # 1. 加载库 (带缓存)
        if lib_path in self.loaded_libraries:
            library_data = self.loaded_libraries[lib_path]
        else:
            try:
                # === [修改点] 支持目录加载 ===
                if path_obj.is_dir():
                    # 扫描目录下所有 json 文件
                    json_files = list(path_obj.glob("*.json"))
                    if not json_files:
                        logger.error(f"  ❌ 目录为空，未找到JSON: {lib_path}")
                        return

                    logger.info(
                        f"  📂 检测到库目录: {path_obj.name}，正在合并 {len(json_files)} 个文件..."
                    )

                    for jf in json_files:
                        try:
                            with open(jf, "r", encoding="utf-8") as f:
                                chunk = json.load(f)
                                if isinstance(chunk, list):
                                    library_data.extend(chunk)
                                else:
                                    logger.warning(f"  ⚠️ 跳过非列表格式文件: {jf.name}")
                        except Exception as e:
                            logger.error(f"  ⚠️ 读取文件失败 {jf.name}: {e}")

                else:
                    # 传统的单文件加载
                    with open(path_obj, "r", encoding="utf-8") as f:
                        library_data = json.load(f)

                # 存入缓存
                self.loaded_libraries[lib_path] = library_data
                logger.info(
                    f"  📖 库加载完成: {source_id} (共 {len(library_data)} 条素材)"
                )

            except Exception as e:
                logger.error(f"  ❌ 无法加载库 {lib_path}: {e}")
                return

        # 2. [智能探测] 自动找出库里占比最高的 role 标签
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
            f"  ✅ 签约成功: [{story_role_id}] -> 演员: {source_id} (角色Tag: {most_common_role})"
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
                    if "narrator" in self.matchers:
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
                target_node["role_tag"] = lib_role

                # Match!
                match_result = matcher.get_best_match(target_node)

                # 结果封装
                prod_item = {
                    "seq": i,
                    "type": "speech",
                    "role": story_role,
                    "actor_role": lib_role,
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
    from datetime import datetime

    # 设定默认路径
    BASE_PATH = Path("/Users/xinliu/Documents/xxx/story-project")

    DEFAULT_LIB_DIR = BASE_PATH / "role_audio_clip_lib"
    DEFAULT_MAP_FILE = BASE_PATH / "story/role_mapping.json"
    DEFAULT_STORY_FILE = BASE_PATH / "story/ToyRoomDefender_Ep01.json"

    # === [关键修改] 动态生成文件名 ===
    # 1. 生成时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 2. 定义基础文件名 (不带后缀)
    base_filename = f"story/production_playlist_Ep01_{timestamp}"

    # 3. 分别加上后缀
    DEFAULT_OUTPUT = f"{base_filename}.json"  # 输出列表
    DEFAULT_LOG = f"{base_filename}.log"  # 对应的日志

    # 4. [激活日志] 传入刚才生成的日志路径
    # 注意：这里需要把相对路径转为基于 BASE_PATH 的路径，或者确保执行目录正确
    # 这里假设 story 文件夹就在当前运行目录下，或者你可以写死绝对路径
    setup_logging(DEFAULT_LOG)

    logger.info(f"🚀 本次任务 ID: {timestamp}")
    logger.info(f"📝 日志文件: {DEFAULT_LOG}")
    logger.info(f"💾 输出文件: {DEFAULT_OUTPUT}")

    # 5. 初始化导演
    director = StoryDirector(lib_base_dir=DEFAULT_LIB_DIR)

    # 6. 加载角色映射
    if DEFAULT_MAP_FILE.exists():
        director.load_character_map(str(DEFAULT_MAP_FILE))
    else:
        logger.error(f"找不到角色映射文件: {DEFAULT_MAP_FILE}")
        exit(1)

    # 7. 开始导戏
    if DEFAULT_STORY_FILE.exists():
        director.direct_story(str(DEFAULT_STORY_FILE), DEFAULT_OUTPUT)
    else:
        logger.error(f"找不到剧本文件: {DEFAULT_STORY_FILE}")
