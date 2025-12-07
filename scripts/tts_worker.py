"""
TTS Worker (Local Integration Version) - 最终合成工兵
适配环境：AutoDL / Linux Server with Index-TTS2
功能：
1. 引入 scripts.tts_utils 加载本地模型
2. 自动索引 role_audio 目录下的所有音频
3. 读取 production_playlist.json 并动态修复路径
4. 调用 self.tts.infer 生成音频 (支持旁白音色替换)
5. 使用 pydub 进行去点击、拼接和渲染
"""

import json
import os
import sys
import time
import logging
import argparse  # [新增] 用于接收命令行参数
from pathlib import Path

# === 1. 环境与依赖设置 ===
current_script_path = Path(__file__).resolve()
scripts_dir = current_script_path.parent
code_root = scripts_dir.parent

if str(code_root) not in sys.path:
    sys.path.append(str(code_root))

try:
    from pydub import AudioSegment
    from pydub.generators import Sine
except ImportError:
    print("❌ 缺少 pydub 库，请运行: pip install pydub")
    sys.exit(1)

try:
    from scripts.tts_utils import initialize_tts_model, TTS_AVAILABLE
except ImportError as e:
    print(f"❌ 无法导入 scripts.tts_utils: {e}")
    sys.exit(1)

# === 2. 配置参数 ===
DATA_ROOT = code_root.parent
logger = logging.getLogger("LocalWorker")

PLAYLIST_FILE = DATA_ROOT / "story/production_playlist_Ep01.json"
OUTPUT_DIR = DATA_ROOT / "output"
SEGMENTS_DIR = OUTPUT_DIR / "segments"
FINAL_FILE = OUTPUT_DIR / "story/final_audiobook_Ep01.wav"

AUDIO_LIB_DIR = DATA_ROOT / "role_audio"
ANCHOR_DIR = DATA_ROOT / "audio_library/anchor"

FADE_MS = 10
INTERVAL_MS = 500

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("LocalWorker")


# ============================================================================
# 3. 辅助类：音频文件管理器
# ============================================================================
class AudioManager:
    """负责扫描和定位音频文件"""

    def __init__(self, lib_root: Path):
        self.lib_root = lib_root
        self.file_map = {}
        self._scan_library()

    def _scan_library(self):
        if not self.lib_root.exists():
            logger.warning(f"⚠️ 音频库目录不存在: {self.lib_root}")
            return
        logger.info(f"🔍 正在索引音频库: {self.lib_root} ...")
        count = 0
        for path in self.lib_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in [".wav", ".mp3", ".flac"]:
                self.file_map[path.name] = str(path.absolute())
                count += 1
        logger.info(f"✅ 索引完成，共找到 {count} 个音频文件")

    def find_path(self, file_id: str, original_path: str = "") -> str:
        if original_path and os.path.exists(original_path):
            return original_path
        if file_id in self.file_map:
            return self.file_map[file_id]
        if not file_id.endswith(".wav"):
            wav_id = file_id + ".wav"
            if wav_id in self.file_map:
                return self.file_map[wav_id]
        if "anchor" in str(original_path) or "anchor" in file_id:
            local_anchor = ANCHOR_DIR / Path(original_path).name
            if local_anchor.exists():
                return str(local_anchor.absolute())
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
            logger.error("❌ TTS 模块标记为不可用")
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

    def synthesize(
        self,
        text,
        ref_audio_path,
        emotion,
        output_wav_path,
        narrator_input=None,
        role="unknown",
    ):
        """
        执行推理
        Args:
            narrator_input: (可选) 强制指定的旁白音色文件路径
            role: 当前角色名称
        """
        try:
            if not ref_audio_path or not os.path.exists(ref_audio_path):
                logger.error(f"❌ 参考音频无法访问: {ref_audio_path}")
                return False

            # === [关键逻辑修改] ===
            # 默认：音色(spk) 和 情绪(emo) 都用 ref_audio
            spk_audio = ref_audio_path
            emo_audio = ref_audio_path

            # 特殊情况：如果是旁白角色，且用户指定了 narrator_input
            if role == "narrator" and narrator_input:
                if os.path.exists(narrator_input):
                    # 替换音色，但保留 ref_audio 的情绪
                    spk_audio = narrator_input
                    # logger.info(f"   ✨ [异源驱动] 使用指定音色: {Path(narrator_input).name}")
                else:
                    logger.warning(
                        f"⚠️ 指定的旁白文件不存在: {narrator_input}，回退到原声"
                    )

            # 调用 IndexTTS2 推理
            self.model.infer(
                text=text,
                spk_audio_prompt=spk_audio,  # 音色
                emo_audio_prompt=emo_audio,  # 情绪/韵律
                output_path=output_wav_path,
                verbose=False,  # 减少刷屏
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
    def __init__(self, narrator_input=None):
        SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.tts = LocalTTSWrapper()
        self.audio_mgr = AudioManager(AUDIO_LIB_DIR)
        self.final_track = AudioSegment.empty()

        # 保存用户指定的旁白文件路径
        self.narrator_input = narrator_input
        if self.narrator_input:
            logger.info(f"🎙️ 已启用旁白音色替换: {self.narrator_input}")

    def run(self):
        if not PLAYLIST_FILE.exists():
            logger.error(f"找不到 {PLAYLIST_FILE}")
            return

        with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
            playlist = json.load(f)

        logger.info(f"📂 开始处理 {len(playlist)} 个任务...")

        for item in playlist:
            seq = item["seq"]
            type_ = item["type"]

            if type_ == "sfx":
                logger.info(f"[{seq}] 🎵 音效: {item['content']}")
                sfx = AudioSegment.silent(duration=2000)
                self.final_track += sfx

            elif type_ == "speech":
                text = item["text"]
                role = item["role"]
                ref_info = item["ref_audio"]

                original_path = ref_info.get("path", "")
                file_id = ref_info.get("id", "")
                real_ref_path = self.audio_mgr.find_path(file_id, original_path)

                if not real_ref_path:
                    logger.error(f"❌ 找不到参考音频 (ID: {file_id})，跳过")
                    self.final_track += AudioSegment.silent(duration=1000)
                    continue

                emotion = item["tts_params"]["emotion"]
                out_path = SEGMENTS_DIR / f"{seq:03d}_{role}.wav"

                logger.info(f"[{seq}] 🎙️ 合成: {role} -> {text[:15]}...")

                # [修改] 传递 narrator_input 和 role 参数
                success = self.tts.synthesize(
                    text=text,
                    ref_audio_path=real_ref_path,
                    emotion=emotion,
                    output_wav_path=str(out_path),
                    narrator_input=self.narrator_input,  # 传入指定音色
                    role=role,  # 传入角色名以便判断
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

        logger.info("💾 正在渲染最终文件...")
        FINAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.final_track.export(FINAL_FILE, format="wav")
        logger.info(f"🎉 任务完成! 文件路径: {FINAL_FILE}")


# ============================================================================
# 6. 入口函数
# ============================================================================
if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="有声书合成工兵")
    parser.add_argument(
        "--narrator_input",
        type=str,
        default=None,
        help="[可选] 指定旁白角色的音色参考音频路径 (覆盖默认音色)",
    )

    args = parser.parse_args()

    worker = TTSWorker(narrator_input=args.narrator_input)
    worker.run()
