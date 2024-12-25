import os
import subprocess
from videoprocessor.utils.logger import setup_logger

logger = setup_logger(__name__)

def burn_subtitle_to_video(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    font_name: str = 'STHeiti'
) -> str:
    """将字幕烧录到视频中"""
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 判断字幕文件类型
        is_ass = subtitle_path.lower().endswith('.ass')
        
        if is_ass:
            # 使用 ASS 字幕
            filter_complex = f"ass={os.path.abspath(subtitle_path)}"
        else:
            # 使用 SRT 字幕，需要更多的字体设置
            filter_complex = (
                f"subtitles={os.path.abspath(subtitle_path)}"
                f":force_style='Fontname={font_name},FontSize=24,PrimaryColour=&HFFFFFF&,"
                f"BorderStyle=3,Outline=1,Shadow=0,MarginV=35'"
            )
        
        # 构建 FFmpeg 命令
        command = [
            'ffmpeg',
            '-i', video_path,
            '-vf', filter_complex,
            '-c:a', 'copy',  # 复制音频流
            '-y',  # 覆盖已存在的文件
            output_path
        ]
        
        logger.info(f"执行命令: {' '.join(command)}")
        
        # 执行命令
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )
        
        # 验证输出文件
        if not os.path.exists(output_path):
            raise Exception("输出文件不存在")
        
        if os.path.getsize(output_path) == 0:
            raise Exception("输出文件为空")
        
        logger.info(f"字幕烧录完成: {output_path}")
        return output_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg 执行失败: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"字幕烧录失败: {str(e)}")
        raise

def test_subtitle_burn():
    """测试字幕烧录"""
    try:
        # 测试文件路径
        video_path = './test.mp4'  # 原始视频
        ass_subtitle_path = './translated_subtitles.ass'  # ASS 字幕
        srt_subtitle_path = './translated_subtitles.srt'  # SRT 字幕
        
        # 测试 ASS 字幕
        if os.path.exists(ass_subtitle_path):
            output_path = './output_with_ass.mp4'
            burn_subtitle_to_video(
                video_path,
                ass_subtitle_path,
                output_path
            )
        
        # 测试 SRT 字幕
        if os.path.exists(srt_subtitle_path):
            output_path = './output_with_srt.mp4'
            burn_subtitle_to_video(
                video_path,
                srt_subtitle_path,
                output_path,
                font_name='STHeiti'
            )
        
        logger.info("测试完成!")
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_subtitle_burn()
    import sys
    sys.exit(0 if success else 1)