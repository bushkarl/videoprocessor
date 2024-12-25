#!/usr/bin/env python3
import os
import sys
from videoprocessor import VideoProcessor

def main():
    """示例代码"""
    try:
        # 获取示例视频路径
        input_video = os.path.join(os.path.dirname(__file__), "input.mp4")
        output_video = os.path.join(os.path.dirname(__file__), "output.mp4")
        
        # 创建处理器实例
        processor = VideoProcessor(input_video)
        
        # 处理视频
        output_path = processor.process(
            target_language="zh-CN",
            output_path=output_video
        )
        
        print(f"处理完成: {output_path}")
        return 0
        
    except Exception as e:
        print(f"处理失败: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 