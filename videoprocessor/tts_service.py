import os
import srt
import asyncio
from datetime import timedelta
from edge_tts import Communicate
from pydub import AudioSegment
import soundfile as sf
import io
from concurrent.futures import ThreadPoolExecutor
from .utils.logger import setup_logger

logger = setup_logger(__name__)

class TextToSpeechService:
    """文本转语音服务"""
    
    def __init__(self):
        # 支持的语音列表
        self.voice_map = {
            'zh': {
                'xiaoxiao': 'zh-CN-XiaoxiaoNeural',  # 晓晓 - 女声
                'xiaoyi': 'zh-CN-XiaoyiNeural',      # 晓伊 - 女声
                'xiaoxuan': 'zh-CN-XiaoxuanNeural',  # 晓萱 - 女声
                'xiaozhen': 'zh-CN-XiaozhenNeural',  # 晓甄 - 女声
                'yunxi': 'zh-CN-YunxiNeural',        # 云希 - 男声
                'yunxia': 'zh-CN-YunxiaNeural',      # 云夏 - 男声
                'yunyang': 'zh-CN-YunyangNeural',    # 云扬 - 男声
            },
            'en': {
                'jenny': 'en-US-JennyNeural',        # Jenny - 女声
                'aria': 'en-US-AriaNeural',          # Aria - 女声
                'guy': 'en-US-GuyNeural',            # Guy - 男声
            },
            'ja': {
                'nanami': 'ja-JP-NanamiNeural',      # Nanami - 女声
                'keita': 'ja-JP-KeitaNeural',        # Keita - 男声
            },
            'ko': {
                'sunhi': 'ko-KR-SunHiNeural',        # SunHi - 女声
                'inpyo': 'ko-KR-InPyoNeural',        # InPyo - 男声
            }
        }
        
        # 默认语音
        self.default_voices = {
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
        self.min_speed = 0  # 最小语速
        self.max_speed = 20  # 最大语速
        self.speed_adjust_factor = 0.9  # 语速调整系数
        self.max_speed_diff = 10  # 相邻字幕最大语速差异（百分比）
        
        # 并发控制参数
        self.max_workers = 5  # 最大并发数
        self.chunk_size = 10  # 每批处理的字幕数
        
        self.current_language = 'zh-cn'  # 添加当前语言属性
        
        # 重试设置
        self.max_retries = 3
        self.retry_delay = 2  # 秒
        self.retry_backoff = 1.5  # 重试延迟增长因子
    
    def get_voice(self, language: str, voice_name: str = None) -> str:
        """获取语音标识符"""
        try:
            language = language.lower()
            # 将 zh-cn 映射到 zh
            if language == 'zh-cn':
                language = 'zh'
            
            if voice_name:
                # 如果指定了具体的语音名称
                voice_name = voice_name.lower()
                logger.info(f"尝试使用指定语音: {voice_name}")
                
                if language in self.voice_map:
                    if voice_name in self.voice_map[language]:
                        selected_voice = self.voice_map[language][voice_name]
                        logger.info(f"使用语音: {voice_name} ({selected_voice})")
                        return selected_voice
                    else:
                        available_voices = list(self.voice_map[language].keys())
                        logger.warning(
                            f"指定的语音 {voice_name} 不可用，"
                            f"可用选项: {', '.join(available_voices)}"
                        )
            
            # 返回默认语音
            default_voice = self.default_voices.get(language, 'zh-CN-XiaoxiaoNeural')
            logger.info(f"使用默认语音: {default_voice}")
            return default_voice
            
        except Exception as e:
            logger.error(f"获取语音标识符失败: {str(e)}")
            return 'zh-CN-XiaoxiaoNeural'  # 出错时使用默认语音
    
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
    
    async def _generate_audio_with_retry(self, text: str, voice: str, rate: str, output_path: str):
        """带重试机制的音频生成"""
        last_error = None
        delay = self.retry_delay
        
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    logger.info(f"第 {attempt + 1} 次重试生成音频...")
                
                # 创建通信对象
                communicate = Communicate(text, voice, rate=rate)
                temp_mp3 = f"{output_path}.mp3"
                await communicate.save(temp_mp3)
                
                # 如果成功生成，处理音频格式
                audio = AudioSegment.from_mp3(temp_mp3)
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
                
                return True
                
            except Exception as e:
                last_error = e
                logger.warning(f"音频生成失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                
                if attempt < self.max_retries - 1:
                    # 使用指数退避策略
                    await asyncio.sleep(delay)
                    delay *= self.retry_backoff
                
        # 所有重试都失败
        raise Exception(f"音频生成失败，已重试 {self.max_retries} 次: {str(last_error)}")
    
    async def _generate_audio(self, text: str, rate: str, output_path: str, target_language: str, voice_name: str = None):
        """生成单个音频片段"""
        try:
            voice = self.get_voice(target_language, voice_name)
            
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
                # 使用重试机制生成音频
                await self._generate_audio_with_retry(text, voice, rate, output_path)
            
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
                # ���取音频段
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
    
    def _smooth_rates(self, subtitles: list) -> list:
        """平滑相邻字幕的语速差异，优先降低较快的语速"""
        rates = []
        
        # 第一遍：计算初始语速
        for subtitle in subtitles:
            if not subtitle.content.strip():
                rates.append("+0%")
                continue
            
            rate = self._calculate_rate(subtitle.content, subtitle.end - subtitle.start)
            rates.append(rate)
        
        # 第二遍：平滑处理
        smoothed_rates = rates.copy()
        for i in range(1, len(rates)):
            prev_rate = int(smoothed_rates[i-1].rstrip('%').lstrip('+'))
            curr_rate = int(rates[i].rstrip('%').lstrip('+'))
            
            # 计算语速差异
            rate_diff = abs(curr_rate - prev_rate)
            
            # 如果差异超过阈值，调整语速
            if rate_diff > self.max_speed_diff:
                # 优先降低较快的语速
                if curr_rate > prev_rate:
                    # 当前语速更快，降低当前语速
                    new_rate = prev_rate + self.max_speed_diff
                    smoothed_rates[i] = f"{new_rate:+d}%"
                    logger.info(
                        f"平滑语速(降速): 字幕{i} "
                        f"原始语速={curr_rate:+d}% -> "
                        f"调整后={new_rate:+d}% "
                        f"(前一字幕={prev_rate:+d}%)"
                    )
                else:
                    # 前一个语速更快，尝试降低前一个语速
                    new_prev_rate = curr_rate + self.max_speed_diff
                    if new_prev_rate >= self.min_speed:
                        smoothed_rates[i-1] = f"{new_prev_rate:+d}%"
                        logger.info(
                            f"平滑语速(降速): 字幕{i-1} "
                            f"原始语速={prev_rate:+d}% -> "
                            f"调整后={new_prev_rate:+d}% "
                            f"(后一字幕={curr_rate:+d}%)"
                        )
                    else:
                        # 如果前一个语速无法降低，才提高当前语速
                        new_rate = prev_rate - self.max_speed_diff
                        smoothed_rates[i] = f"{new_rate:+d}%"
                        logger.info(
                            f"平滑语速(升速): 字幕{i} "
                            f"原始语速={curr_rate:+d}% -> "
                            f"调整后={new_rate:+d}% "
                            f"(前一字幕={prev_rate:+d}%)"
                        )
                
                # 确保所有语速都在允许范围内
                for j in range(max(0, i-1), i+1):
                    rate_value = int(smoothed_rates[j].rstrip('%').lstrip('+'))
                    rate_value = max(self.min_speed, min(self.max_speed, rate_value))
                    smoothed_rates[j] = f"{rate_value:+d}%"
        
        return smoothed_rates
    
    async def _generate_audio_chunk(self, subtitles: list, temp_dir: str, target_language: str, voice_name: str = None) -> list:
        """并发生成一组音频"""
        # 计算平滑后的语速
        rates = self._smooth_rates(subtitles)
        
        tasks = []
        for i, (subtitle, rate) in enumerate(zip(subtitles, rates)):
            if not subtitle.content.strip():
                continue
            
            temp_path = os.path.join(temp_dir, f"temp_{subtitle.index}.wav")
            
            task = asyncio.create_task(self._generate_audio(
                text=subtitle.content,
                rate=rate,
                output_path=temp_path,
                target_language=target_language,
                voice_name=voice_name
            ))
            tasks.append((subtitle, temp_path, task))
        
        results = []
        for subtitle, temp_path, task in tasks:
            try:
                await task
                results.append({
                    'path': temp_path,
                    'start_time': subtitle.start,
                    'end_time': subtitle.end
                })
                logger.info(f"音频片段生成成功: {temp_path}")
            except Exception as e:
                logger.error(f"生成音频片段失败: {str(e)}")
                if not getattr(self, 'ignore_errors', False):
                    raise
        
        return results
    
    async def _process_subtitles(self, subs: list, temp_dir: str, target_language: str, voice_name: str = None) -> list:
        """分批处理字幕"""
        all_segments = []
        total_subs = len(subs)
        
        for i in range(0, total_subs, self.chunk_size):
            chunk = subs[i:i + self.chunk_size]
            logger.info(f"处理字幕批次 {i+1}-{min(i+self.chunk_size, total_subs)}/{total_subs}")
            
            # 并发生成这一批的音频
            segments = await self._generate_audio_chunk(
                chunk, 
                temp_dir,
                target_language=target_language,
                voice_name=voice_name
            )
            all_segments.extend(segments)
            
            # 简单的速率限制
            await asyncio.sleep(0.5)
        
        return all_segments
    
    def synthesize(self, srt_path: str, target_language: str = 'zh-cn', 
                  voice_name: str = None, output_path: str = None) -> str:
        """将字幕文件转换为语音"""
        try:
            # 获取语音标识符
            logger.info(f"请求语音: {voice_name or '默认'}")
            voice = self.get_voice(target_language, voice_name)
            logger.info(f"最终使用语音: {voice}")
            
            # 读取字幕文件
            with open(srt_path, 'r', encoding='utf-8-sig') as f:
                subs = list(srt.parse(f.read()))
            
            logger.info(f"开始处理 {len(subs)} 条字幕")
            
            # 创建临时目录
            temp_dir = "temp_audio"
            os.makedirs(temp_dir, exist_ok=True)
            
            # 使用事件循环处理所有字幕
            audio_segments = asyncio.run(self._process_subtitles(
                subs, 
                temp_dir,
                target_language=target_language,
                voice_name=voice_name
            ))
            
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
                    try:
                        os.remove(os.path.join(temp_dir, file))
                    except Exception as e:
                        logger.warning(f"清理临时文件失败: {str(e)}")
                try:
                    os.rmdir(temp_dir)
                except Exception as e:
                    logger.warning(f"清理临时目录失败: {str(e)}") 