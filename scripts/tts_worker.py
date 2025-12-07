"""
TTS Worker (Local Integration Version) - 最终合成工兵
适配环境：AutoDL / Linux Server with Index-TTS2
功能：
1. 引入 scripts.tts_utils 加载本地模型
2. 自动索引 role_audio 目录下的所有音频
3. 读取 production_playlist.json 并动态修复路径
4. 调用 self.tts.infer 生成音频
5. 使用 pydub 进行去点击、拼接和渲染
"""

import json
import os
import sys
import time
import logging
from pathlib import Path

# === 1. 环境与依赖设置 ===

# 确保能导入项目根目录下的 scripts 模块
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# 引入音频处理库
try:
    from pydub import AudioSegment
    from pydub.generators import Sine
except ImportError:
    print("❌ 缺少 pydub 库，请运行: pip install pydub")
    sys.exit(1)

# 引入你的 TTS 模块
try:
    from scripts.tts_utils import initialize_tts_model, TTS_AVAILABLE
except ImportError as e:
    print(f"❌ 无法导入 scripts.tts_utils: {e}")
    print("请确保在项目根目录下运行此脚本，且 scripts 文件夹存在。")
    sys.exit(1)

# === 2. 配置参数 ===

BASE_DIR = Path(".")
PLAYLIST_FILE = BASE_DIR / "story/production_playlist_Ep01.json"
OUTPUT_DIR = BASE_DIR / "output"
SEGMENTS_DIR = OUTPUT_DIR / "segments"
FINAL_FILE = OUTPUT_DIR / "story/final_audiobook_Ep01.wav"

# [新增] 音频库根目录
# 脚本会自动扫描这个目录下的所有子文件夹寻找参考音频
AUDIO_LIB_DIR = BASE_DIR / "role_audio"
ANCHOR_DIR = BASE_DIR / "audio_library" / "anchor"  # 兜底音频目录

# 渲染参数
FADE_MS = 10  # 去点击 (ms)
INTERVAL_MS = 500  # 默认气口 (ms)

# 日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("LocalWorker")

# ============================================================================
# 3. 辅助类：音频文件管理器 (File Manager)
# ============================================================================


class AudioManager:
    """负责扫描和定位音频文件"""

    def __init__(self, lib_root: Path):
        self.lib_root = lib_root
        self.file_map = {}
        self._scan_library()

    def _scan_library(self):
        """递归扫描所有音频文件，建立 {filename: full_path} 索引"""
        if not self.lib_root.exists():
            logger.warning(f"⚠️ 音频库目录不存在: {self.lib_root}")
            return

        logger.info(f"🔍 正在索引音频库: {self.lib_root} ...")
        count = 0
        # 递归遍历所有子目录
        for path in self.lib_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in [".wav", ".mp3", ".flac"]:
                # 存入映射表：文件名 -> 绝对路径
                # 注意：这里假设文件名(ID)是全局唯一的，或者只要找到一个同名的就行
                self.file_map[path.name] = str(path.absolute())
                count += 1
        logger.info(f"✅ 索引完成，共找到 {count} 个音频文件")

    def find_path(self, file_id: str, original_path: str = "") -> str:
        """
        根据 ID 查找真实路径。
        策略：
        1. 如果 original_path 有效且存在，直接用。
        2. 尝试用 file_id 在索引里找。
        3. 尝试给 file_id 加上 .wav 后缀再找。
        4. 尝试在 anchor 目录找。
        """
        # 1. 检查原始路径
        if original_path and os.path.exists(original_path):
            return original_path

        # 2. 检查索引 (精确匹配)
        if file_id in self.file_map:
            return self.file_map[file_id]

        # 3. 检查索引 (尝试添加后缀)
        if not file_id.endswith(".wav"):
            wav_id = file_id + ".wav"
            if wav_id in self.file_map:
                return self.file_map[wav_id]

        # 4. 检查兜底 Anchor 目录
        # 处理 production_playlist.json 里写的相对路径 "audio_library/anchor/..."
        if "anchor" in str(original_path) or "anchor" in file_id:
            # 尝试拼接本地 anchor 路径
            local_anchor = ANCHOR_DIR / Path(original_path).name
            if local_anchor.exists():
                return str(local_anchor.absolute())

            # 尝试直接找文件名
            anchor_name = Path(original_path).name
            if anchor_name in self.file_map:
                return self.file_map[anchor_name]

        return None


# ============================================================================
# 4. 模型封装类 (LocalTTSWrapper)
# ============================================================================


class LocalTTSWrapper:
    def __init__(self):
        if not TTS_AVAILABLE:
            logger.error("❌ TTS 模块标记为不可用 (TTS_AVAILABLE=False)")
            sys.exit(1)

        logger.info("🚀 正在初始化本地 TTS 模型...")
        try:
            self.model = initialize_tts_model()
            if self.model is None:
                raise Exception("initialize_tts_model 返回了 None")
            logger.info("✅ 模型加载成功!")
        except Exception as e:
            logger.error(f"❌ 模型初始化失败: {e}")
            sys.exit(1)

    def synthesize(self, text, ref_audio_path, emotion, output_wav_path):
        """执行推理"""
        try:
            if not ref_audio_path or not os.path.exists(ref_audio_path):
                logger.error(f"❌ 参考音频无法访问: {ref_audio_path}")
                return False

            # 调用 IndexTTS2 推理
            self.model.infer(
                text=text,
                spk_audio_prompt=ref_audio_path,  # 音色参考
                emo_audio_prompt=ref_audio_path,  # 情绪参考
                output_path=output_wav_path,
                verbose=False,
            )

            if (
                os.path.exists(output_wav_path)
                and os.path.getsize(output_wav_path) > 100
            ):
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"推理过程报错: {e}")
            return False


# ============================================================================
# 5. 主工兵逻辑
# ============================================================================


class TTSWorker:
    def __init__(self):
        SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.tts = LocalTTSWrapper()
        self.audio_mgr = AudioManager(AUDIO_LIB_DIR)  # 初始化音频管理器
        self.final_track = AudioSegment.empty()

    def run(self):
        if not PLAYLIST_FILE.exists():
            logger.error("找不到 production_playlist.json")
            return

        with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
            playlist = json.load(f)

        logger.info(f"📂 开始处理 {len(playlist)} 个任务...")

        for item in playlist:
            seq = item["seq"]
            type_ = item["type"]

            # === 处理音效 (SFX) ===
            if type_ == "sfx":
                # 暂时用 2秒静音占位
                logger.info(f"[{seq}] 🎵 音效: {item['content']}")
                sfx = AudioSegment.silent(duration=2000)
                self.final_track += sfx

            # === 处理人声 (Speech) ===
            elif type_ == "speech":
                text = item["text"]
                role = item["role"]
                ref_info = item["ref_audio"]

                # [关键步骤] 动态寻找真实的音频路径
                original_path = ref_info.get("path", "")
                file_id = ref_info.get("id", "")

                real_ref_path = self.audio_mgr.find_path(file_id, original_path)

                if not real_ref_path:
                    logger.error(
                        f"❌ 找不到参考音频 (ID: {file_id}, Path: {original_path})，跳过此句"
                    )
                    # 可以在这里插入一段静音防止错位
                    self.final_track += AudioSegment.silent(duration=1000)
                    continue

                emotion = item["tts_params"]["emotion"]
                out_path = SEGMENTS_DIR / f"{seq:03d}_{role}.wav"

                logger.info(f"[{seq}] 🎙️ 合成: {role} -> {text[:15]}...")

                # 调用模型
                success = self.tts.synthesize(
                    text, real_ref_path, emotion, str(out_path)
                )

                if success:
                    try:
                        seg = AudioSegment.from_wav(str(out_path))
                        seg = seg.fade_in(FADE_MS).fade_out(FADE_MS)
                        self.final_track += seg
                        self.final_track += AudioSegment.silent(duration=INTERVAL_MS)
                    except Exception as e:
                        logger.error(f"音频处理失败: {e}")
                else:
                    logger.error(f"❌ 第 {seq} 句合成失败")

        # 导出
        logger.info("💾 正在渲染最终文件...")
        self.final_track.export(FINAL_FILE, format="wav")
        logger.info(f"🎉 任务完成! 文件路径: {FINAL_FILE}")


if __name__ == "__main__":
    worker = TTSWorker()
    worker.run()
