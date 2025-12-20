"""
TTS Worker (V2.0 Optimized) - 极简高效版
适配环境：AutoDL / Linux Server with Index-TTS2
功能：
1. 直接利用 JSON 中的 path 字段，无需扫描全盘。
2. 支持 --narrator_input 异源驱动。
3. 依然保留 pydub 渲染管线。
"""

import json
import os
import sys
import time
import logging
import argparse
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

# 注意：这里需要你手动修改一次 production_playlist.json 的文件名
# 或者你可以通过命令行参数传入 playlist 路径 (更灵活)
PLAYLIST_FILE = DATA_ROOT / "story/production_playlist_Ep01_20251210_140126.json"
OUTPUT_DIR = DATA_ROOT / "output"
SEGMENTS_DIR = OUTPUT_DIR / "segments"
FINAL_FILE = OUTPUT_DIR / "story/final_audiobook_Ep01.wav"

ANCHOR_DIR = DATA_ROOT / "audio_library/anchor"

FADE_MS = 10
INTERVAL_MS = 500

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("LocalWorker")


# ============================================================================
# 3. 模型封装类 (LocalTTSWrapper)
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
        try:
            # 检查参考音频是否存在
            if not ref_audio_path or not os.path.exists(ref_audio_path):
                logger.error(f"❌ 参考音频无法访问: {ref_audio_path}")
                return False

            # === [异源驱动逻辑] ===
            spk_audio = ref_audio_path
            emo_audio = ref_audio_path

            if role == "narrator" and narrator_input:
                if os.path.exists(narrator_input):
                    spk_audio = narrator_input  # 替换音色
                else:
                    logger.warning(f"⚠️ 指定旁白文件不存在: {narrator_input}")

            # 调用 IndexTTS2 推理
            self.model.infer(
                text=text,
                spk_audio_prompt=spk_audio,
                emo_audio_prompt=emo_audio,
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
# 4. 主工兵逻辑
# ============================================================================
class TTSWorker:
    def __init__(self, playlist_path=None, narrator_input=None):
        SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.tts = LocalTTSWrapper()
        self.final_track = AudioSegment.empty()

        # 允许通过参数指定 playlist，否则用默认值
        self.playlist_file = Path(playlist_path) if playlist_path else PLAYLIST_FILE
        self.narrator_input = narrator_input

        if self.narrator_input:
            logger.info(f"🎙️ 已启用旁白音色替换: {self.narrator_input}")

    def run(self):
        if not self.playlist_file.exists():
            logger.error(f"找不到播放列表: {self.playlist_file}")
            # 尝试在上一级目录找找看（兼容性处理）
            alt_path = Path("..") / self.playlist_file.name
            if alt_path.exists():
                logger.info(f"🔄 在上级目录找到了: {alt_path}")
                self.playlist_file = alt_path
            else:
                return

        with open(self.playlist_file, "r", encoding="utf-8") as f:
            playlist = json.load(f)

        logger.info(f"📂 读取列表: {self.playlist_file.name} ({len(playlist)} 条任务)")

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

                # [核心简化] 直接使用 JSON 里的相对路径
                # 假设 JSON 里存的是 "role_audio/narrator/xxx.wav"
                # 我们只需要拼上 DATA_ROOT 即可
                json_path = ref_info.get("path", "")

                # 如果是 anchor (通常没有相对路径)，特殊处理
                if "anchor" in json_path or "anchor" in ref_info.get("id", ""):
                    # 假设 anchor 固定在 audio_library/anchor 下
                    real_ref_path = (
                        ANCHOR_DIR / "modal_warm_stable.wav"
                    )  # 或者根据 ID 找
                else:
                    real_ref_path = DATA_ROOT / json_path

                # 转为绝对路径字符串
                abs_ref_path = str(real_ref_path.resolve())

                if not os.path.exists(abs_ref_path):
                    logger.error(f"❌ 路径无效: {abs_ref_path}")
                    self.final_track += AudioSegment.silent(duration=1000)
                    continue

                emotion = item["tts_params"]["emotion"]
                out_path = SEGMENTS_DIR / f"{seq:03d}_{role}.wav"

                logger.info(f"[{seq}] 🎙️ 合成: {role} -> {text[:15]}...")

                success = self.tts.synthesize(
                    text=text,
                    ref_audio_path=abs_ref_path,
                    emotion=emotion,
                    output_wav_path=str(out_path),
                    narrator_input=self.narrator_input,
                    role=role,
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--narrator_input", type=str, help="旁白音色文件")
    parser.add_argument("--playlist", type=str, help="指定的播放列表JSON路径")

    args = parser.parse_args()

    worker = TTSWorker(playlist_path=args.playlist, narrator_input=args.narrator_input)
    worker.run()
