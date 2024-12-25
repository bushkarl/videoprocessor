import subprocess
import os

def create_test_video(output_path: str, duration: int = 5):
    """创建测试视频文件"""
    command = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=blue:s=1280x720:d={duration}',
        '-vf', f'drawtext=text=\'Test Video\':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2',
        '-c:v', 'libx264',
        '-t', str(duration),
        '-y',
        output_path
    ]
    
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"测试视频已创建: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"创建测试视频失败: {e.stderr}")
        raise

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(os.path.dirname(script_dir), "test.mp4")
    create_test_video(output_path)
