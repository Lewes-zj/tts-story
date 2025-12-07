"""
Audio Metadata Cleaning and Migration Script

This script cleans and migrates audio metadata JSON files from various sources
into a standardized format with vector embeddings.
"""

import json
import logging
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass

# Third-party imports
from sentence_transformers import SentenceTransformer
import numpy as np

# ============================================================================
# CONFIGURATION CONSTANTS (已适配 AudioMatcher V2.0)
# ============================================================================

# Golden schema: 必须与 AudioMatcher 的输入要求完全一致
GOLDEN_SCHEMA = {
    # === 1. 身份与物理属性 ===
    "id": str,  # 唯一标识 (文件名)
    "role": str,  # L1 身份门禁 (对应 adult_male_rough)
    "text": str,  # [新增] 原始台词 (用于调试和记录)
    "duration": float,  # L1.5 物理约束 (秒)
    "file_path": str,  # TTS 引擎读取音频的物理路径
    # === 2. 核心匹配参数 (L2 打分用) ===
    "vocal_mode": str,  # 音色 (rough_gravel)
    "energy_level": int,  # 能量 (1-5)
    "pitch_curve": str,  # 语调 (slide_up)
    "tags": list,  # 噪音/特征 (laugh_particle)
    # === 3. 语义向量 (L2 核心) ===
    "semantic_desc": str,  # 英文描述文本
    "semantic_vector": list,  # BERT 向量
    # === 4. 数据治理 ===
    "source": str,  # 来源标记 (xiongda)
}

# Field priority map: 映射 xiongda.json 到标准字段
FIELD_PRIORITY_MAP = {
    "id": ["id", "filename"],
    "role": ["role", "role_tag", "character"],
    "text": ["text", "content", "transcript", "caption"],  # [新增] 抓取文本
    "duration": ["duration", "length"],
    # === 关键字段映射 ===
    "vocal_mode": ["vocal_mode", "timbral.vocal_mode", "timbre"],
    "energy_level": ["energy_level", "prosodic.energy_level", "energy"],
    "pitch_curve": ["pitch_curve", "prosodic.pitch_curve", "pitch"],
    "tags": ["tags", "physiological.mouth_artifact"],
    "semantic_desc": ["semantic_desc", "semantic_vector_desc", "description"],
    "file_path": ["file_path", "path"],
    "source": ["source"],
}

# Default values
DEFAULT_VALUES = {
    "id": None,
    "role": "narrator",
    "text": "",  # 默认为空字符串
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

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================================
# TOOL FUNCTIONS
# ============================================================================


def flatten_json_objects(data: Any) -> List[Dict[str, Any]]:
    """Recursively flatten a nested list of dictionaries."""
    if isinstance(data, dict):
        return [data]

    flat_list = []
    if isinstance(data, list):
        for item in data:
            flat_list.extend(flatten_json_objects(item))
    return flat_list


def flatten_list(value: Any) -> List[str]:
    """
    Flatten a nested list or convert a single value to a list.

    Args:
        value: Input value (list, string, or other types)

    Returns:
        Flattened list of strings

    Examples:
        >>> flatten_list(["a", ["b", "c"]])
        ['a', 'b', 'c']
        >>> flatten_list("single")
        ['single']
        >>> flatten_list(["tag1", "tag2"])
        ['tag1', 'tag2']
    """
    if value is None:
        return []

    if isinstance(value, str):
        # Handle comma-separated strings
        if "," in value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return [value]

    if not isinstance(value, list):
        return [str(value)]

    result = []
    for item in value:
        if isinstance(item, list):
            result.extend(flatten_list(item))
        elif isinstance(item, str):
            if "," in item:
                result.extend([sub.strip() for sub in item.split(",") if sub.strip()])
            else:
                result.append(item)
        else:
            result.append(str(item))

    return result


def parse_timestamp(value: Any) -> Optional[str]:
    """
    Parse various timestamp formats into ISO 8601 format.

    Args:
        value: Input timestamp (string, int, or datetime object)

    Returns:
        ISO 8601 formatted timestamp string or None if parsing fails

    Examples:
        >>> parse_timestamp("2023-12-01 10:30:00")
        '2023-12-01T10:30:00'
        >>> parse_timestamp(1701426600)
        '2023-12-01T10:30:00'
        >>> parse_timestamp("invalid")
        None
    """
    if value is None:
        return None

    # If already a datetime object
    if isinstance(value, datetime):
        return value.isoformat()

    # If Unix timestamp (int or float)
    if isinstance(value, (int, float)):
        try:
            # Handle both seconds and milliseconds
            if value > 1e10:  # Likely milliseconds
                value = value / 1000
            return datetime.fromtimestamp(value).isoformat()
        except (ValueError, OSError):
            logger.warning(f"Invalid Unix timestamp: {value}")
            return None

    # If string, try various formats
    if isinstance(value, str):
        # List of common timestamp formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.isoformat()
            except ValueError:
                continue

        logger.warning(f"Could not parse timestamp: {value}")
        return None

    return None


def safe_cast(value: Any, target_type: type, default: Any = None) -> Any:
    """
    Safely cast a value to a target type with fallback to default.

    Args:
        value: Input value to cast
        target_type: Target type (int, float, str, bool, list, dict)
        default: Default value if casting fails

    Returns:
        Casted value or default

    Examples:
        >>> safe_cast("123", int)
        123
        >>> safe_cast("invalid", int, 0)
        0
        >>> safe_cast("3.14", float)
        3.14
    """
    if value is None:
        return default

    try:
        # Handle boolean conversion
        if target_type == bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "on")
            return bool(value)

        # Handle list conversion
        if target_type == list:
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                # Try to parse as JSON array
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass
                # Split by comma
                return [item.strip() for item in value.split(",") if item.strip()]
            return [value]

        # Handle dict conversion
        if target_type == dict:
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    pass
            return default

        # Handle numeric conversions
        if target_type in (int, float):
            if isinstance(value, str):
                # Remove common non-numeric characters
                cleaned = re.sub(r"[^\d.-]", "", value)
                if not cleaned:
                    return default
                return target_type(cleaned)
            return target_type(value)

        # Handle string conversion
        if target_type == str:
            return str(value)

        # Default casting
        return target_type(value)

    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to cast {value} to {target_type}: {e}")
        return default


def generate_fallback_id(data: Dict[str, Any]) -> str:
    """
    Generate a fallback ID based on audio metadata using MD5 hash.

    Args:
        data: Audio metadata dictionary

    Returns:
        Generated ID string (MD5 hash)

    Examples:
        >>> data = {"title": "test", "file_path": "/path/to/file.mp3"}
        >>> id1 = generate_fallback_id(data)
        >>> id2 = generate_fallback_id(data)
        >>> id1 == id2
        True
    """
    # Use file_path, title, and speaker to generate a unique ID
    components = [
        data.get("file_path", ""),
        data.get("title", ""),
        data.get("speaker", ""),
        data.get("duration", ""),
    ]

    content = "|".join(str(comp) for comp in components)
    return hashlib.md5(content.encode()).hexdigest()


# ============================================================================
# VECTORIZER CLASS
# ============================================================================


class Vectorizer:
    """
    Handles generation of semantic vector embeddings from text descriptions.
    Uses sentence-transformers library for generating embeddings.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the vectorizer with a specific model.

        Args:
            model_name: Name of the sentence-transformers model to use
        """
        self.model_name = model_name
        self.model = None
        logger.info(f"Initializing Vectorizer with model: {model_name}")

    def load_model(self):
        """
        Load the sentence transformer model.
        Lazy loading to avoid unnecessary model loading if not needed.
        """
        if self.model is None:
            try:
                logger.info(f"Loading sentence transformer model: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                logger.info("Model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {e}")
                raise

    def encode(self, text: str) -> List[float]:
        """
        Generate vector embedding from text.

        Args:
            text: Input text to encode

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If text is empty or None
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for encoding")
            return []

        # Ensure model is loaded
        self.load_model()

        try:
            # Generate embedding
            embedding = self.model.encode(text, convert_to_numpy=True)
            # Convert numpy array to list and round for cleaner storage
            return [round(float(x), 6) for x in embedding.tolist()]
        except Exception as e:
            logger.error(f"Failed to encode text: {e}")
            return []

    def batch_encode(self, texts: List[str]) -> List[List[float]]:
        """
        Generate vector embeddings for multiple texts (batch processing).

        Args:
            texts: List of input texts to encode

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter out empty texts
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            logger.warning("No valid texts to encode in batch")
            return []

        # Ensure model is loaded
        self.load_model()

        try:
            # Generate embeddings
            embeddings = self.model.encode(valid_texts, convert_to_numpy=True)
            # Convert to list of lists
            return [[round(float(x), 6) for x in emb.tolist()] for emb in embeddings]
        except Exception as e:
            logger.error(f"Failed to batch encode texts: {e}")
            return []

    def get_vector_dim(self) -> int:
        """
        Get the dimensionality of the embedding vectors.

        Returns:
            Dimension of the embedding vectors
        """
        self.load_model()
        return self.model.get_sentence_embedding_dimension()


# ============================================================================
# FIELD EXTRACTION LOGIC
# ============================================================================


def extract_field_with_priority(
    raw_data: Dict[str, Any], field_name: str, target_type: type = str
) -> Any:
    alternatives = FIELD_PRIORITY_MAP.get(field_name, [field_name])

    for alt_name in alternatives:
        # Fix: Support dot notation (e.g., "timbral.vocal_mode")
        value = raw_data
        if "." in alt_name:
            keys = alt_name.split(".")
            try:
                for k in keys:
                    value = value[k]
            except (KeyError, TypeError):
                continue  # Path not found
        else:
            if alt_name not in raw_data:
                continue
            value = raw_data[alt_name]

        return safe_cast(value, target_type, None)

    return None


def extract_duration(raw_data: Dict[str, Any]) -> float:
    # 1. Try direct extraction
    duration = extract_field_with_priority(raw_data, "duration", float)

    # 2. Fix: Try calculating from timestamp object
    if duration is None and "timestamp" in raw_data:
        ts = raw_data["timestamp"]
        if isinstance(ts, dict) and "start" in ts and "end" in ts:
            try:
                # Assuming format "MM:SS.ms"
                def parse_mins_secs(t_str):
                    mins, secs = t_str.split(":")
                    return float(mins) * 60 + float(secs)

                start = parse_mins_secs(ts["start"])
                end = parse_mins_secs(ts["end"])
                duration = end - start
            except Exception as e:
                logger.warning(f"Failed to calc duration from timestamp: {e}")

    if duration is None:
        return DEFAULT_VALUES["duration"]

    if duration > 1000:
        duration = duration / 1000.0
    return max(0.0, duration)


def extract_tags(raw_data: Dict[str, Any], tag_field: str) -> List[str]:
    """
    Extract and normalize tag fields (timbre_tags, prosody_tags).

    Args:
        raw_data: Raw input data dictionary
        tag_field: Field name ("timbre_tags" or "prosody_tags")

    Returns:
        List of tag strings
    """
    value = extract_field_with_priority(raw_data, tag_field, list)

    if value is None:
        return []

    # Flatten and clean the tags
    tags = flatten_list(value)

    # Remove empty strings and duplicates while preserving order
    seen = set()
    result = []
    for tag in tags:
        tag = str(tag).strip()
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)

    return result


# ============================================================================
# TRANSFORMATION FUNCTIONS
# ============================================================================


@dataclass
class TransformStats:
    """Statistics for tracking transformation process."""

    total: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def transform_item(
    raw_item: Dict[str, Any],
    vectorizer: Optional[Vectorizer] = None,
    source_name: str = "unknown",
) -> Optional[Dict[str, Any]]:
    """
    Transform a single raw metadata item to the golden schema.

    Args:
        raw_item: Raw metadata dictionary
        vectorizer: Vectorizer instance for generating embeddings
        source_name: Name of the data source

    Returns:
        Transformed metadata dictionary or None if transformation fails
    """
    try:
        # Initialize output with default values
        output = {}

        # Extract ID (with fallback generation)
        output["id"] = extract_field_with_priority(raw_item, "id", str)
        if not output["id"]:
            output["id"] = generate_fallback_id(raw_item)

        output["text"] = (
            extract_field_with_priority(raw_item, "text", str) or DEFAULT_VALUES["text"]
        )

        # Extract basic string fields
        output["role"] = (
            extract_field_with_priority(raw_item, "role", str) or DEFAULT_VALUES["role"]
        )
        output["file_path"] = (
            extract_field_with_priority(raw_item, "file_path", str)
            or DEFAULT_VALUES["file_path"]
        )

        # Extract numeric fields
        output["duration"] = extract_duration(raw_item)

        # Extract list fields (tags)
        # 直接提取 "tags"，脚本会自动去 FIELD_PRIORITY_MAP 里找 "physiological.mouth_artifact"
        output["tags"] = extract_tags(raw_item, "tags")

        # Extract semantic description
        output["semantic_desc"] = (
            extract_field_with_priority(raw_item, "semantic_desc", str)
            or DEFAULT_VALUES["semantic_desc"]
        )

        # Generate semantic vector if vectorizer is provided and description exists
        if vectorizer and output["semantic_desc"]:
            try:
                output["semantic_vector"] = vectorizer.encode(output["semantic_desc"])
            except Exception as e:
                logger.warning(
                    f"Failed to generate vector for item {output['id']}: {e}"
                )
                output["semantic_vector"] = []
        else:
            output["semantic_vector"] = []

        # Extract timestamps
        created_at = extract_field_with_priority(raw_item, "created_at", str)
        output["created_at"] = parse_timestamp(created_at) or datetime.now().isoformat()

        updated_at = extract_field_with_priority(raw_item, "updated_at", str)
        output["updated_at"] = parse_timestamp(updated_at) or datetime.now().isoformat()

        # Set source
        output["source"] = source_name

        return output

    except Exception as e:
        logger.error(f"Failed to transform item: {e}")
        logger.debug(f"Problematic item: {raw_item}")
        return None


# ============================================================================
# FILE PROCESSING WORKFLOW
# ============================================================================


def process_json_file(
    input_path: Path,
    output_path: Path,
    vectorizer: Optional[Vectorizer] = None,
    source_name: Optional[str] = None,
) -> TransformStats:
    """
    Process a single JSON file and convert to golden schema.

    Args:
        input_path: Path to input JSON file
        output_path: Path to output JSON file
        vectorizer: Vectorizer instance for generating embeddings
        source_name: Name of the data source (defaults to filename)

    Returns:
        TransformStats object with processing statistics
    """
    stats = TransformStats()

    # Use filename as source if not provided
    if source_name is None:
        source_name = input_path.stem

    logger.info(f"Processing file: {input_path}")

    try:
        # Load input JSON
        with open(input_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        raw_items = flatten_json_objects(raw_data)

        stats.total = len(raw_items)
        logger.info(f"Found {stats.total} items to process")

        # Transform each item
        transformed_items = []
        for idx, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                logger.warning(f"Skipping non-dict item at index {idx}")
                stats.skipped += 1
                continue

            transformed = transform_item(raw_item, vectorizer, source_name)

            if transformed:
                transformed_items.append(transformed)
                stats.successful += 1
            else:
                stats.failed += 1
                stats.errors.append(f"Failed to transform item at index {idx}")

        # Write output JSON
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(transformed_items, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Successfully wrote {len(transformed_items)} items to {output_path}"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from {input_path}: {e}")
        stats.failed = 1
        stats.errors.append(f"JSON parse error: {e}")
    except Exception as e:
        logger.error(f"Error processing file {input_path}: {e}")
        stats.failed = 1
        stats.errors.append(f"Processing error: {e}")

    return stats


def batch_process_directory(
    input_dir: Path,
    output_dir: Path,
    use_vectorizer: bool = True,
    model_name: str = "all-MiniLM-L6-v2",
) -> Dict[str, TransformStats]:
    """
    Batch process all JSON files in a directory.

    Args:
        input_dir: Directory containing input JSON files
        output_dir: Directory for output JSON files
        use_vectorizer: Whether to generate semantic vectors
        model_name: Sentence transformer model name

    Returns:
        Dictionary mapping filenames to their TransformStats
    """
    logger.info(f"Starting batch processing: {input_dir} -> {output_dir}")

    # Initialize vectorizer if needed
    vectorizer = None
    if use_vectorizer:
        try:
            vectorizer = Vectorizer(model_name)
            logger.info("Vectorizer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize vectorizer: {e}")
            logger.warning("Continuing without vector generation")

    # Find all JSON files
    json_files = list(input_dir.glob("*.json"))

    if not json_files:
        logger.warning(f"No JSON files found in {input_dir}")
        return {}

    logger.info(f"Found {len(json_files)} JSON files to process")

    # Process each file
    results = {}
    for json_file in json_files:
        output_file = output_dir / json_file.name
        stats = process_json_file(json_file, output_file, vectorizer)
        results[json_file.name] = stats

    # Print summary
    print("\n" + "=" * 80)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 80)

    total_items = sum(s.total for s in results.values())
    total_success = sum(s.successful for s in results.values())
    total_failed = sum(s.failed for s in results.values())
    total_skipped = sum(s.skipped for s in results.values())

    print(f"\nTotal files processed: {len(results)}")
    print(f"Total items: {total_items}")
    print(f"  ✓ Successful: {total_success}")
    print(f"  ✗ Failed: {total_failed}")
    print(f"  ⊘ Skipped: {total_skipped}")

    print("\nPer-file breakdown:")
    for filename, stats in results.items():
        status = "✓" if stats.failed == 0 else "✗"
        print(f"  {status} {filename}: {stats.successful}/{stats.total} successful")
        if stats.errors:
            for error in stats.errors[:3]:  # Show first 3 errors
                print(f"      - {error}")

    print("=" * 80 + "\n")

    return results


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Clean and migrate audio metadata JSON files to standardized format"
    )

    parser.add_argument(
        "input", type=str, help="Input JSON file or directory containing JSON files"
    )

    parser.add_argument(
        "output", type=str, help="Output JSON file or directory for processed files"
    )

    parser.add_argument(
        "--no-vectors",
        action="store_true",
        help="Disable semantic vector generation (faster processing)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="all-MiniLM-L6-v2",
        help="Sentence transformer model name (default: all-MiniLM-L6-v2)",
    )

    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Source name for metadata (defaults to filename)",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Convert to Path objects
    input_path = Path(args.input)
    output_path = Path(args.output)

    # Validate input
    if not input_path.exists():
        logger.error(f"Input path does not exist: {input_path}")
        exit(1)

    # Determine processing mode
    if input_path.is_file():
        # Single file mode
        logger.info("Single file processing mode")

        vectorizer = None
        if not args.no_vectors:
            try:
                vectorizer = Vectorizer(args.model)
            except Exception as e:
                logger.error(f"Failed to initialize vectorizer: {e}")
                exit(1)

        stats = process_json_file(input_path, output_path, vectorizer, args.source)

        # Print summary
        print("\n" + "=" * 80)
        print("PROCESSING SUMMARY")
        print("=" * 80)
        print(f"Total items: {stats.total}")
        print(f"  ✓ Successful: {stats.successful}")
        print(f"  ✗ Failed: {stats.failed}")
        print(f"  ⊘ Skipped: {stats.skipped}")
        if stats.errors:
            print("\nErrors:")
            for error in stats.errors:
                print(f"  - {error}")
        print("=" * 80 + "\n")

    elif input_path.is_dir():
        # Directory batch mode
        logger.info("Batch directory processing mode")

        batch_process_directory(
            input_path,
            output_path,
            use_vectorizer=not args.no_vectors,
            model_name=args.model,
        )

    else:
        logger.error(f"Invalid input path: {input_path}")
        exit(1)

    logger.info("Processing complete!")
