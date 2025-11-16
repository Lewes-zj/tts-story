"""
有声故事书生成API
提供生成有声故事书的RESTful API接口
"""

import os
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入有声故事书生成器
try:
    from scripts.story_book_generator import StoryBookGenerator
    STORY_BOOK_AVAILABLE = True
except ImportError:
    print("警告: 无法导入StoryBookGenerator，有声故事书功能将不可用")
    STORY_BOOK_AVAILABLE = False

app = FastAPI(title="有声故事书生成API", description="根据用户选择的角色和故事生成有声故事书")

class StoryBookRequest(BaseModel):
    """有声故事书生成请求模型"""
    user_id: int
    role_id: int
    story_path: str

class StoryBookResponse(BaseModel):
    """有声故事书生成响应模型"""
    success: bool
    message: str
    story_book_path: Optional[str] = None

@app.post("/story_book/generate", response_model=StoryBookResponse)
async def generate_story_book(request: StoryBookRequest):
    """
    生成有声故事书
    
    Args:
        request (StoryBookRequest): 生成请求参数
        
    Returns:
        StoryBookResponse: 生成结果
    """
    if not STORY_BOOK_AVAILABLE:
        raise HTTPException(status_code=500, detail="有声故事书功能不可用")
        
    try:
        # 创建生成器实例
        generator = StoryBookGenerator()
        
        # 生成有声故事书
        story_book_path = generator.generate_story_book(
            user_id=request.user_id,
            role_id=request.role_id,
            story_path=request.story_path
        )
        
        if story_book_path:
            return StoryBookResponse(
                success=True,
                message="有声故事书生成成功",
                story_book_path=story_book_path
            )
        else:
            return StoryBookResponse(
                success=False,
                message="有声故事书生成失败"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成有声故事书时出错: {str(e)}")

# 为了方便测试，添加一个根路径
@app.get("/")
async def root():
    return {"message": "有声故事书生成API服务"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)