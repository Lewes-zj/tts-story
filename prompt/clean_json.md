**角色设定**：你是一位专注于数据治理的资深 Python 工程师。

**任务**：编写一个**通用且健壮**的元数据清洗与迁移脚本 `clean_metadata.py`。

**背景**：
我有多个来源不一的原始音频元数据 JSON 文件（N 个角色），它们的格式参差不齐，包含各种已知的和未知的格式错误。
我们需要一个脚本，能够读取任意输入的 JSON，并将其强制转换为我们严格定义的**目标标准格式**。

### 1. 目标标准模版 (The Golden Schema)

无论输入长什么样，输出列表中的每一项必须严格符合以下结构和默认值：

```json
{
  "id": "String (必填, 最好对应文件名)",
  "role": "String (必填, 默认为 'narrator')",
  "duration": "Float (必填, 秒数, 精确到小数点后2位)",
  "vocal_mode": "String (默认为 'modal_warm')",
  "energy_level": "Int (默认为 3)",
  "pitch_curve": "String (默认为 'stable')",
  "semantic_desc": "String (默认为空字符串)",
  "tags": "List[String] (默认为 ['clean'])",
  "vector_embedding": "List[Float] (必填, 由 semantic_desc 生成)"
}
```

### 2. 已知的转换逻辑 (Transformation Rules)

请在代码中实现以下具体的清洗逻辑：

1.  **结构修复（扁平化）：**
    输入 JSON 可能包含多层嵌套列表（例如 `[A, [B, C], D]`）。脚本必须先递归展平整个列表，确保处理的是扁平对象。
2.  **时间戳转换：**
    - 如果遇到 `"timestamp": {"start": "...", "end": "..."}` 结构，解析 `MM:SS.ms` 并计算差值作为 `duration`。
    - 如果遇到 `"duration": "5s"` (字符串)，尝试解析为 Float。
3.  **字段映射与重命名（优先匹配）：**
    - `role` 取值优先级：`role` > `role_tag` > `character` > 默认值。
    - `semantic_desc` 取值优先级：`semantic_desc` > `semantic_vector_desc` > `description` > 默认值。
    - `vocal_mode` 取值位置：顶层 > `timbral.vocal_mode` > 默认值。
    - `tags` 来源：顶层 `tags` > `physiological.mouth_artifact` (需转换) > 默认值。
4.  **Tags 转换逻辑：**
    - 如果源数据是 `mouth_artifact: "clean"` -> 转换为 `["clean"]`。
    - 如果源数据是其他值（如 `"smack_lips"`） -> 转换为 `["smack_lips"]`。

### 3. 未知情况的兜底策略 (Robustness Strategy)

针对其他可能存在的格式问题，请遵循“防御性编程”原则：

1.  **缺失字段兜底：**
    如果源数据中完全没有某个字段（如 `energy_level`），**不要报错**，直接使用上述模板中的默认值填充。
2.  **类型强制转换：**
    - 如果 `energy_level` 是字符串 "3"，转为 Int 3。
    - 如果 `duration` 无法解析，打印 Warning 并跳过该条目（不要让整个脚本崩溃）。
3.  **ID 缺失：**
    如果没有 `id`，尝试使用输入文件名 + 索引生成临时 ID。

### 4. 代码要求

1.  **依赖：** 使用 `sentence_transformers` 生成向量。
2.  **命令行：** 支持 `python clean_metadata.py input_dir/ output_dir/`。
    - 脚本应扫描输入目录下的所有 `.json` 文件，逐个清洗，并在输出目录生成对应的 `_cleaned.json` 文件。
3.  **日志：** 处理过程中，打印简单的统计信息（例如：“文件 A 清洗完成：输入 50 条，成功 48 条，跳过 2 条错误数据”）。

这很常见，通常是因为**生成的代码太长**或者**逻辑太复杂**，导致 Antigravity (Claude) 在输出过程中触发了长度限制或超时崩溃（Context Window Limit）。

别担心，它的方案已经存下来了。我们只需要采用 **“分期付款”** 的策略，让它分两次把代码吐出来，就能绕过这个错误。

你可以按照顺序，分两次发送以下指令：

### 第 1 步：获取基础模块（配置、工具、向量引擎）

**复制发送：**

由于代码较长，请分模块编写。

**Part 1 任务：** 请编写 `clean_metadata.py` 的**前半部分**。

包含以下内容：

1.  所有的 `import` 引用。
2.  **配置常量** (GOLDEN_SCHEMA, FIELD_PRIORITY_MAP, DEFAULT_VALUES)。
3.  **工具函数** (`flatten_list`, `parse_timestamp`, `safe_cast`, `generate_fallback_id`)。
4.  **向量生成器类** (`Vectorizer` class)。

请只输出这一部分代码，不要包含 `main` 函数。

---

### 第 2 步：获取核心逻辑与主流程

等它输出了 Part 1 之后，**复制发送：**

**Part 2 任务：** 请继续编写 `clean_metadata.py` 的**后半部分**。

包含以下内容：

1.  **字段提取逻辑** (`extract_role`, `extract_tags`, `extract_duration` 等)。
2.  **单条转换函数** (`transform_item`)。
3.  **文件处理主流程** (`process_json_file`, `batch_process_directory`)。
4.  **命令行入口** (`if __name__ == "__main__": ...`)。

请确保这部分代码能衔接上 Part 1。
