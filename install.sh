#!/bin/bash

# 检查并安装 Python 3.11
if ! command -v python3.11 &> /dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install python@3.11
        # 强制链接 Python 3.11
        brew unlink python@3.13 || true
        brew link python@3.11
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo apt-get update
        sudo apt-get install -y python3.11 python3.11-venv
    fi
fi

# 确保使用 Python 3.11
PYTHON_CMD=$(which python3.11)
if [ -z "$PYTHON_CMD" ]; then
    echo "Error: Python 3.11 not found"
    exit 1
fi

# 显示将要使用的 Python 版本
$PYTHON_CMD --version

# 检查 Python 版本
$PYTHON_CMD -c "import sys; assert sys.version_info.major == 3 and sys.version_info.minor == 11, 'Python 3.11 is required'"

# 删除旧的虚拟环境
rm -rf venv

# 创建新的虚拟环境
$PYTHON_CMD -m venv venv
source venv/bin/activate

# 验证虚拟环境中的 Python 版本
python --version

# 升级基础工具
pip3 install --upgrade pip setuptools wheel build

# 安装 Rust 相关依赖
pip3 install setuptools-rust

# 安装基本依赖
pip3 install -r requirements.txt

# 复制环境变量文件
cp .env venv/.env

# 创建工具目录
mkdir -p utils

# 创建测试视频生成脚本
cat > utils/create_test_video.py << 'EOL'
import subprocess
import os

def create_test_video(output_path: str, duration: int = 5):
    """创建测试视频文件"""
    command = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=blue:s=1280x720:d={duration}',
        '-vf', f'drawtext=text=\'Test Video\':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2',
        '-c:v', 'libx264',
        '-t', str(duration),
        '-y',
        output_path
    ]
    
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"测试视频已创建: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"创建测试视频失败: {e.stderr}")
        raise

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(os.path.dirname(script_dir), "test.mp4")
    create_test_video(output_path)
EOL

# 创建 __init__.py 使其成为包
touch utils/__init__.py

# 安装 FFmpeg (根据操作系统)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    brew install ffmpeg
    # 安装 Rust（如果需要）
    which rustc || curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    sudo apt-get update
    sudo apt-get install -y ffmpeg
    # 安装 Rust（如果需要）
    which rustc || curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
fi

# 确保 Rust 在环境变量中
export PATH="$HOME/.cargo/bin:$PATH"

# 清理之前的安装和构建文件
pip uninstall -y video-processor
rm -rf build dist *.egg-info
rm -rf videoprocessor/*.egg-info

# 安装项目
pip3 install --no-cache-dir -e .

# 验证安装
python -c "from videoprocessor.cli import main; print('CLI tool available')" || echo "CLI import failed"

# 显示最终的 Python 版本和已安装的包
echo "Python version in virtual environment:"
python --version
echo "Installed packages:"
pip list

echo "安装完成！" 

# 创建并设置运行脚本
cat > run.sh << 'EOL'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "${SCRIPT_DIR}/venv/bin/activate"
python -m videoprocessor.cli "$@"
EOL

chmod +x run.sh

# 创建符号链接（可选）
if [[ "$OSTYPE" == "darwin"* ]]; then
    sudo ln -sf "$(pwd)/run.sh" /usr/local/bin/video-processor
fi 