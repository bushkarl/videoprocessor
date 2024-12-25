import os
import subprocess
import json
from .utils.logger import setup_logger
import srt

logger = setup_logger(__name__)

class VideoComposer:
    """视频合成器"""
    
    def _get_video_dimensions(self, video_path: str) -> tuple:
        """获取视频尺寸"""
        try:
            command = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'json',
                video_path
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            data = json.loads(result.stdout)
            
            width = int(data['streams'][0]['width'])
            height = int(data['streams'][0]['height'])
            
            logger.info(f"视频尺寸: {width}x{height}")
            return width, height
            
        except Exception as e:
            logger.error(f"获取视频尺寸失败: {str(e)}")
            raise
    
    def _remove_subtitles(self, video_path: str, output_path: str) -> str:
        """移��视频中的字幕流和硬编码字幕"""
        try:
            # 1. 首先检查视频流信息
            probe_command = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height',
                '-of', 'json',
                video_path
            ]
            
            result = subprocess.run(probe_command, capture_output=True, text=True)
            data = json.loads(result.stdout)
            video_codec = data['streams'][0]['codec_name']
            
            # 2. 使用 delogo 滤镜移除硬编码字幕
            # 针对不同视频尺寸调整字幕区域
            width = int(data['streams'][0]['width'])
            height = int(data['streams'][0]['height'])
            
            # 计算字幕区域（通常在底部 1/4 区域）
            subtitle_y = int(height * 0.75)  # 从底部 1/4 处开始
            subtitle_h = int(height * 0.25)  # 覆盖底部 1/4
            
            # 构建移除字幕的命令
            command = [
                'ffmpeg',
                '-i', video_path,
                '-filter_complex', 
                # 移除底部字幕区域
                f"[0:v]delogo=x=0:y={subtitle_y}:w={width}:h={subtitle_h}:show=0[v]",
                '-map', '[v]',  # 使用处理后的视频流
                '-map', '0:a',  # 复制所有音频流
                '-c:a', 'copy',  # 音频直接复制
                '-c:v', video_codec,  # 使用原始视频编码
                # 确保不复制任何字幕流
                '-sn',  # 禁用字幕
                '-dn',  # 禁用数据流
                '-y',
                output_path
            ]
            
            logger.info(f"执行字幕移除命令: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"移除字幕失败: {result.stderr}")
                # 如果失败，尝试使用备用方案
                return self._remove_subtitles_fallback(video_path, output_path)
            
            logger.info("原字幕移除完成")
            return output_path
            
        except Exception as e:
            logger.error(f"移除字幕失败: {str(e)}")
            # 发生异常时尝试备用方案
            return self._remove_subtitles_fallback(video_path, output_path)

    def _remove_subtitles_fallback(self, video_path: str, output_path: str) -> str:
        """备用的字幕移除方法"""
        try:
            logger.info("使用备用方案移除字幕")
            # 1. 提取纯视频流（不包含字幕）
            command = [
                'ffmpeg',
                '-i', video_path,
                # 使用 crop 滤镜裁剪掉字幕区域
                '-vf', 'crop=iw:ih*0.85:0:0',  # 裁剪掉底部 15% 的区域
                '-map', '0:v',  # 只要视频流
                '-map', '0:a',  # 只要音频流
                '-c:a', 'copy',
                '-sn',          # 禁用字幕流
                '-dn',          # 禁用数据流
                '-max_muxing_queue_size', '1024',  # 增加队列大小
                '-y',
                output_path
            ]
            
            logger.info(f"执行备用字幕移除命令: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"备用方案移除字幕失败: {result.stderr}")
                raise Exception(f"备用方案移除字幕失败: {result.stderr}")
            
            logger.info("使用备用方案移除字幕完成")
            return output_path
            
        except Exception as e:
            logger.error(f"备用方案移除字幕失败: {str(e)}")
            raise
    
    def compose(self, video_path: str, audio_path: str, subtitle_path: str, output_path: str, remove_original_subs: bool = False) -> str:
        """合成最终视频"""
        try:
            # 创建临时目录
            temp_dir = os.path.join(os.path.dirname(output_path), '.temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # 获取视频尺寸并确定字体大小
            width, height = self._get_video_dimensions(video_path)
            font_size = 12 if height > width else 18  # 竖屏使用小字体
            
            # 1. 如果需要，移除原字幕
            if remove_original_subs:
                temp_video_no_subs = os.path.join(temp_dir, "temp_no_subs.mp4")
                video_path = self._remove_subtitles(video_path, temp_video_no_subs)
            
            # 2. 合成新字幕
            temp_video_with_sub = os.path.join(temp_dir, "temp_with_sub.mp4")
            
            # 判断字幕文件类型
            is_ass = subtitle_path.lower().endswith('.ass')
            
            if is_ass:
                filter_complex = f"ass={os.path.abspath(subtitle_path)}"
            else:
                filter_complex = (
                    f"subtitles={os.path.abspath(subtitle_path)}"
                    f":force_style='Fontname=STHeiti,FontSize={font_size},"  # 动态字体大小
                    f"PrimaryColour=&HFFFFFF&,"
                    f"BorderStyle=1,"
                    f"Outline=1.5,"
                    f"Shadow=0.5,"
                    f"Alignment=2,"
                    f"MarginV=10'"
                )
            
            subtitle_command = [
                'ffmpeg',
                '-i', video_path,
                '-vf', filter_complex,
                '-c:a', 'copy',
                '-y',
                temp_video_with_sub
            ]
            
            result = subprocess.run(subtitle_command, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"字幕合成失败: {result.stderr}")
                raise Exception(f"字幕合成失败: {result.stderr}")
            
            logger.info("字幕合成完成")
            
            # 3. 替换音频
            merge_command = [
                'ffmpeg',
                '-i', temp_video_with_sub,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-strict', 'experimental',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',
                '-y',
                output_path
            ]
            
            result = subprocess.run(merge_command, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"音频合成失败: {result.stderr}")
                raise Exception(f"音频合成失败: {result.stderr}")
            
            logger.info("音频合成完成")
            
            # 验证输出文件
            if not os.path.exists(output_path):
                raise Exception("输出文件不存在")
            
            if os.path.getsize(output_path) == 0:
                raise Exception("输出文件为空")
            
            logger.info(f"视频合成完成: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"视频合成失败: {str(e)}")
            raise
        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_dir):
                    for file in os.listdir(temp_dir):
                        os.remove(os.path.join(temp_dir, file))
                    os.rmdir(temp_dir)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {str(e)}") 