#!/usr/bin/env python3

import subprocess
import sys
import os
from utils.create_test_video import create_test_video

def test_installation():
    """测试安装是否成功"""
    try:
        # 导入测试
        from videoprocessor import VideoProcessor
        
        # 创建测试视频
        test_video = "test.mp4"
        create_test_video(test_video)
        
        try:
            # 基本功能测试
            processor = VideoProcessor(test_video)
            
            # 命令行测试
            result = subprocess.run(
                ['python', '-m', 'videoprocessor.cli', test_video, 'output.mp4'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"Error: Command line tool failed\n{result.stderr}")
                return False
                
            print("Installation test passed!")
            return True
            
        finally:
            print("Cleaning up test files...")
            # 清理测试文件
            if os.path.exists(test_video):
                os.remove(test_video)
            if os.path.exists('output.mp4'):
                os.remove('output.mp4')
        
    except ImportError as e:
        print(f"Import Error: {str(e)}")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_installation()
    sys.exit(0 if success else 1) 