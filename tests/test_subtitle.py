import os
import sys
import srt
from datetime import timedelta

def test_write_chinese_subtitle():
    """测试中文字幕写入"""
    try:
        # 创建测试目录
        os.makedirs('tests/output', exist_ok=True)
        
        # 创建测试字幕数据
        subtitles = [
            srt.Subtitle(
                index=1,
                start=timedelta(seconds=0),
                end=timedelta(seconds=3),
                content="这是第一行中文字幕测试"
            ),
            srt.Subtitle(
                index=2,
                start=timedelta(seconds=3),
                end=timedelta(seconds=6),
                content="第二行字幕，包含标点符号。"
            ),
            srt.Subtitle(
                index=3,
                start=timedelta(seconds=6),
                end=timedelta(seconds=9),
                content="第三行字幕！带有感叹号！"
            ),
            srt.Subtitle(
                index=4,
                start=timedelta(seconds=9),
                end=timedelta(seconds=12),
                content="第四行字幕？带有问号���"
            ),
            srt.Subtitle(
                index=5,
                start=timedelta(seconds=12),
                end=timedelta(seconds=15),
                content="最后一行中文字幕测试完成。"
            )
        ]
        
        # 测试不同编码方式
        encodings = ['utf-8-sig', 'utf-8', 'gbk']
        
        for encoding in encodings:
            # 生成输出文件路径
            output_path = f'tests/output/test_subtitle_{encoding}.srt'
            
            print(f"\n测试 {encoding} 编码:")
            print(f"写入文件: {output_path}")
            
            # 写入字幕文件
            with open(output_path, 'w', encoding=encoding, newline='\r\n') as f:
                f.write(srt.compose(subtitles))
            
            # 验证写入的文件
            print("验证文件内容:")
            with open(output_path, 'r', encoding=encoding) as f:
                content = f.read()
                parsed_subs = list(srt.parse(content))
                
                # 验证字幕数量
                if len(parsed_subs) != len(subtitles):
                    raise Exception(f"字幕数量不匹配: 期望 {len(subtitles)}, 实际 {len(parsed_subs)}")
                
                # 验证每条字幕的内容
                for i, (original, parsed) in enumerate(zip(subtitles, parsed_subs), 1):
                    print(f"第 {i} 条字幕: {parsed.content}")
                    if original.content != parsed.content:
                        raise Exception(f"字幕内容不匹配: \n期望: {original.content}\n实际: {parsed.content}")
            
            print(f"{encoding} 编码测试通过")
        
        print("\n所有编码测试通过!")
        return True
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_write_chinese_subtitle()
    sys.exit(0 if success else 1) 