import whisper
import srt
from datetime import timedelta
from .utils.logger import setup_logger

logger = setup_logger(__name__)

class SubtitleGenerator:
    """字幕生成器"""
    
    def __init__(self):
        """初始化 Whisper 模型"""
        self.model = whisper.load_model("base")
    
    def generate(self, audio_path: str, output_path: str) -> str:
        """生成字幕文件"""
        try:
            # 使用 Whisper 识别音频
            result = self.model.transcribe(audio_path)
            
            # 转换为 SRT 格式
            subs = []
            for i, segment in enumerate(result["segments"], start=1):
                start = timedelta(seconds=segment["start"])
                end = timedelta(seconds=segment["end"])
                text = segment["text"].strip()
                
                sub = srt.Subtitle(
                    index=i,
                    start=start,
                    end=end,
                    content=text
                )
                subs.append(sub)
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subs))
            
            return output_path
            
        except Exception as e:
            logger.error(f"字幕生成失败: {str(e)}")
            raise 