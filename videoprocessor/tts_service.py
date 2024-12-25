import os
import srt
from datetime import timedelta
from edge_tts import Communicate
import asyncio
from pydub import AudioSegment
import soundfile as sf
import io
from .utils.logger import setup_logger
import subprocess

logger = setup_logger(__name__)

class TextToSpeechService:
    """文本转语音服务"""
    
    def __init__(self):
        self.voice_map = {
            'zh': 'zh-CN-XiaoxiaoNeural',
            'zh-cn': 'zh-CN-XiaoxiaoNeural',
            'en': 'en-US-JennyNeural',
            'ja': 'ja-JP-NanamiNeural',
            'ko': 'ko-KR-SunHiNeural'
        }
        # 音频参数
        self.sample_rate = 44100
        self.channels = 2
        # 语速控制参数
        self.min_speed = -5  # 最大减速比例
        self.max_speed = 25   # 最大加速比例
        self.speed_adjust_factor = 0.9  # 语速调整系数，降低调整幅度
    
    def _calculate_rate(self, text: str, duration: timedelta) -> str:
        """根据字幕时间计算语速"""
        try:
            # 如果文本为空，返回默认语速
            if not text or not text.strip():
                return "+0%"
                
            char_count = len(text)
            target_duration = duration.total_seconds()
            
            if target_duration <= 0:
                logger.warning("字幕时长为0，使用默认语速")
                return "+0%"
            
            # 计算当前语速（字符/秒）
            current_speed = char_count / target_duration
            
            # 根据字幕长度动态调整目标语速
            if char_count < 20:
                target_speed = 3.5  # 短句用较慢语速
            # elif char_count < 20:
            #     target_speed = 3.5  # 中等句子用中等语速
            else:
                target_speed = 4.0  # 长句用较快语速
            
            # 计算需要的语速调整比例
            speed_diff = (current_speed / target_speed - 1)
            rate_percent = int(speed_diff * 100 * self.speed_adjust_factor)
            
            # 限制语速调整范围
            rate_percent = max(self.min_speed, min(self.max_speed, rate_percent))
            
            # 对于较短的文本，进一步降低调整幅度
            # if char_count < 5:
            #     rate_percent = int(rate_percent * 0.7)
            # elif char_count < 10:
            #     rate_percent = int(rate_percent * 0.8)
            
            # 记录详细的语速信息
            logger.info(
                f"语速调整: 文本长度={char_count}字, "
                f"目标时长={target_duration:.1f}秒, "
                f"当前语速={current_speed:.1f}字/秒, "
                f"目标语速={target_speed}字/秒, "
                f"调整比例={rate_percent:+d}%"
            )
            
            return f"{rate_percent:+d}%"
            
        except Exception as e:
            logger.error(f"语速计算失败: {str(e)}")
            return "+0%"  # 出错时使用默认语速
    
    async def _generate_audio(self, text: str, rate: str, output_path: str):
        """生成单个音频片段"""
        try:
            voice = self.voice_map['zh']
            
            # 解析语速值
            rate_value = int(rate.rstrip('%').lstrip('+'))
            
            # 对较大的语速调整进行分段处理
            if abs(rate_value) > 20:
                # 第一步：使用温和的语速调整
                base_rate = f"{int(rate_value * 0.7):+d}%"
                communicate = Communicate(text, voice, rate=base_rate)
                
                # 生成临时文件
                temp_mp3 = f"{output_path}.mp3"
                await communicate.save(temp_mp3)
                
                # 使用 pydub 进行剩余的调整
                audio = AudioSegment.from_mp3(temp_mp3)
                
                # 计算剩余需要调整的比例
                remaining_adjust = (rate_value - int(rate_value * 0.7)) / 100
                if remaining_adjust > 0:
                    audio = audio.speedup(playback_speed=1.0 + remaining_adjust)
                elif remaining_adjust < 0:
                    audio = audio.speedup(playback_speed=1.0 / (1.0 - remaining_adjust))
            else:
                # 对于温和的语速调整直接使用 edge-tts
                communicate = Communicate(text, voice, rate=rate)
                temp_mp3 = f"{output_path}.mp3"
                await communicate.save(temp_mp3)
                audio = AudioSegment.from_mp3(temp_mp3)
            
            # 统一处理音频格式
            audio = audio.set_frame_rate(self.sample_rate)
            audio = audio.set_channels(self.channels)
            
            # 导出为 WAV 格式
            audio.export(
                output_path,
                format='wav',
                parameters=[
                    "-ar", str(self.sample_rate),
                    "-ac", str(self.channels),
                    "-acodec", "pcm_s16le"
                ]
            )
            
            # 删除临时文件
            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)
            
            logger.info(f"音频片段生成成功: {output_path}")
            
        except Exception as e:
            logger.error(f"音频生成失败: {str(e)}")
            raise
    
    def _merge_audio_files(self, audio_segments: list, output_path: str):
        """合并音频片段"""
        try:
            # 创建足够长的空白音频
            total_duration = max(seg['end_time'] for seg in audio_segments)
            total_ms = int(total_duration.total_seconds() * 1000)
            merged = AudioSegment.silent(duration=total_ms, 
                                       frame_rate=self.sample_rate)
            
            # 在正确的时间点插入每个音频片段
            for seg in audio_segments:
                # 读取音频片段
                audio = AudioSegment.from_wav(seg['path'])
                
                # 确保音频格式一致
                audio = audio.set_frame_rate(self.sample_rate)
                audio = audio.set_channels(self.channels)
                
                # 插入到正确的位置
                position = int(seg['start_time'].total_seconds() * 1000)
                merged = merged.overlay(audio, position=position)
            
            # 导出最终的音频文件
            merged.export(
                output_path,
                format="wav",
                parameters=[
                    "-ar", str(self.sample_rate),
                    "-ac", str(self.channels),
                    "-acodec", "pcm_s16le"
                ]
            )
            
            # 验证最终文件
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise Exception("最终音频文件生成失败")
                
            logger.info(f"音频合并完成: {output_path}")
            
        except Exception as e:
            logger.error(f"音频合并失败: {str(e)}")
            raise
    
    def _synthesize_subtitle(self, text: str, rate: str, output_path: str) -> str:
        """合成单条字幕的语音"""
        try:
            # 如果文本为空，生成静音片段
            if not text or not text.strip():
                logger.info("空字幕，生成静音片段")
                return self._generate_silence(output_path)
                
            # 计算这段文本需要的语速
            rate = self._calculate_rate(text, timedelta(seconds=len(text) / 4))
            logger.info(f"字幕 语速调整: {rate}")
            
            # 生成音频
            asyncio.run(self._generate_audio(text, rate, output_path))
            
            logger.info(f"音频片段生成成功: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"字幕合成失败: {str(e)}")
            raise
    
    def _generate_silence(self, output_path: str) -> str:
        """生成静音音频片段"""
        try:
            command = [
                'ffmpeg',
                '-f', 'lavfi',           # 使用 lavfi 输入
                '-i', 'anullsrc=r=44100:cl=stereo',  # 生成静音
                '-t', '0.5',             # 持续时间（秒）
                '-acodec', 'pcm_s16le',  # 音频编码
                '-y',                    # 覆盖已存在的文件
                output_path
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"静音生成失败: {result.stderr}")
                raise Exception(f"静音生成失败: {result.stderr}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"静音生成失败: {str(e)}")
            raise
    
    def synthesize(self, srt_path: str, target_language: str = 'zh-cn', output_path: str = None) -> str:
        """将字幕文件转换为语音"""
        try:
            # 读取字幕文件
            with open(srt_path, 'r', encoding='utf-8-sig') as f:
                subs = list(srt.parse(f.read()))
            
            logger.info(f"开始处理 {len(subs)} 条字幕")
            
            # 创建临时目录
            temp_dir = "temp_audio"
            os.makedirs(temp_dir, exist_ok=True)
            
            # 存储所有音频片段的信息
            audio_segments = []
            
            # 处理每条字幕
            for i, subtitle in enumerate(subs, 1):
                try:
                    # 跳过空字幕
                    if not subtitle.content or not subtitle.content.strip():
                        logger.info(f"跳过空字幕 {i}/{len(subs)}")
                        continue
                        
                    temp_path = os.path.join(temp_dir, f"temp_{i}.wav")
                    
                    # 计算这段文本需要的语速
                    rate = self._calculate_rate(subtitle.content, subtitle.end - subtitle.start)
                    logger.info(f"字幕 {i}/{len(subs)} 语速调整: {rate}")
                    
                    # 生成音频
                    self._synthesize_subtitle(subtitle.content, rate, temp_path)
                    
                    # 记录音频片段信息
                    audio_segments.append({
                        'path': temp_path,
                        'start_time': subtitle.start,
                        'end_time': subtitle.end
                    })
                    
                except Exception as e:
                    logger.error(f"处理字幕 {i}/{len(subs)} 失败: {str(e)}")
                    if not self.ignore_errors:
                        raise
            
            # 合并所有音频片段
            self._merge_audio_files(audio_segments, output_path)
            
            logger.info("语音合成完成")
            return output_path
            
        except Exception as e:
            logger.error(f"语音合成失败: {str(e)}")
            raise
        finally:
            # 清理临时文件
            if os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir) 