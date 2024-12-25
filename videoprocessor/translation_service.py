import os
import srt
import time
from translate import Translator
from googletrans import Translator as GoogleTranslator
import requests
from .utils.logger import setup_logger

logger = setup_logger(__name__)

class TranslationService:
    """翻译服务"""
    
    def __init__(self):
        """初始化翻译服务"""
        self.max_retries = 3
        self.retry_delay = 2  # 秒
        self.batch_size = 10  # 每次翻译5批
        self.request_interval = 1.5  # 请求间隔加大到1.5秒
        
        # 语言代码映射
        self.language_map = {
            'zh-cn': {'google': 'zh-cn', 'translate': 'zh', 'youdao': 'zh-CHS'},
            'zh-CN': {'google': 'zh-cn', 'translate': 'zh', 'youdao': 'zh-CHS'},
            'en': {'google': 'en', 'translate': 'en', 'youdao': 'en'},
            'ja': {'google': 'ja', 'translate': 'ja', 'youdao': 'ja'},
            'ko': {'google': 'ko', 'translate': 'ko', 'youdao': 'ko'}
        }
        
        # 翻译服务列表
        self.translators = [
            self._translate_with_google,
            self._translate_with_translate,
            self._translate_with_youdao
        ]
    
    def _normalize_language_code(self, language_code: str, service: str) -> str:
        """标准化语言代码"""
        language_code = language_code.lower()
        if language_code in self.language_map:
            return self.language_map[language_code][service]
        return language_code
    
    def _translate_with_google(self, text: str, target_language: str) -> str:
        """使用 Google Translate"""
        try:
            translator = GoogleTranslator()
            result = translator.translate(
                text,
                dest=self._normalize_language_code(target_language, 'google')
            )
            return result.text
        except Exception as e:
            logger.warning(f"Google翻译失败: {str(e)}")
            raise
    
    def _translate_with_translate(self, text: str, target_language: str) -> str:
        """使用 translate 库"""
        try:
            translator = Translator(
                to_lang=self._normalize_language_code(target_language, 'translate')
            )
            return translator.translate(text)
        except Exception as e:
            logger.warning(f"translate库翻译失败: {str(e)}")
            raise
    
    def _translate_with_youdao(self, text: str, target_language: str) -> str:
        """使用有道翻译"""
        try:
            response = requests.post(
                'http://fanyi.youdao.com/translate',
                data={
                    'doctype': 'json',
                    'type': 'AUTO',
                    'i': text,
                    'to': self._normalize_language_code(target_language, 'youdao')
                },
                timeout=10
            )
            
            result = response.json()
            if not result or 'translateResult' not in result:
                raise Exception("翻译返回数据格式错误")
            
            return result['translateResult'][0][0]['tgt']
        except Exception as e:
            logger.warning(f"有道翻译失败: {str(e)}")
            raise
    
    def _try_translate(self, text: str, target_language: str) -> str:
        """尝试使用不同的翻译服务"""
        last_error = None
        
        for translator in self.translators:
            for retry in range(self.max_retries):
                try:
                    result = translator(text, target_language)
                    if result:
                        return result
                except Exception as e:
                    last_error = e
                    logger.warning(f"翻译重试 ({retry+1}/{self.max_retries}): {str(e)}")
                    time.sleep(self.retry_delay)
            
            logger.warning(f"切换下一个翻译服务")
        
        raise Exception(f"所有翻译服务都失败: {str(last_error)}")
    
    def translate_text(self, texts: list, target_language: str = 'zh-cn', use_batch: bool = False) -> str:
        """翻译文本"""
        try:
            logger.info(f"翻译目标语言: {target_language}")
            
            if use_batch:
                return self._batch_translate(texts, target_language)
            else:
                return self._single_translate(texts, target_language)
                
        except Exception as e:
            logger.error(f"翻译失败: {str(e)}")
            raise
    
    def _single_translate(self, texts: list, target_language: str) -> str:
        """逐句翻译"""
        translated_texts = []
        total_texts = len(texts)
        
        for i, text in enumerate(texts, 1):
            logger.info(f"正在翻译第 {i}/{total_texts} 条字幕")
            translated_text = self._try_translate(text, target_language)
            translated_texts.append(translated_text)
            time.sleep(self.request_interval)
        
        logger.info(f"翻译完成，共处理 {len(translated_texts)} 条字幕")
        return '\n'.join(translated_texts)
    
    def _batch_translate(self, text_batches: list, target_language: str) -> str:
        """批量翻译"""
        translated_batches = []
        total_batches = len(text_batches)
        
        for i in range(0, total_batches, self.batch_size):
            current_group = text_batches[i:i + self.batch_size]
            batch_start = i + 1
            batch_end = min(i + self.batch_size, total_batches)
            logger.info(f"正在处理第 {batch_start}-{batch_end}/{total_batches} 批文本")
            
            group_results = []
            for batch in current_group:
                translated_text = self._try_translate(batch, target_language)
                group_results.append(translated_text)
                time.sleep(self.request_interval)
            
            translated_batches.extend(group_results)
            logger.info(f"完成第 {batch_start}-{batch_end} 批翻译")
        
        final_text = '\n'.join(translated_batches)
        logger.info(f"翻译完成，共处理 {len(translated_batches)} 批文本")
        return final_text
    
    def translate(self, subtitle_path: str, target_language: str, output_path: str) -> str:
        """翻译字幕文件"""
        try:
            # 读取字幕文件
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subs = list(srt.parse(f.read()))
            
            logger.info(f"开始翻译 {len(subs)} 条字幕")
            
            # 翻译每个字幕
            translated_subs = []
            for i, sub in enumerate(subs, 1):
                logger.info(f"翻译第 {i}/{len(subs)} 条字幕")
                translated_text = self.translate_text(sub.content, target_language)
                new_sub = srt.Subtitle(
                    index=sub.index,
                    start=sub.start,
                    end=sub.end,
                    content=translated_text
                )
                translated_subs.append(new_sub)
            
            # 写入翻译后的字幕
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(srt.compose(translated_subs))
            
            logger.info("字幕翻译完成")
            return output_path
            
        except Exception as e:
            logger.error(f"字幕翻译失败: {str(e)}")
            raise 