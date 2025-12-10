"""
Audio Metadata Cleaning Script (V4.2 Recursive & Relative Path Edition)
功能：
1. 递归扫描输入目录下的所有 JSON 文件。
2. 递归扫描音频目录，建立全局索引。
3. 注入相对路径 (Relative Path)，确保跨平台可用。
"""

import json
import logging
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

# Third-party imports
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError:
    pass

# ============================================================================
# CONFIGURATION
# ============================================================================

GOLDEN_SCHEMA = {
    "id": str,
    "role": str,
    "text": str,
    "duration": float,
    "file_path": str,
    "vocal_mode": str,
    "energy_level": int,
    "pitch_curve": str,
    "tags": list,
    "semantic_desc": str,
    "semantic_vector": list,
    "source": str,
}

FIELD_PRIORITY_MAP = {
    "id": ["id", "filename"],
    "role": ["role", "role_tag", "character"],
    "text": ["text", "content", "transcript"],
    "duration": ["duration", "length"],
    "vocal_mode": ["vocal_mode", "timbral.vocal_mode"],
    "energy_level": ["energy_level", "prosodic.energy_level"],
    "pitch_curve": ["pitch_curve", "prosodic.pitch_curve"],
    "tags": ["tags", "physiological.mouth_artifact"],
    "semantic_desc": ["semantic_desc", "semantic_vector_desc"],
    "file_path": ["file_path", "path"],
    "source": ["source"],
}

DEFAULT_VALUES = {
    "id": None,
    "role": "narrator",
    "text": "",
    "duration": 0.0,
    "file_path": "",
    "vocal_mode": "modal_warm",
    "energy_level": 3,
    "pitch_curve": "stable",
    "tags": ["clean"],
    "semantic_desc": "",
    "semantic_vector": [],
    "source": "unknown",
}

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA CLASSES (必须放在使用它们的函数之前)
# ============================================================================


@dataclass
class TransformStats:
    total: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0


# ============================================================================
# FILE SCANNER
# ============================================================================


class FileScanner:
    def __init__(self, root_dir: Optional[str] = None):
        self.file_map = {}
        # 获取当前运行脚本的工作目录作为基准
        self.base_cwd = Path.cwd()
        if root_dir:
            self.scan(root_dir)

    def scan(self, root_dir: str):
        path_obj = Path(root_dir)
        if not path_obj.exists():
            logger.warning(f"⚠️ 扫描目录不存在: {root_dir}")
            return

        logger.info(f"🔍 正在建立文件索引: {root_dir} ...")
        logger.info(f"   (基准路径: {self.base_cwd})")

        count = 0
        # 递归扫描所有音频文件 (.wav, .mp3, .flac)
        for p in path_obj.rglob("*"):
            if p.is_file() and p.suffix.lower() in [".wav", ".mp3", ".flac"]:
                try:
                    # 计算相对路径
                    relative_path = p.absolute().relative_to(self.base_cwd)
                    self.file_map[p.name] = str(relative_path)
                except ValueError:
                    # 如果文件不在项目目录下，存绝对路径
                    self.file_map[p.name] = str(p.absolute())
                count += 1
        logger.info(f"✅ 索引建立完成，共找到 {count} 个音频文件")

    def find_path(self, filename: str) -> str:
        # 1. 精确匹配
        if filename in self.file_map:
            return self.file_map[filename]
        # 2. 尝试加后缀匹配
        if not filename.endswith(".wav"):
            if f"{filename}.wav" in self.file_map:
                return self.file_map[f"{filename}.wav"]
        return ""


# ============================================================================
# VECTORIZER
# ============================================================================


class Vectorizer:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None

    def encode(self, text: str) -> List[float]:
        if not text:
            return []
        if not self.model:
            self.model = SentenceTransformer(self.model_name)
        embedding = self.model.encode(text, convert_to_numpy=True)
        return [round(float(x), 6) for x in embedding.tolist()]


# ============================================================================
# TOOL FUNCTIONS
# ============================================================================


def flatten_json_objects(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        return [data]
    flat_list = []
    if isinstance(data, list):
        for item in data:
            flat_list.extend(flatten_json_objects(item))
    return flat_list


def flatten_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    if not isinstance(value, list):
        return [str(value)]
    result = []
    for item in value:
        if isinstance(item, list):
            result.extend(flatten_list(item))
        else:
            result.append(str(item))
    return result


def safe_cast(value: Any, target_type: type, default: Any = None) -> Any:
    try:
        return target_type(value) if value is not None else default
    except:
        return default


def extract_field_with_priority(
    raw_data: Dict[str, Any], field_name: str, target_type: type = str
) -> Any:
    alternatives = FIELD_PRIORITY_MAP.get(field_name, [field_name])
    for alt_name in alternatives:
        value = raw_data
        if "." in alt_name:
            keys = alt_name.split(".")
            try:
                for k in keys:
                    value = value[k]
            except:
                continue
        else:
            if alt_name not in raw_data:
                continue
            value = raw_data[alt_name]
        return safe_cast(value, target_type, None)
    return None


def extract_duration(raw_data: Dict[str, Any]) -> float:
    duration = extract_field_with_priority(raw_data, "duration", float)
    if duration is None and "timestamp" in raw_data:
        ts = raw_data["timestamp"]
        if isinstance(ts, dict) and "start" in ts and "end" in ts:
            try:

                def parse(t):
                    m, s = t.split(":")
                    return float(m) * 60 + float(s)

                duration = parse(ts["end"]) - parse(ts["start"])
            except:
                pass
    return max(0.0, duration) if duration else DEFAULT_VALUES["duration"]


def extract_tags(raw_data: Dict[str, Any], tag_field: str) -> List[str]:
    return flatten_list(extract_field_with_priority(raw_data, tag_field, list))


def generate_fallback_id(data: Dict[str, Any]) -> str:
    seed = str(data.get("text", "")) + str(data.get("role", ""))
    return hashlib.md5(seed.encode()).hexdigest()


# ============================================================================
# CORE LOGIC
# ============================================================================


def transform_item(
    raw_item: Dict[str, Any],
    vectorizer: Optional[Vectorizer],
    source_name: str,
    scanner: Optional[FileScanner],
) -> Optional[Dict[str, Any]]:
    try:
        output = {}
        output["id"] = extract_field_with_priority(
            raw_item, "id", str
        ) or generate_fallback_id(raw_item)
        output["role"] = (
            extract_field_with_priority(raw_item, "role", str) or DEFAULT_VALUES["role"]
        )
        output["text"] = (
            extract_field_with_priority(raw_item, "text", str) or DEFAULT_VALUES["text"]
        )

        # [Path Injection]
        original_path = extract_field_with_priority(raw_item, "file_path", str)
        scanned_path = scanner.find_path(output["id"]) if scanner else ""

        if scanned_path:
            output["file_path"] = scanned_path
        elif original_path:
            output["file_path"] = original_path
        else:
            output["file_path"] = ""

        output["duration"] = extract_duration(raw_item)
        output["vocal_mode"] = (
            extract_field_with_priority(raw_item, "vocal_mode", str)
            or DEFAULT_VALUES["vocal_mode"]
        )
        output["energy_level"] = (
            extract_field_with_priority(raw_item, "energy_level", int)
            or DEFAULT_VALUES["energy_level"]
        )
        output["pitch_curve"] = (
            extract_field_with_priority(raw_item, "pitch_curve", str)
            or DEFAULT_VALUES["pitch_curve"]
        )
        output["tags"] = extract_tags(raw_item, "tags")

        desc = extract_field_with_priority(raw_item, "semantic_desc", str)
        output["semantic_desc"] = desc or ""
        output["semantic_vector"] = (
            vectorizer.encode(desc) if (vectorizer and desc) else []
        )
        output["source"] = source_name
        return output
    except Exception as e:
        logger.error(f"Transform failed: {e}")
        return None


def process_file(
    input_file: Path, output_file: Path, vectorizer, scanner, source
) -> TransformStats:
    stats = TransformStats()
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = flatten_json_objects(json.load(f))

        logger.info(f"Processing {input_file.name} ({len(data)} items)...")
        results = []

        for item in data:
            if not isinstance(item, dict):
                stats.skipped += 1
                continue
            res = transform_item(item, vectorizer, source or input_file.stem, scanner)
            if res:
                results.append(res)
                stats.successful += 1
            else:
                stats.failed += 1

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {stats.successful} items to {output_file}")
        stats.total = len(data)
    except Exception as e:
        logger.error(f"Error processing {input_file}: {e}")
        stats.failed = 1
    return stats


def batch_process_directory(
    input_dir: Path,
    output_dir: Path,
    use_vectorizer: bool = True,
    model_name: str = "all-MiniLM-L6-v2",
    path_prefix: str = "",
) -> Dict[str, TransformStats]:
    logger.info(f"🚀 启动递归批处理: {input_dir}")

    # 如果没传 path_prefix (scan-dir)，则默认扫描 input_dir
    scan_root = path_prefix if path_prefix else input_dir
    scanner = FileScanner(str(scan_root))

    vectorizer = None
    if use_vectorizer:
        try:
            vectorizer = Vectorizer(model_name)
        except:
            logger.warning("Vector generation disabled")

    # [关键] 递归查找所有 JSON 文件
    json_files = list(input_dir.rglob("*.json"))

    if not json_files:
        logger.warning(f"⚠️ 在 {input_dir} 及其子目录下未找到任何 .json 文件！")
        return {}

    logger.info(f"📂 发现 {len(json_files)} 个 JSON 文件，开始处理...")

    results = {}
    for jf in json_files:
        # 防止重名覆盖：输出文件名 = "父文件夹名_原文件名"
        if jf.parent == input_dir:
            out_name = jf.name
        else:
            out_name = f"{jf.parent.name}_{jf.name}"

        source_tag = jf.parent.name
        stats = process_file(jf, output_dir / out_name, vectorizer, scanner, source_tag)
        results[jf.name] = stats

    return results


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input JSON file or directory")
    parser.add_argument("output", help="Output JSON file or directory")
    parser.add_argument("--scan-dir", help="Root directory to scan for audio files")
    parser.add_argument("--source", help="Source tag name")
    parser.add_argument("--no-vectors", action="store_true")
    parser.add_argument("--model", default="all-MiniLM-L6-v2")

    # 兼容旧参数 path-prefix, 实际指向 scan-dir
    parser.add_argument("--path-prefix", help="Alias for --scan-dir")

    args = parser.parse_args()

    # 统一参数
    scan_dir = args.scan_dir or args.path_prefix
    input_p = Path(args.input)
    output_p = Path(args.output)

    if input_p.is_file():
        scanner = FileScanner(scan_dir) if scan_dir else None
        vectorizer = Vectorizer(args.model) if not args.no_vectors else None
        process_file(input_p, output_p, vectorizer, scanner, args.source)

    elif input_p.is_dir():
        batch_process_directory(
            input_p, output_p, not args.no_vectors, args.model, path_prefix=scan_dir
        )
