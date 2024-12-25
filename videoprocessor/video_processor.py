import os
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
    
    def process(self, input_path: str, output_path: str) -> str:
        """处理视频"""
        try:
            # 创建临时目录
            temp_dir = os.path.join(os.path.dirname(output_path), '.temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # 1. 提取音频
            audio_path = os.path.join(temp_dir, "extracted_audio.wav")
            audio_path = self.audio_extractor.extract(input_path)
            logger.info("提取音频完成")
            
            # 2. 生成原始字幕
            original_subtitle_path = os.path.join(temp_dir, "original_subtitles.srt")
            original_subtitle_path = self.subtitle_generator.generate(
                audio_path,
                original_subtitle_path
            )
            logger.info("生成字幕完成")
            
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
            translated_subtitle_path = os.path.join(temp_dir, "translated_subtitles.srt")
            translated_subtitle_path = self.subtitle_processor.fill_subtitles(
                original_subs,
                translated_text,
                translated_subtitle_path
            )
            logger.info("生成翻译字幕完成")
            
            # 6. 生成配音
            dubbed_audio_path = os.path.join(temp_dir, "dubbed_audio.wav")
            dubbed_audio_path = self.tts_service.synthesize(
                translated_subtitle_path,
                target_language='zh-cn',
                output_path=dubbed_audio_path
            )
            logger.info("生成配音完成")
            
            # 7. 合成视频（使用翻译后的字幕）
            final_path = self.video_composer.compose(
                input_path,
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
                if os.path.exists(temp_dir):
                    for file in os.listdir(temp_dir):
                        try:
                            file_path = os.path.join(temp_dir, file)
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                        except Exception as e:
                            logger.warning(f"清理临时文件失败: {file_path} - {str(e)}")
                    try:
                        os.rmdir(temp_dir)
                    except Exception as e:
                        logger.warning(f"清理临时目录失败: {str(e)}")
            except Exception as e:
                logger.warning(f"清理临时文件过程出错: {str(e)}") 