"""
Configuration for Audio Matcher V2.2 (Prosody-First, Timbre-Safe)
"""

# === 核心权重配置 (V2.2 新增) ===
# 这里的权重用于归一化后的得分 (0-100分制)
# Narrator: 韵律 50%, 向量 50%, 音色只做减法
# Character: 向量 60% (戏感), 韵律 40%, 音色忽略
SCORING_WEIGHTS = {
    "narrator": {"prosody": 0.5, "vector": 0.5},
    "character": {"prosody": 0.4, "vector": 0.6},
}

# === 音色安全区配置 (V2.2 新增) ===
# 旁白模式下的“安全音色” (Standard Modes)
SAFE_VOCAL_MODES = ["modal_warm", "modal_bright", "storytelling_standard", "neutral"]

# 旁白模式下的“风险音色” (Extreme Modes)
# 如果目标没要求，但素材是这些，就要扣分
EXTREME_VOCAL_MODES = [
    "fry_creak",
    "nasal_squeak",
    "rough_gravel",
    "breathy_airy",
    "whisper",
]

# === 降级映射表 (保留，用于特殊情况判断) ===
VOCAL_MODE_FALLBACK_MAP = {
    "nasal_squeak": ["modal_bright", "modal_warm"],
    "fry_creak": ["rough_gravel", "modal_warm"],
    "breathy_airy": ["modal_warm"],
    "hollow": ["modal_warm"],
    "modal_warm": ["rough_gravel", "modal_bright"],  # 允许反差萌
}

# === 阈值与惩罚分 ===
LEVEL1_THRESHOLD = 80
LEVEL2_THRESHOLD = 60

# 物理约束比率 (Ratio = Target / Reference)
DURATION_RATIO_RED_ZONE_MAX = 6.0
DURATION_RATIO_RED_ZONE_MIN = 0.1
DURATION_RATIO_PENALTY_MAX = 4.0
DURATION_RATIO_PENALTY_MIN = 0.2

# 基础时长参数
DURATION_CHINESE_CHAR = 0.25  # 秒/字
DURATION_PUNCTUATION = 0.4  # 秒/标点

# 容差
ENERGY_LEVEL_TOLERANCE = 1

# === 得分与惩罚数值 ===
# 注意：V2.2 中，音色不再加分，只扣分
SCORE_TIMBRE_SAFETY_PENALTY = -30  # 风险音色惩罚
PENALTY_NOISE = -50  # 噪音惩罚
PENALTY_DURATION = -30  # 时长不合适惩罚

# 韵律打分满分基准 (用于归一化)
MAX_RAW_PROSODY_SCORE = 30

# 噪音标签
NOISE_TAGS = ["smack_lips", "click", "background_noise", "noise", "plosive"]

# 兜底文件路径
ANCHOR_AUDIO_PATH = "audio_library/anchor/modal_warm_stable.wav"
