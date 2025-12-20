# 架构重构快速开始指南

本指南帮助您快速开始对 tts-story 项目进行架构重构。

---

## 🎯 重构目标

将现有的单层架构重构为清晰的分层架构，解决以下核心问题：

1. ✅ 项目结构混乱
2. ✅ sys.path 污染
3. ✅ 数据库连接管理不当
4. ✅ 缺乏统一配置管理

---

## 📋 准备工作

### 1. 创建新分支

```bash
git checkout -b refactor/architecture-improvement
```

### 2. 备份当前代码

```bash
cp -r tts-story tts-story-backup
```

### 3. 安装必要依赖

```bash
pip install sqlalchemy alembic python-dotenv pydantic-settings
```

---

## 🚀 第一步：创建新的目录结构（30 分钟）

### 执行以下命令：

```bash
cd tts-story

# 创建新的目录结构
mkdir -p app/{api/v1,core,models,schemas,services/{tts,audio,story},repositories,utils}
mkdir -p tests/{unit,integration}
mkdir -p logs

# 创建 __init__.py 文件
touch app/__init__.py
touch app/api/__init__.py
touch app/api/v1/__init__.py
touch app/core/__init__.py
touch app/models/__init__.py
touch app/schemas/__init__.py
touch app/services/__init__.py
touch app/services/tts/__init__.py
touch app/services/audio/__init__.py
touch app/services/story/__init__.py
touch app/repositories/__init__.py
touch app/utils/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py

echo "✅ 目录结构创建完成"
```

---

## 🔧 第二步：创建核心配置文件（1 小时）

### 2.1 创建 .env.example

```bash
cat > .env.example << 'EOF'
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=tts_story

# 外部依赖路径
INDEX_TTS_PATH=/root/autodl-tmp/index-tts

# TTS模型配置
TTS_MODEL_DIR=/root/autodl-tmp/index-tts/checkpoints
TTS_CONFIG_PATH=/root/autodl-tmp/index-tts/checkpoints/config.yaml

# JWT配置
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# 日志配置
LOG_LEVEL=INFO

# 应用配置
APP_ENV=development
DEBUG=true
EOF
```

### 2.2 复制为实际配置

```bash
cp .env.example .env
# 然后编辑 .env 填入真实配置
```

### 2.3 创建 app/core/config.py

参考 ARCHITECTURE_REVIEW.md 中的配置管理方案创建这个文件。

### 2.4 创建 app/core/logging.py

参考 ARCHITECTURE_REVIEW.md 中的日志管理方案创建这个文件。

### 2.5 创建 app/core/exceptions.py

参考 ARCHITECTURE_REVIEW.md 中的异常处理方案创建这个文件。

---

## 📦 第三步：迁移数据库层（2 小时）

### 3.1 创建 app/models/database.py

```bash
# 按照 ARCHITECTURE_REVIEW.md 中的方案创建
```

### 3.2 创建 app/repositories/base.py

```bash
# 按照 ARCHITECTURE_REVIEW.md 中的方案创建
```

### 3.3 迁移现有 DAO

```bash
# 示例：迁移 user_dao.py
# 原路径：scripts/user_dao.py
# 新路径：app/repositories/user.py

# 步骤：
# 1. 复制文件到新位置
cp scripts/user_dao.py app/repositories/user.py

# 2. 修改导入语句
# 3. 继承 BaseRepository
# 4. 使用 SQLAlchemy Session
```

---

## 🎨 第四步：迁移 API 层（2 小时）

### 4.1 迁移认证 API

```bash
# 原路径：scripts/auth_api.py
# 新路径：app/api/v1/auth.py

cp scripts/auth_api.py app/api/v1/auth.py

# 修改：
# 1. 更新导入路径
# 2. 添加版本前缀 /api/v1
# 3. 使用新的依赖注入
```

### 4.2 迁移其他 API

按照相同模式迁移：

- character_api.py → app/api/v1/character.py
- story_api.py → app/api/v1/story.py
- task_api.py → app/api/v1/task.py
- file_api.py → app/api/v1/file.py

---

## 🔨 第五步：创建新的应用入口（30 分钟）

### 5.1 创建 main.py

```python
# main.py
"""应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.error_handlers import register_exception_handlers
from app.api.v1 import auth, character, story, task, file

# 配置日志
setup_logging()

# 获取配置
settings = get_settings()

# 创建应用
app = FastAPI(
    title="TTS Story API",
    description="Text-to-Speech Story Generation Platform",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册异常处理器
register_exception_handlers(app)

# 挂载静态文件
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 注册路由
app.include_router(auth.router)
app.include_router(character.router)
app.include_router(story.router)
app.include_router(task.router)
app.include_router(file.router)

@app.get("/")
def root():
    """根路径"""
    return {
        "name": "TTS Story API",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
```

---

## ✅ 第六步：测试新架构（1 小时）

### 6.1 启动应用

```bash
python main.py
```

### 6.2 访问文档

打开浏览器访问：http://localhost:8000/docs

### 6.3 测试 API

```bash
# 测试健康检查
curl http://localhost:8000/health

# 测试注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test",
    "email": "test@example.com",
    "password": "password123"
  }'
```

---

## 📝 第七步：逐步迁移业务逻辑（分阶段进行）

### 阶段 1：核心 TTS 功能

1. 迁移 `index_tts2_voice_cloner.py` → `app/services/tts/voice_cloner.py`
2. 迁移 `tts_utils.py` → `app/services/tts/utils.py`
3. 迁移 `generate_by_emo_vector.py` → `app/services/tts/emotion_generator.py`

### 阶段 2：音频处理

1. 迁移 `audio_processor.py` → `app/services/audio/processor.py`
2. 迁移 `audio_matcher.py` → `app/services/audio/matcher.py`

### 阶段 3：故事生成

1. 迁移 `story_book_generator.py` → `app/services/story/book_generator.py`
2. 迁移 `story_director.py` → `app/services/story/director.py`

---

## 🔄 第八步：更新导入路径（持续）

使用以下脚本批量更新导入路径：

```python
# update_imports.py
import os
import re

# 定义替换规则
replacements = {
    r'from scripts\.': 'from app.',
    r'import scripts\.': 'import app.',
}

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    modified = False
    for pattern, replacement in replacements.items():
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            content = new_content
            modified = True

    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {filepath}")

# 遍历所有Python文件
for root, dirs, files in os.walk('app'):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            update_file(filepath)
```

运行：

```bash
python update_imports.py
```

---

## 🧪 第九步：添加测试（推荐）

### 9.1 安装 pytest

```bash
pip install pytest pytest-cov pytest-asyncio
```

### 9.2 创建测试配置

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.models.database import Base, get_db

# 测试数据库URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

### 9.3 编写测试

```python
# tests/unit/test_auth.py
def test_register(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
```

### 9.4 运行测试

```bash
pytest tests/ -v
```

---

## 📊 进度检查清单

### 第一周

- [ ] 创建新目录结构
- [ ] 创建核心配置文件
- [ ] 迁移数据库层
- [ ] 迁移 API 层
- [ ] 创建新的应用入口
- [ ] 基本功能测试通过

### 第二周

- [ ] 迁移 TTS 服务
- [ ] 迁移音频处理服务
- [ ] 迁移故事生成服务
- [ ] 更新所有导入路径
- [ ] 添加单元测试
- [ ] 代码审查

### 第三周

- [ ] 性能优化
- [ ] 安全加固
- [ ] 文档更新
- [ ] 部署测试
- [ ] 上线准备

---

## ⚠️ 注意事项

### 1. 保持向后兼容

在重构期间，可以保留 scripts/ 目录，逐步废弃：

```python
# scripts/xxx_api.py (标记为废弃)
import warnings
from app.api.v1.xxx import router

warnings.warn(
    "scripts.xxx_api is deprecated, use app.api.v1.xxx instead",
    DeprecationWarning
)
```

### 2. 数据库迁移

使用 Alembic 管理数据库变更：

```bash
# 初始化Alembic
alembic init alembic

# 创建迁移
alembic revision --autogenerate -m "initial migration"

# 执行迁移
alembic upgrade head
```

### 3. 环境变量

确保所有环境都配置了正确的 .env 文件

### 4. 代码审查

每个阶段完成后进行代码审查，确保质量

---

## 🆘 遇到问题？

### 常见问题

**Q: 导入错误 - ModuleNotFoundError**

```
A: 检查 PYTHONPATH 是否包含项目根目录
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**Q: 数据库连接失败**

```
A: 检查 .env 文件中的数据库配置是否正确
```

**Q: JWT 验证失败**

```
A: 检查 JWT_SECRET_KEY 是否配置
```

---

## 📚 参考资料

- [FastAPI 最佳实践](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [12 Factor App](https://12factor.net/)

---

## 🎉 完成！

完成所有步骤后，您将拥有一个：

- ✅ 结构清晰的代码库
- ✅ 易于维护和扩展
- ✅ 遵循最佳实践
- ✅ 便于测试的架构

祝重构顺利！🚀
