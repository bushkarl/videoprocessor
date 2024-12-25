import os
import subprocess
from .utils.logger import setup_logger

logger = setup_logger(__name__)

class AudioExtractor:
    """音频提取器"""
    
    def extract(self, video_path: str, output_path: str = None) -> str:
        """
        从视频中提取音频
        
        Args:
            video_path: 输入视频路径
            output_path: 输出音频路径（可选，如果不提供则自动生成）
        
        Returns:
            str: 提取的音频文件路径
        """
        try:
            # 如果没有提供输出路径，则自动生成
            if output_path is None:
                dirname = os.path.dirname(video_path)
                basename = os.path.splitext(os.path.basename(video_path))[0]
                output_path = os.path.join(dirname, f"{basename}_audio.wav")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 构建 FFmpeg 命令
            command = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # 不处理视频
                '-acodec', 'pcm_s16le',  # 音频编码为 WAV
                '-ar', '44100',  # 采样率
                '-ac', '2',  # 双声道
                '-y',  # 覆盖已存在的文件
                output_path
            ]
            
            # 执行命令
            result = subprocess.run(command, capture_output=True, text=True)
            
            # 检查执行结果
            if result.returncode != 0:
                logger.error(f"音频提取失败: {result.stderr}")
                raise Exception(f"音频提取失败: {result.stderr}")
            
            # 验证输出文件
            if not os.path.exists(output_path):
                raise Exception("输出文件不存在")
            
            if os.path.getsize(output_path) == 0:
                raise Exception("输出文件为空")
            
            logger.info(f"音频提取完成: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"音频提取失败: {str(e)}")
            raise 