import os
import srt
import re
from datetime import timedelta
from .utils.logger import setup_logger

logger = setup_logger(__name__)

class SubtitleProcessor:
    """字幕处理器"""
    
    def __init__(self):
        # 基础配置
        self.cn_punctuation = '。！？；'
        self.en_punctuation = '.!?;'
        self.max_chars = 50  # 单条字幕最大字符数
        self.merge_threshold = 200  # 合并阈值(毫秒)
        self.batch_size = 5  # 每批最多5条字幕
        self.max_chars_per_batch = 500  # 每批最大字符数
        self.use_batch_translation = False  # 默认使用逐句翻译
        
        # 存储原始字幕的时间信息
        self.original_timings = {}  # {index: (start, end)}
    
    def _store_original_timings(self, subs: list):
        """存储原始字幕的时间信息"""
        self.original_timings = {
            sub.index: (sub.start, sub.end)
            for sub in subs
        }
    
    def _merge_subtitles(self, subs: list) -> list:
        """智能合并字幕，但保持原始时间轴"""
        if not subs:
            return []
        
        # 先存储原始时间信息
        self._store_original_timings(subs)
        
        merged = []
        current = subs[0]
        buffer_text = current.content
        buffer_start = current.start
        buffer_end = current.end
        
        for next_sub in subs[1:]:
            time_gap = (next_sub.start - buffer_end).total_seconds() * 1000
            potential_text = f"{buffer_text} {next_sub.content}"
            
            if (time_gap <= self.merge_threshold and 
                len(potential_text) <= self.max_chars and
                buffer_text[-1] not in f"{self.cn_punctuation}{self.en_punctuation}"):
                # 合并文本，扩展时间范围
                buffer_text = potential_text
                buffer_end = next_sub.end
            else:
                # 添加当前缓冲区的字幕
                merged.append(srt.Subtitle(
                    index=len(merged) + 1,
                    start=buffer_start,
                    end=buffer_end,
                    content=buffer_text
                ))
                # 重置缓冲区
                buffer_text = next_sub.content
                buffer_start = next_sub.start
                buffer_end = next_sub.end
        
        # 添加最后一条字幕
        merged.append(srt.Subtitle(
            index=len(merged) + 1,
            start=buffer_start,
            end=buffer_end,
            content=buffer_text
        ))
        
        return merged
    
    def _restore_timings(self, translated_subs: list, original_subs: list) -> list:
        """将翻译后的字幕时间还原为原始时间"""
        if len(translated_subs) != len(original_subs):
            logger.warning(f"翻译前后字幕数量不匹配: {len(original_subs)} -> {len(translated_subs)}")
            # 如果数量不匹配，使用原始字幕的时间轴
            restored = []
            for i, trans_sub in enumerate(translated_subs):
                if i < len(original_subs):
                    restored.append(srt.Subtitle(
                        index=i + 1,
                        start=original_subs[i].start,
                        end=original_subs[i].end,
                        content=trans_sub.content
                    ))
            return restored
        
        # 数量匹配时，直接使用原始时间
        restored = []
        for i, (trans_sub, orig_sub) in enumerate(zip(translated_subs, original_subs)):
            restored.append(srt.Subtitle(
                index=i + 1,
                start=orig_sub.start,
                end=orig_sub.end,
                content=trans_sub.content
            ))
        return restored
    
    def _merge_subtitle_texts(self, subs: list) -> list:
        """将字幕文本分批合并，每批控制在5句话以内"""
        merged_batches = []
        current_batch = []
        current_chars = 0
        
        for sub in subs:
            text = sub.content.strip()
            if not text:
                continue
            
            # 如果当前批次已达到限制，创建新批次
            if (len(current_batch) >= self.batch_size or 
                current_chars + len(text) > self.max_chars_per_batch):
                if current_batch:
                    merged_batches.append('\n'.join(current_batch))
                current_batch = [text]
                current_chars = len(text)
            else:
                current_batch.append(text)
                current_chars += len(text)
        
        # 添加最后一批
        if current_batch:
            merged_batches.append('\n'.join(current_batch))
        
        # 计算平均每批句子数
        total_sentences = sum(len(batch.split('\n')) for batch in merged_batches)
        avg_sentences = total_sentences / len(merged_batches) if merged_batches else 0
        
        logger.info(
            f"字幕分批完成: {len(merged_batches)} 批, "
            f"平均每批 {avg_sentences:.1f} 句"
        )
        
        return merged_batches
    
    def _split_translated_text(self, translated_text: str) -> list:
        """将翻译后的文本分割回字幕列表"""
        return [text.strip() for text in translated_text.split('\n') if text.strip()]
    
    def _fill_translations(self, original_subs: list, translated_texts: list) -> list:
        """将翻译后的文本填充回原始字幕的时间轴"""
        if len(original_subs) != len(translated_texts):
            logger.warning(f"翻译前后字幕数量不匹配: {len(original_subs)} -> {len(translated_texts)}")
        
        filled_subs = []
        for i, orig_sub in enumerate(original_subs):
            if i < len(translated_texts):
                filled_subs.append(srt.Subtitle(
                    index=orig_sub.index,
                    start=orig_sub.start,
                    end=orig_sub.end,
                    content=translated_texts[i]
                ))
            else:
                # 如果翻译文本不够，使用原文
                filled_subs.append(orig_sub)
        
        return filled_subs
    
    def process(self, input_path: str, use_batch: bool = False) -> tuple:
        """处理字幕文件，返回原始字幕和待翻译文本"""
        try:
            # 读取字幕文件
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()
                subtitles = list(srt.parse(content))
            
            logger.info(f"开始处理 {len(subtitles)} 条字幕")
            
            # 提取文本
            texts = [sub.content.strip() for sub in subtitles]
            
            if use_batch:
                # 批量处理
                batches = []
                current_batch = []
                current_chars = 0
                
                for text in texts:
                    text_chars = len(text)
                    if current_chars + text_chars > self.max_chars_per_batch:
                        if current_batch:  # 当前批次不为空时添加
                            batches.append('\n'.join(current_batch))
                            current_batch = [text]
                            current_chars = text_chars
                    else:
                        current_batch.append(text)
                        current_chars += text_chars
                
                # 添加最后一批
                if current_batch:
                    batches.append('\n'.join(current_batch))
                
                logger.info(f"字幕分批完成: {len(batches)} 批, 平均每批 {len(texts)/len(batches):.1f} 句")
                return subtitles, batches
            else:
                # 逐句处理
                logger.info("合并为 1 批文本")
                return subtitles, texts
            
        except Exception as e:
            logger.error(f"字幕处理失败: {str(e)}")
            raise
    
    def fill_subtitles(self, original_subs: list, translated_text: str, output_path: str) -> str:
        """将翻译后的文本填充回原始字幕"""
        try:
            # 分割翻译后的文本
            translated_texts = translated_text.strip().split('\n')
            
            # 验证翻译文本数量
            if len(translated_texts) != len(original_subs):
                raise Exception(
                    f"翻译文本数量与原始字幕不匹配: "
                    f"原始字幕 {len(original_subs)} 条, "
                    f"翻译文本 {len(translated_texts)} 条"
                )
            
            # 填充翻译文本到原始字幕
            filled_subs = []
            for i, (sub, trans_text) in enumerate(zip(original_subs, translated_texts), 1):
                new_sub = srt.Subtitle(
                    index=i,
                    start=sub.start,
                    end=sub.end,
                    content=trans_text.strip()
                )
                filled_subs.append(new_sub)
                logger.debug(f"字幕 {i}: {trans_text.strip()}")
            
            # 写入新的字幕文件
            with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(srt.compose(filled_subs))
            
            # 验证生成的字幕文件
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.info(f"生成的字幕文件预览:\n{content[:500]}")
            
            logger.info(f"字幕填充完成: {len(filled_subs)} 条")
            return output_path
            
        except Exception as e:
            logger.error(f"字幕填充失败: {str(e)}")
            raise 