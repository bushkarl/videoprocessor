import os
import sys
import argparse
from .video_processor import VideoProcessor
from .utils.logger import setup_logger

logger = setup_logger(__name__)

def get_output_path(input_path: str, step: str) -> str:
    """根据输入文件名和处理步骤生成输出文件名"""
    dirname = os.path.dirname(input_path) or '.'  # 如果没有目录则使用当前目录
    basename = os.path.splitext(os.path.basename(input_path))[0]
    
    step_suffix = {
        'extract_audio': '_audio.wav',
        'generate_srt': '_original.srt',
        'translate': '_translated.srt',
        'tts': '_dubbed.wav',
        'remove_subs': '_no_subs.mp4',
        'compose': '_final.mp4'
    }
    
    return os.path.join(dirname, basename + step_suffix.get(step, '.mp4'))

def main():
    parser = argparse.ArgumentParser(description='视频处理工具')
    parser.add_argument('input', help='输入视频文件路径')
    parser.add_argument('-o', '--output', help='输出视频文件路径')
    
    # 添加步骤选项
    parser.add_argument('--steps', nargs='+', choices=[
        'extract_audio',    # 提取音频
        'generate_srt',     # 生成字幕
        'translate',        # 翻译字幕
        'tts',             # 生成配音
        'remove_subs',      # 移除原字幕
        'compose',         # 合成视频
        'all'              # 执行所有步骤
    ], default=['all'], help='指定要执行的步骤')
    
    # 添加其他选项
    parser.add_argument('--remove-subs', action='store_true', help='移除原始字幕（默认保留）')
    parser.add_argument('--keep-temp', action='store_true', help='保留中间文件（默认删除）')
    
    args = parser.parse_args()
    
    try:
        # 验证输入文件存在
        if not os.path.exists(args.input):
            raise FileNotFoundError(f"输入文件不存在: {args.input}")
        
        processor = VideoProcessor()
        processor.remove_original_subs = args.remove_subs
        processor.keep_temp_files = args.keep_temp
        
        # 设置输出路径
        final_output = args.output or get_output_path(args.input, 'compose')
        
        if 'all' in args.steps:
            # 执行完整流程
            processor.process(args.input, final_output)
        else:
            # 执行选定的步骤
            results = {}
            
            # 1. 提取音频（如果需要）
            if 'extract_audio' in args.steps or 'generate_srt' in args.steps:
                audio_path = get_output_path(args.input, 'extract_audio')
                logger.info(f"开始提取音频到: {audio_path}")
                results['audio'] = processor.audio_extractor.extract(
                    video_path=args.input,
                    output_path=audio_path
                )
                logger.info(f"音频提取完成: {results['audio']}")
            
            # 2. 生成字幕
            if 'generate_srt' in args.steps:
                # 确保有音频文件
                if 'audio' not in results:
                    audio_path = get_output_path(args.input, 'extract_audio')
                    if os.path.exists(audio_path):
                        logger.info(f"使用已存在的音频文件: {audio_path}")
                        results['audio'] = audio_path
                    else:
                        logger.info("需要先提取音频")
                        results['audio'] = processor.audio_extractor.extract(
                            video_path=args.input,
                            output_path=audio_path
                        )
                
                srt_path = get_output_path(args.input, 'generate_srt')
                logger.info(f"开始生成字幕到: {srt_path}")
                results['srt'] = processor.subtitle_generator.generate(
                    audio_path=results['audio'],
                    output_path=srt_path
                )
                logger.info(f"字幕生成完成: {results['srt']}")
            
            # 3. 翻译字幕
            if 'translate' in args.steps:
                # 确保有原始字幕
                if 'srt' not in results:
                    srt_path = get_output_path(args.input, 'generate_srt')
                    if not os.path.exists(srt_path):
                        raise Exception("需要先生成原始字幕文件")
                    results['srt'] = srt_path
                
                translated_path = get_output_path(args.input, 'translate')
                logger.info(f"开始翻译字幕到: {translated_path}")
                subs, texts = processor.subtitle_processor.process(results['srt'])
                translated_text = processor.translation_service.translate_text(
                    texts,
                    target_language='zh-cn'
                )
                results['translated_srt'] = processor.subtitle_processor.fill_subtitles(
                    subs,
                    translated_text,
                    translated_path
                )
                logger.info(f"字幕翻译完成: {results['translated_srt']}")
            
            if 'tts' in args.steps:
                if 'translated_srt' not in results:
                    translated_path = get_output_path(args.input, 'translate')
                    if not os.path.exists(translated_path):
                        raise Exception("需要先生成翻译字幕文件")
                    results['translated_srt'] = translated_path
                
                dubbed_path = get_output_path(args.input, 'tts')
                results['dubbed_audio'] = processor.tts_service.synthesize(
                    results['translated_srt'],
                    target_language='zh-cn',
                    output_path=dubbed_path
                )
                logger.info(f"配音生成完成: {results['dubbed_audio']}")
            
            if 'remove_subs' in args.steps:
                no_subs_path = get_output_path(args.input, 'remove_subs')
                results['no_subs_video'] = processor.video_composer._remove_subtitles(
                    args.input,
                    no_subs_path
                )
                logger.info(f"字幕移除完成: {results['no_subs_video']}")
            
            if 'compose' in args.steps:
                if 'dubbed_audio' not in results or 'translated_srt' not in results:
                    raise Exception("需要先生成配音和翻译字幕文件")
                
                input_video = results.get('no_subs_video', args.input)
                results['final_video'] = processor.video_composer.compose(
                    input_video,
                    results['dubbed_audio'],
                    results['translated_srt'],
                    final_output,
                    remove_original_subs=args.remove_subs
                )
                logger.info(f"视频合成完成: {results['final_video']}")
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"处理失败: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 