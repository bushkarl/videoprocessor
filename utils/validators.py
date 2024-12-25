import os
from typing import List
import magic

def validate_video_file(file_path: str) -> bool:
    """
    验证视频文件
    
    Args:
        file_path: 视频文件路径
        
    Returns:
        bool: 文件是否有效
        
    Raises:
        ValueError: 当文件无效时
    """
    if not os.path.exists(file_path):
        raise ValueError(f"文件不存在: {file_path}")
    
    # 获取文件 MIME 类型
    mime = magic.Magic(mime=True)
    file_type = mime.from_file(file_path)
    
    # 支持的视频格式
    valid_types = [
        'video/mp4',
        'video/mpeg',
        'video/x-msvideo',
        'video/quicktime'
    ]
    
    if file_type not in valid_types:
        raise ValueError(
            f"不支持的文件格式: {file_type}\n"
            f"支持的格式: {', '.join(valid_types)}"
        )
    
    return True 