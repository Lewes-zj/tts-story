"""
有声故事书生成器测试脚本
用于测试StoryBookGenerator类的基本功能
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_story_book_generator():
    """测试有声故事书生成器"""
    try:
        # 导入有声故事书生成器
        from scripts.story_book_generator import StoryBookGenerator
        
        # 创建生成器实例
        generator = StoryBookGenerator()
        
        # 检查TTS是否可用
        if generator.tts is None:
            print("警告: TTS模型不可用，但可以测试其他功能")
            
        # 检查DAO是否初始化成功
        if generator.user_emo_audio_dao is not None:
            print("成功: UserEmoAudioDAO初始化成功")
        else:
            print("错误: UserEmoAudioDAO初始化失败")
            
        # 测试故事文件解析
        story_path = "db/xiaohongmao.json"
        if os.path.exists(story_path):
            story_list = generator._parse_story_file(story_path)
            if story_list:
                print(f"成功: 解析故事文件，共{len(story_list)}个段落")
                # 显示前几个段落的信息
                for i, item in enumerate(story_list[:3]):
                    print(f"  段落{i+1}: {item.get('speaker', '未知')} - {item.get('emotion_description', '未知情绪')}")
            else:
                print("警告: 故事文件解析结果为空")
        else:
            print(f"警告: 故事文件不存在 {story_path}")
            
        print("有声故事书生成器测试完成")
        
    except Exception as e:
        print(f"测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_story_book_generator()