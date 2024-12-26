import os
import subprocess
from dotenv import load_dotenv
from .audio_extractor import AudioExtractor
from .subtitle_generator import SubtitleGenerator
from .subtitle_processor import SubtitleProcessor
from .translation_service import TranslationService
from .tts_service import TextToSpeechService
from .video_composer import VideoComposer
from .utils.logger import setup_logger

logger = setup_logger(__name__)

class VideoProcessor:
    """视频处理的主类，协调所有处理流程"""
    
    def __init__(self):
        """初始化视频处理器"""
        # 加载环境变量
        load_dotenv()
        
        # 初始化各个组件
        self.audio_extractor = AudioExtractor()
        self.subtitle_generator = SubtitleGenerator()
        self.subtitle_processor = SubtitleProcessor()
        self.translation_service = TranslationService()
        self.tts_service = TextToSpeechService()
        self.video_composer = VideoComposer()
        
        # 创建临时文件夹
        self.temp_dir = os.path.join(os.getcwd(), '.temp')
        os.makedirs(self.temp_dir, exist_ok=True)
        
        self.use_batch_translation = True  # 默认使用批量翻译
        self.remove_original_subs = False  # 默认不移除原字幕
        self.voice_name = None  # 存储语音选择
        self.speed_factor = 1.0  # 存储速度因子
        
        # 添加输出目录设置
        self.output_dir = None  # 将在 process 方法中设置
        self.save_intermediate = True  # 是否保存中间文件
    
    def _slow_down_video(self, input_path: str, speed: float = 1.0) -> str:
        """减速视频和音频
        
        Args:
            input_path: 输入视频路径
            speed: 速度因子 (0.5 表示减速一半，2.0 表示加速一倍)
        
        Returns:
            str: 处理后的视频路径
        """
        try:
            output_path = os.path.join(self.temp_dir, "speed_adjusted.mp4")
            
            # 处理 atempo 滤镜的限制（0.5 到 2.0）
            atempo_filters = []
            remaining_speed = speed
            
            # 如果速度因子超出范围，需要串联多个 atempo
            while remaining_speed < 0.5:
                atempo_filters.append("atempo=0.5")
                remaining_speed /= 0.5
            while remaining_speed > 2.0:
                atempo_filters.append("atempo=2.0")
                remaining_speed /= 2.0
            if 0.5 <= remaining_speed <= 2.0:
                atempo_filters.append(f"atempo={remaining_speed}")
            
            # 构建音频滤镜链
            audio_filter = ','.join(atempo_filters)
            
            # 构建完整的滤镜图
            filter_complex = (
                # 视频速度调整
                f"[0:v]setpts={1/speed}*PTS[v];"
                # 音频速度调整（使用串联的 atempo）
                f"[0:a]{audio_filter}[a]"
            )
            
            command = [
                'ffmpeg',
                '-i', input_path,
                '-filter_complex', filter_complex,
                '-map', '[v]',  # 使用处理后的视频流
                '-map', '[a]',  # 使用处理后的音频流
                # 保持视频编码器
                '-c:v', 'libx264',
                '-preset', 'medium',  # 编码速度和质量的平衡
                '-crf', '23',        # 视频质量控制
                # 音频编码设置
                '-c:a', 'aac',
                '-b:a', '192k',      # 音频比特率
                '-y',
                output_path
            ]
            
            logger.info(f"执行速度调整命令: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"速度调整失败: {result.stderr}")
                raise Exception(f"速度调整失败: {result.stderr}")
            
            # 验证输出文件
            if not os.path.exists(output_path):
                raise Exception("输出文件不存在")
            
            if os.path.getsize(output_path) == 0:
                raise Exception("输出文件为空")
            
            logger.info(f"视频和音频速度调整完成: {speed}x")
            return output_path
            
        except Exception as e:
            logger.error(f"速度调整失败: {str(e)}")
            raise

    def process(self, input_path: str, output_path: str) -> str:
        """
        处理视频
        
        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
        
        Returns:
            str: 处理后的视频路径
        """
        try:
            # 验证输入文件
            if not input_path or not os.path.exists(input_path):
                raise FileNotFoundError(f"输入视频文件不存在: {input_path}")
            
            # 确保输出目录存在
            output_dir = os.path.dirname(os.path.abspath(output_path))
            os.makedirs(output_dir, exist_ok=True)
            
            # 存储原始视频路径，用于后续处理
            original_video = input_path
            
            # 如果需要减速，先处理视频
            if self.speed_factor != 1.0:
                input_path = self._slow_down_video(input_path, self.speed_factor)
                logger.info(f"视频速度调整为 {self.speed_factor}x")
            
            # 1. 提取音频
            audio_path = self.audio_extractor.extract(input_path)
            logger.info("提取音频完成")
            
            # 2. 生成原始字幕
            original_subtitle_path = os.path.join(self.temp_dir, "original_subtitles.srt")
            original_subtitle_path = self.subtitle_generator.generate(
                audio_path,
                original_subtitle_path
            )
            
            # 保存原始字幕
            if self.save_intermediate:
                output_original_srt = os.path.join(
                    self.output_dir,
                    f"{os.path.splitext(os.path.basename(input_path))[0]}_original.srt"
                )
                self._save_file(original_subtitle_path, output_original_srt)
                logger.info(f"原始字幕已保存: {output_original_srt}")
            
            # 3. 处理字幕并获取文本
            original_subs, texts = self.subtitle_processor.process(
                original_subtitle_path,
                use_batch=self.use_batch_translation
            )
            logger.info("处理字幕完成")
            
            # 4. 翻译文本
            translated_text = self.translation_service.translate_text(
                texts,
                target_language='zh-cn',
                use_batch=self.use_batch_translation
            )
            logger.info("翻译完成")
            
            # 5. 将翻译后的文本填充回字幕
            translated_subtitle_path = os.path.join(self.temp_dir, "translated_subtitles.srt")
            translated_subtitle_path = self.subtitle_processor.fill_subtitles(
                original_subs,
                translated_text,
                translated_subtitle_path
            )
            
            # 保存翻译后的字幕
            if self.save_intermediate:
                output_translated_srt = os.path.join(
                    self.output_dir,
                    f"{os.path.splitext(os.path.basename(input_path))[0]}_translated.srt"
                )
                self._save_file(translated_subtitle_path, output_translated_srt)
                logger.info(f"翻译字幕已保存: {output_translated_srt}")
            
            # 6. 生成配音
            dubbed_audio_path = os.path.join(self.temp_dir, "dubbed_audio.wav")
            dubbed_audio_path = self.tts_service.synthesize(
                translated_subtitle_path,
                target_language='zh-cn',
                voice_name=self.voice_name,
                output_path=dubbed_audio_path
            )
            logger.info("生成配音完成")
            
            # 7. 合成视频（使用减速后的视频）
            final_path = self.video_composer.compose(
                input_path,  # 使用减速后的视频路径
                dubbed_audio_path,
                translated_subtitle_path,
                output_path,
                remove_original_subs=self.remove_original_subs
            )
            
            logger.info(f"处理完成: {final_path}")
            return final_path
            
        except Exception as e:
            logger.error(f"处理失败: {str(e)}")
            raise
        finally:
            # 清理临时文件
            try:
                if os.path.exists(self.temp_dir):
                    for file in os.listdir(self.temp_dir):
                        try:
                            file_path = os.path.join(self.temp_dir, file)
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                        except Exception as e:
                            logger.warning(f"清理临时文件失败: {file_path} - {str(e)}")
                    try:
                        os.rmdir(self.temp_dir)
                    except Exception as e:
                        logger.warning(f"清理临时目录失败: {str(e)}")
            except Exception as e:
                logger.warning(f"清理临时文件过程出错: {str(e)}") 

    def _save_file(self, src_path: str, dst_path: str):
        """保存文件到输出目录"""
        try:
            import shutil
            shutil.copy2(src_path, dst_path)
        except Exception as e:
            logger.warning(f"保存文件失败 {dst_path}: {str(e)}") 