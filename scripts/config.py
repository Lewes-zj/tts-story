"""
TTS Audio Matcher 配置文件
包含音色降级映射和常量定义
"""

# 音色模式降级映射表
VOCAL_MODE_FALLBACK_MAP = {
    "nasal_squeak": ["modal_bright", "modal_warm"],
    "fry_creak": ["rough_gravel", "modal_warm"],
    "breathy_airy": ["modal_warm"],
    "hollow": ["modal_warm"],
    # [新增] 允许 "modal_warm" (温暖) 降级匹配到 "rough_gravel" (粗糙)
    # 这样熊大演暖男时，能拿 20 分 (降级分)，而不是 0 分。
    # 这有助于在多个粗糙音频中，选出那个相对不那么离谱的。
    "modal_warm": ["rough_gravel", "modal_bright"],
}

# L1.5 物理约束阀值
## 如果你的熊大库里全是长音频（5秒+），而剧本里有很多短词（如“嘘”），可能会导致 $R < 0.2$，从而在 L1.5 阶段就被剔除了，导致 scored_candidates 为空，最终还是触发 Anchor。
## 所以这里放宽了 L1.5 的限制，允许 $R < 0.2$ 的音频通过。
# DURATION_RATIO_RED_ZONE_MAX = 4.0  # 红线区：比率超过此值直接剔除
# DURATION_RATIO_RED_ZONE_MIN = 0.2  # 红线区：比率低于此值直接剔除
DURATION_RATIO_RED_ZONE_MAX = 6.0  # 原来是 4.0
DURATION_RATIO_RED_ZONE_MIN = 0.1  # 原来是 0.2 (允许 0.5秒的字配 5秒的音)
DURATION_RATIO_PENALTY_MAX = 2.5  # 惩罚区：比率超过此值扣分
DURATION_RATIO_PENALTY_MIN = 0.4  # 惩罚区：比率低于此值扣分

# L2 打分权重
SCORE_TIMBRE_PERFECT = 40  # 音色完美匹配得分
SCORE_TIMBRE_FALLBACK = 20  # 音色降级匹配得分
SCORE_PROSODY_ENERGY = 15  # 韵律能量匹配得分
SCORE_PROSODY_PITCH = 15  # 韵律音调匹配得分
SCORE_VECTOR_MAX = 20  # 语义向量最高得分

# L2 惩罚分数
PENALTY_NOISE = -30  # 净度惩罚（噪音）
PENALTY_DURATION = -50  # 时长惩罚

# L3 决策阈值
LEVEL1_THRESHOLD = 80  # 完美匹配阈值
LEVEL2_THRESHOLD = 60  # 代偿匹配阈值

# 时长估算参数（秒/字符）
DURATION_CHINESE_CHAR = 0.25  # 每个汉字估算时长
DURATION_PUNCTUATION = 0.4  # 每个标点符号估算时长（包含气口）

# 韵律匹配容差
ENERGY_LEVEL_TOLERANCE = 0.5  # 能量等级匹配容差

# 噪音标签列表（用于判断是否需要扣分）
NOISE_TAGS = ["noise", "smack_lips", "chewing", "background_noise"]

# 默认锚点音频路径（兜底音频）
ANCHOR_AUDIO_PATH = "audio_library/anchor/modal_warm_stable.wav"
