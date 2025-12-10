"""
TTS Audio Matcher V2.2 - Prosody-First, Timbre-Safe
核心逻辑回归本质：韵律为王，音色维稳。
L1: 身份与物理过滤 -> L2: 韵律优先加权打分 -> L3: 强制出演决策
"""

import re
from typing import Dict, List, Tuple, Optional
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from config import (
    SCORING_WEIGHTS,
    SAFE_VOCAL_MODES,
    EXTREME_VOCAL_MODES,
    DURATION_RATIO_RED_ZONE_MAX,
    DURATION_RATIO_RED_ZONE_MIN,
    DURATION_RATIO_PENALTY_MAX,
    DURATION_RATIO_PENALTY_MIN,
    SCORE_TIMBRE_SAFETY_PENALTY,
    MAX_RAW_PROSODY_SCORE,
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
    def __init__(self, audio_library: List[Dict]):
        self.audio_library = audio_library
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        # 预计算向量
        for audio in self.audio_library:
            if "semantic_desc" in audio and "vector_embedding" not in audio:
                audio["vector_embedding"] = self.model.encode(audio["semantic_desc"])

    def get_best_match(self, target_node: Dict) -> Dict:
        """主入口：获取最佳匹配"""

        # L1: 身份过滤 (角色ID + 物理红线)
        candidates = self._filter_l1_hard_rules(target_node)

        if not candidates:
            return self._get_anchor_audio("L1", "No candidates passed L1 filters")

        # L2: 加权打分 (V2.2 核心算法)
        scored_candidates = self._calculate_scores_v2_2(target_node, candidates)

        # 排序
        scored_candidates.sort(key=lambda x: x["total_score"], reverse=True)

        # L3: 决策 (V3.0 强制出演逻辑)
        return self._make_decision(scored_candidates)

    def _filter_l1_hard_rules(self, target_node: Dict) -> List[Dict]:
        """L1: 硬规则过滤 (角色 + 物理红线 + 性别)"""
        target_role = target_node.get("role_tag", "")
        text = target_node.get("text", "")
        target_duration = self._estimate_text_duration(text)

        # TODO: 如果未来加上性别字段，在这里添加 Gender Gate 逻辑
        # target_gender = target_node.get("gender", "unknown")

        filtered = []
        for audio in self.audio_library:
            # 1. 角色一致性
            if audio.get("role", "") != target_role:
                continue

            # 2. 物理时长约束 (红线剔除)
            ref_duration = audio.get("duration", 1.0)
            ratio = target_duration / ref_duration if ref_duration > 0 else 999

            if (
                ratio > DURATION_RATIO_RED_ZONE_MAX
                or ratio < DURATION_RATIO_RED_ZONE_MIN
            ):
                continue

            # 3. 标记惩罚区 (不剔除，留给 L2 扣分)
            is_duration_penalty = (
                ratio > DURATION_RATIO_PENALTY_MAX or ratio < DURATION_RATIO_PENALTY_MIN
            )

            # 创建副本以免污染原库
            candidate = audio.copy()
            candidate["_calc_ratio"] = ratio
            candidate["_is_duration_penalty"] = is_duration_penalty
            filtered.append(candidate)

        return filtered

    def _calculate_scores_v2_2(
        self, target_node: Dict, candidates: List[Dict]
    ) -> List[Dict]:
        """
        L2: V2.2 韵律优先打分逻辑
        Formula: Total = (W_p * S_p) + (W_v * S_v) + S_safety - P_noise
        """
        role_type = (
            "narrator" if target_node.get("role_tag") == "narrator" else "character"
        )
        weights = SCORING_WEIGHTS.get(role_type, SCORING_WEIGHTS["character"])

        scored = []
        for audio in candidates:
            score_breakdown = {}

            # 1. 韵律得分 (归一化到 0-100)
            raw_prosody = self._score_prosody(target_node, audio)
            # 将 0-30 的分值映射到 0-100
            norm_prosody = min(100, (raw_prosody / MAX_RAW_PROSODY_SCORE) * 100)
            final_prosody = norm_prosody * weights["prosody"]
            score_breakdown["prosody"] = final_prosody

            # 2. 向量得分 (0-100)
            raw_vector = self._score_vector(target_node, audio)  # 返回 0-100
            final_vector = raw_vector * weights["vector"]
            score_breakdown["vector"] = final_vector

            # 3. 音色安全系数 (仅 Narrator 生效，只减不加)
            safety_bonus = 0
            if role_type == "narrator":
                safety_bonus = self._calculate_safety_bonus(target_node, audio)
            score_breakdown["timbre_safety"] = safety_bonus

            # 4. 净度惩罚
            noise_penalty = self._calculate_noise_penalty(target_node, audio)
            score_breakdown["noise_penalty"] = noise_penalty

            # 5. 时长惩罚
            dur_penalty = PENALTY_DURATION if audio.get("_is_duration_penalty") else 0
            score_breakdown["duration_penalty"] = dur_penalty

            # === 总分计算 ===
            total_score = (
                final_prosody
                + final_vector
                + safety_bonus
                + noise_penalty
                + dur_penalty
            )

            result = audio.copy()
            result["total_score"] = total_score
            result["score_breakdown"] = score_breakdown
            scored.append(result)

        return scored

    def _calculate_safety_bonus(self, target_node: Dict, audio: Dict) -> int:
        """
        V2.2 核心：音色安全区检查
        如果不安全，扣分；如果安全，不加分。
        """
        target_mode = target_node.get("timbral", {}).get("vocal_mode", "")
        audio_mode = audio.get("vocal_mode", "")

        # 如果音频处于“极端风险区” (Extreme)
        if audio_mode in EXTREME_VOCAL_MODES:
            # 除非文本显式要求了这个怪异音色，否则视为污染
            if target_mode != audio_mode:
                return SCORE_TIMBRE_SAFETY_PENALTY

        # 其他情况（安全音色 或 显式要求的怪音色）均不扣分
        return 0

    def _score_prosody(self, target_node: Dict, audio: Dict) -> int:
        """计算原始韵律分 (0 - 30)"""
        score = 0
        prosodic = target_node.get("prosodic", {})

        # 1. 能量匹配 (+15)
        t_energy = prosodic.get("energy_level", 0)
        a_energy = audio.get("energy_level", 0)
        if abs(t_energy - a_energy) <= ENERGY_LEVEL_TOLERANCE:
            score += 15

        # 2. 语调匹配 (+15)
        if prosodic.get("pitch_curve") == audio.get("pitch_curve"):
            score += 15

        return score

    def _score_vector(self, target_node: Dict, audio: Dict) -> float:
        """计算向量相似度 (0 - 100)"""
        target_desc = target_node.get("semantic_vector_desc", "")
        audio_vec = audio.get("vector_embedding", [])

        if not target_desc or audio_vec is None or len(audio_vec) == 0:
            return 0.0

        target_vec = self.model.encode(target_desc).reshape(1, -1)
        audio_vec = np.array(audio_vec).reshape(1, -1)

        similarity = cosine_similarity(target_vec, audio_vec)[0][0]
        return max(0.0, float(similarity) * 100)  # 映射到 0-100

    def _calculate_noise_penalty(self, target_node: Dict, audio: Dict) -> int:
        """净度惩罚"""
        physiological = target_node.get("physiological", {})
        mouth = physiological.get("mouth_artifact", "")
        breath = physiological.get("breath_mark", "none")
        audio_tags = audio.get("tags", [])

        if mouth == "clean":
            has_noise = any(tag in NOISE_TAGS for tag in audio_tags)
            # 呼吸声豁免权
            if breath != "none" and "breath" in audio_tags:
                return 0
            if has_noise:
                return PENALTY_NOISE
        return 0

    def _make_decision(self, scored_candidates: List[Dict]) -> Dict:
        """L3: 决策 (强制出演逻辑)"""
        if not scored_candidates:
            return self._get_anchor_audio("L3", "All filtered by physics")

        best = scored_candidates[0]
        score = best["total_score"]

        if score >= LEVEL1_THRESHOLD:
            best["match_level"] = "Level 1: Perfect Clone"
        elif score >= LEVEL2_THRESHOLD:
            best["match_level"] = "Level 2: Safe Clone"
        else:
            best["match_level"] = "Level 3: Forced Imperfect"
            best["fallback_reason"] = f"Low score ({score:.1f}) but forced actor"

        return best

    def _get_anchor_audio(self, stage: str, reason: str) -> Dict:
        return {
            "id": "anchor_default",
            "role": "universal",
            "duration": 4.0,
            "path": ANCHOR_AUDIO_PATH,  # 注意字段名统一
            "match_level": "Level 3: Anchor Fallback",
            "fallback_reason": f"[{stage}] {reason}",
            "total_score": 0,
        }

    def _estimate_text_duration(self, text: str) -> float:
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        punct = len(
            re.findall(r'[，。！？、；：""' "（）《》【】…—,.!?;:\"'\(\)\[\]\-]", text)
        )
        return chinese * DURATION_CHINESE_CHAR + punct * DURATION_PUNCTUATION

    def print_match_result(self, result: Dict, target_node: Dict):
        """调试打印"""
        print("-" * 60)
        print(f"Text: {target_node.get('text', '')[:30]}...")
        print(
            f"Role: {target_node.get('role_tag')} | Target Mode: {target_node.get('timbral', {}).get('vocal_mode')}"
        )
        print(f"Match: {result.get('id')} | Score: {result.get('total_score', 0):.1f}")
        print(f"Breakdown: {result.get('score_breakdown')}")
