import os
import sys
import srt
from datetime import timedelta
import subprocess
from videoprocessor.utils.logger import setup_logger

logger = setup_logger(__name__)

def create_test_video(output_path: str, duration: int = 15):
    """创建测试视频"""
    command = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=blue:s=1280x720:d={duration}',
        '-vf', f'drawtext=text=\'字幕测试视频\':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:fontfile=/System/Library/Fonts/PingFang.ttc',
        '-c:v', 'libx264',
        '-t', str(duration),
        '-y',
        output_path
    ]
    
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info(f"测试视频已创建: {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"创建测试视频失败: {e.stderr}")
        raise

def create_ass_subtitle(subtitle_path: str):
    """创建 ASS 格式字幕"""
    ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,STHeiti,28,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,35,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,这是第一行中文字幕测试
Dialogue: 0,0:00:03.00,0:00:06.00,Default,,0,0,0,,第二行字幕，包含标点符号。
Dialogue: 0,0:00:06.00,0:00:09.00,Default,,0,0,0,,第三行字幕！带有感叹号！
Dialogue: 0,0:00:09.00,0:00:12.00,Default,,0,0,0,,第四行字幕？带有问号？
Dialogue: 0,0:00:12.00,0:00:15.00,Default,,0,0,0,,最后一行中文字幕测试完成。
"""
    
    with open(subtitle_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(ass_content)
    
    logger.info(f"ASS 字幕文件已创建: {subtitle_path}")
    return subtitle_path

def compose_subtitle_to_video(video_path: str, subtitle_path: str, output_path: str):
    """合成字幕到视频"""
    try:
        command = [
            'ffmpeg',
            '-i', video_path,
            '-vf', f"ass={os.path.abspath(subtitle_path)}",  # 使用 ASS 字幕
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        
        # 设置环境变量
        env = os.environ.copy()
        env['FFREPORT'] = 'file=ffreport.log:level=32'
        env['PYTHONIOENCODING'] = 'utf-8'
        env['LANG'] = 'zh_CN.UTF-8'
        
        logger.info(f"执行命令: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            raise Exception(f"视频合成失败: {result.stderr}")
        
        logger.info(f"视频合成完成: {output_path}")
        
    except Exception as e:
        logger.error(f"视频合成失败: {str(e)}")
        raise

def test_subtitle_compose():
    """测试字幕合成"""
    try:
        # 创建测试目录
        os.makedirs('tests/output', exist_ok=True)
        
        # 测试文件路径
        video_path = 'tests/output/test_video.mp4'
        subtitle_path = 'tests/output/test_subtitle.ass'  # 改为 .ass 后缀
        output_path = 'tests/output/output_with_subtitle.mp4'
        
        # 1. 创建测试视频
        create_test_video(video_path)
        
        # 2. 创建 ASS 字幕文件
        create_ass_subtitle(subtitle_path)
        
        # 验证字幕文件编码
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            content = f.read()
            logger.info(f"字幕文件内容预览:\n{content[:500]}")
        
        # 3. 合成字幕到视频
        compose_subtitle_to_video(video_path, subtitle_path, output_path)
        
        # 4. 验证输出文件
        if not os.path.exists(output_path):
            raise Exception("输出文件不存在")
        
        if os.path.getsize(output_path) == 0:
            raise Exception("输出文件为空")
        
        logger.info("测试完成!")
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_subtitle_compose()
    sys.exit(0 if success else 1) 