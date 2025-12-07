"""
TTS Audio Matcher - 基于四层漏斗筛选机制的音频匹配引擎
L1: 身份过滤 -> L1.5: 物理约束 -> L2: 加权打分 -> L3: 兜底决策
"""

import re
from typing import Dict, List, Tuple, Optional
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from config import (
    VOCAL_MODE_FALLBACK_MAP,
    DURATION_RATIO_RED_ZONE_MAX,
    DURATION_RATIO_RED_ZONE_MIN,
    DURATION_RATIO_PENALTY_MAX,
    DURATION_RATIO_PENALTY_MIN,
    SCORE_TIMBRE_PERFECT,
    SCORE_TIMBRE_FALLBACK,
    SCORE_PROSODY_ENERGY,
    SCORE_PROSODY_PITCH,
    SCORE_VECTOR_MAX,
    PENALTY_NOISE,
    PENALTY_DURATION,
    LEVEL1_THRESHOLD,
    LEVEL2_THRESHOLD,
    DURATION_CHINESE_CHAR,
    DURATION_PUNCTUATION,
    ENERGY_LEVEL_TOLERANCE,
    NOISE_TAGS,
    ANCHOR_AUDIO_PATH,
)


class AudioMatcher:
    """
    音频匹配引擎类
    根据目标文本节点从音频库中检索最合适的参考音频
    """

    def __init__(self, audio_library: List[Dict]):
        """
        初始化音频匹配器

        Args:
            audio_library: 音频切片库列表
        """
        self.audio_library = audio_library

        # 初始化 Sentence Transformer 模型
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        # 预处理音频库：为缺少 vector_embedding 的项生成嵌入
        for audio in self.audio_library:
            if "semantic_desc" in audio and "vector_embedding" not in audio:
                # 生成语义向量并存储
                audio["vector_embedding"] = self.model.encode(audio["semantic_desc"])

    def get_best_match(self, target_node: Dict) -> Dict:
        """
        获取最佳匹配音频（主入口方法）

        Args:
            target_node: 目标文本节点

        Returns:
            最佳匹配的音频对象（包含匹配信息）
        """
        # L1: 身份过滤 - 角色匹配
        candidates = self._filter_by_role(target_node)

        if not candidates:
            return self._get_anchor_audio("L1", "No matching role found")

        # L1.5: 物理约束 - 时长检查
        candidates = self._filter_by_duration(target_node, candidates)

        if not candidates:
            return self._get_anchor_audio("L1.5", "Duration ratio out of red zone")

        # L2: 加权打分
        scored_candidates = self._calculate_scores(target_node, candidates)

        # 按分数降序排序
        scored_candidates.sort(key=lambda x: x["total_score"], reverse=True)

        # L3: 决策分发
        return self._make_decision(scored_candidates)

    def _filter_by_role(self, target_node: Dict) -> List[Dict]:
        """
        L1: 身份过滤 - 严格匹配角色标签

        Args:
            target_node: 目标文本节点

        Returns:
            角色匹配的候选音频列表
        """
        target_role = target_node.get("role_tag", "")

        # 过滤出角色一致的音频
        matched = [
            audio
            for audio in self.audio_library
            if audio.get("role", "") == target_role
        ]

        return matched

    def _estimate_text_duration(self, text: str) -> float:
        """
        估算文本时长（秒）
        算法: (汉字数量 * 0.25) + (标点符号数量 * 0.4)

        Args:
            text: 目标文本

        Returns:
            估算时长（秒）
        """
        # 统计汉字数量（Unicode范围：\u4e00-\u9fff）
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))

        # 统计标点符号数量（中英文标点）
        punctuation_chars = len(
            re.findall(r'[，。！？、；：""' "（）《》【】…—,.!?;:\"'\(\)\[\]\-]", text)
        )

        # 计算总时长
        duration = (
            chinese_chars * DURATION_CHINESE_CHAR
            + punctuation_chars * DURATION_PUNCTUATION
        )

        return duration

    def _filter_by_duration(
        self, target_node: Dict, candidates: List[Dict]
    ) -> List[Dict]:
        """
        L1.5: 物理约束 - 时长检查与惩罚标记

        Args:
            target_node: 目标文本节点
            candidates: 候选音频列表

        Returns:
            通过物理约束检查的候选列表（标记了惩罚信息）
        """
        text = target_node.get("text", "")
        target_duration = self._estimate_text_duration(text)

        filtered = []

        for audio in candidates:
            ref_duration = audio.get("duration", 1.0)  # 默认1秒避免除零

            # 计算时长比率
            ratio = target_duration / ref_duration if ref_duration > 0 else 999

            # 红线区判定：直接剔除
            if (
                ratio > DURATION_RATIO_RED_ZONE_MAX
                or ratio < DURATION_RATIO_RED_ZONE_MIN
            ):
                continue

            # 惩罚区判定：标记但保留
            is_penalty = (
                ratio > DURATION_RATIO_PENALTY_MAX or ratio < DURATION_RATIO_PENALTY_MIN
            )

            # 添加惩罚标记到音频对象的副本
            audio_copy = audio.copy()
            audio_copy["is_penalty"] = is_penalty
            audio_copy["duration_ratio"] = ratio

            filtered.append(audio_copy)

        return filtered

    def _calculate_scores(
        self, target_node: Dict, candidates: List[Dict]
    ) -> List[Dict]:
        """
        L2: 加权打分引擎
        计算每个候选音频的总分 = 音色 + 韵律 + 语义向量 - 噪音惩罚 - 时长惩罚

        Args:
            target_node: 目标文本节点
            candidates: 候选音频列表

        Returns:
            包含分数信息的候选列表
        """
        scored = []

        for audio in candidates:
            score_breakdown = {}

            # 1. 音色得分 (满分40)
            timbre_score = self._score_timbre(target_node, audio)
            score_breakdown["timbre"] = timbre_score

            # 2. 韵律得分 (满分30)
            prosody_score = self._score_prosody(target_node, audio)
            score_breakdown["prosody"] = prosody_score

            # 3. 语义向量得分 (满分20)
            vector_score = self._score_vector(target_node, audio)
            score_breakdown["vector"] = vector_score

            # 4. 净度惩罚 (扣分项)
            noise_penalty = self._calculate_noise_penalty(target_node, audio)
            score_breakdown["noise_penalty"] = noise_penalty

            # 5. 时长惩罚 (L1.5遗留)
            duration_penalty = PENALTY_DURATION if audio.get("is_penalty", False) else 0
            score_breakdown["duration_penalty"] = duration_penalty

            # 计算总分
            total_score = (
                timbre_score
                + prosody_score
                + vector_score
                + noise_penalty
                + duration_penalty
            )

            # 构建结果对象
            result = audio.copy()
            result["score_breakdown"] = score_breakdown
            result["total_score"] = total_score

            scored.append(result)

        return scored

    def _score_timbre(self, target_node: Dict, audio: Dict) -> int:
        """
        计算音色匹配得分

        Args:
            target_node: 目标文本节点
            audio: 候选音频

        Returns:
            音色得分 (0/20/40)
        """
        target_vocal_mode = target_node.get("timbral", {}).get("vocal_mode", "")
        audio_vocal_mode = audio.get("vocal_mode", "")

        # 完美匹配
        if target_vocal_mode == audio_vocal_mode:
            return SCORE_TIMBRE_PERFECT

        # 降级匹配：检查是否在fallback映射中
        fallback_modes = VOCAL_MODE_FALLBACK_MAP.get(target_vocal_mode, [])
        if audio_vocal_mode in fallback_modes:
            return SCORE_TIMBRE_FALLBACK

        # 不匹配
        return 0

    def _score_prosody(self, target_node: Dict, audio: Dict) -> int:
        """
        计算韵律匹配得分

        Args:
            target_node: 目标文本节点
            audio: 候选音频

        Returns:
            韵律得分 (0-30)
        """
        score = 0
        prosodic = target_node.get("prosodic", {})

        # 1. 能量等级匹配 (容差±0.5)
        target_energy = prosodic.get("energy_level", 0)
        audio_energy = audio.get("energy_level", 0)

        if abs(target_energy - audio_energy) <= ENERGY_LEVEL_TOLERANCE:
            score += SCORE_PROSODY_ENERGY

        # 2. 音调曲线匹配
        target_pitch = prosodic.get("pitch_curve", "")
        audio_pitch = audio.get("pitch_curve", "")

        if target_pitch == audio_pitch:
            score += SCORE_PROSODY_PITCH

        return score

    def _score_vector(self, target_node: Dict, audio: Dict) -> float:
        """
        计算语义向量相似度得分

        Args:
            target_node: 目标文本节点
            audio: 候选音频

        Returns:
            向量得分 (0-20)
        """
        # 计算相似度（暂时使用模拟值）
        similarity = self._calc_similarity(
            target_node.get("semantic_vector_desc", ""),
            audio.get("vector_embedding", []),
        )

        return similarity * SCORE_VECTOR_MAX

    def _calc_similarity(self, target_desc: str, audio_vector: List) -> float:
        """
        辅助函数：计算语义相似度（使用余弦相似度）

        Args:
            target_desc: 目标文本语义描述
            audio_vector: 音频向量嵌入

        Returns:
            相似度 (0.0-1.0)
        """
        # 如果目标描述为空或音频向量为空，返回0
        if not target_desc or audio_vector is None or len(audio_vector) == 0:
            return 0.0

        # 编码目标文本
        target_vector = self.model.encode(target_desc)

        # 将向量转换为numpy数组并reshape为2D
        target_vector = np.array(target_vector).reshape(1, -1)
        audio_vector = np.array(audio_vector).reshape(1, -1)

        # 计算余弦相似度
        similarity = cosine_similarity(target_vector, audio_vector)[0][0]

        # 确保相似度为非负值（通常余弦相似度范围为-1到1，但对于这个模型通常是0到1）
        similarity = max(0.0, similarity)

        return float(similarity)

    def _calculate_noise_penalty(self, target_node: Dict, audio: Dict) -> int:
        """
        计算净度惩罚

        Args:
            target_node: 目标文本节点
            audio: 候选音频

        Returns:
            惩罚分数 (0 或 PENALTY_NOISE)
        """
        physiological = target_node.get("physiological", {})
        mouth_artifact = physiological.get("mouth_artifact", "")
        breath_mark = physiological.get("breath_mark", "none")

        audio_tags = audio.get("tags", [])

        # 目标要求干净
        if mouth_artifact == "clean":
            # 检查音频是否有噪音标签
            has_noise = any(tag in NOISE_TAGS for tag in audio_tags)

            # 豁免条件：目标需要呼吸声 且 音频包含呼吸声
            if breath_mark != "none" and "breath" in audio_tags:
                # 这是合理的生理特征，不扣分
                return 0

            # 有噪音则扣分
            if has_noise:
                return PENALTY_NOISE

        return 0

    def _make_decision(self, scored_candidates: List[Dict]) -> Dict:
        """
        L3: 决策分发 - 根据分数返回最终结果
        [V3.0 改进]: 引入"强制出演"逻辑。
        只要候选列表不为空，就必须返回其中分最高的一个，绝不退回 Anchor。
        """
        # 情况 1: 真的没救了 (库是空的，或者所有音频都因为时长太离谱被 L1.5 物理规则剔除了)
        if not scored_candidates:
            return self._get_anchor_audio(
                "L3", "No candidates available (all filtered by physics)"
            )

        # 取出分数最高的一个
        best = scored_candidates[0]
        best_score = best["total_score"]

        # Level 1: 完美匹配 (分数 >= 80)
        if best_score >= LEVEL1_THRESHOLD:
            best["match_level"] = "Level 1: Perfect Clone"

        # Level 2: 代偿匹配 (分数 >= 60)
        elif best_score >= LEVEL2_THRESHOLD:
            best["match_level"] = "Level 2: Cross-mode Compensation"

        # Level 3: 强制出演 (分数 < 60)
        # [核心修改]: 即使分数很低 (例如 0 分)，只要它是该角色库里的 Top 1，就强制使用它。
        else:
            best["match_level"] = "Level 3: Imperfect Match (Forced)"
            best["fallback_reason"] = (
                f"Score {best_score:.1f} is low, but forcing actor consistency."
            )

        return best

    def _get_anchor_audio(self, stage: str, reason: str) -> Dict:
        """
        返回默认锚点音频（兜底机制）

        Args:
            stage: 触发兜底的阶段 (L1/L1.5/L3)
            reason: 兜底原因

        Returns:
            锚点音频对象
        """
        return {
            "id": "anchor_default",
            "role": "universal",
            "duration": 4.0,
            "vocal_mode": "modal_warm",
            "energy_level": 2,
            "pitch_curve": "stable",
            "tags": ["clean"],
            "audio_path": ANCHOR_AUDIO_PATH,
            "match_level": "Level 3: Anchor Fallback",
            "fallback_stage": stage,
            "fallback_reason": reason,
            "total_score": 0,
            "score_breakdown": {},
        }

    def print_match_result(self, result: Dict, target_node: Dict):
        """
        打印匹配结果（便于调试和测试）

        Args:
            result: 匹配结果
            target_node: 目标文本节点
        """
        print("\n" + "=" * 60)
        print(f"目标文本: {target_node.get('text', '')[:40]}...")
        print(f"目标角色: {target_node.get('role_tag', '')}")
        print(f"目标音色: {target_node.get('timbral', {}).get('vocal_mode', '')}")
        print("-" * 60)
        print(f"匹配音频: {result.get('id', '')}")
        print(f"匹配等级: {result.get('match_level', '')}")
        print(f"总分: {result.get('total_score', 0):.2f}")

        if "score_breakdown" in result and result["score_breakdown"]:
            print("\n分数详情:")
            breakdown = result["score_breakdown"]
            print(f"  - 音色得分: {breakdown.get('timbre', 0)}")
            print(f"  - 韵律得分: {breakdown.get('prosody', 0)}")
            print(f"  - 语义得分: {breakdown.get('vector', 0):.2f}")
            print(f"  - 噪音惩罚: {breakdown.get('noise_penalty', 0)}")
            print(f"  - 时长惩罚: {breakdown.get('duration_penalty', 0)}")

        if "fallback_reason" in result:
            print(f"\n兜底原因: {result.get('fallback_reason', '')}")
            print(f"兜底阶段: {result.get('fallback_stage', '')}")

        if "duration_ratio" in result:
            print(f"\n时长比率: {result.get('duration_ratio', 0):.2f}")

        print("=" * 60)
