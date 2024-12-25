# 智能视频处理系统

## 项目简介
本项目是一个自动化视频处理系统，能够实现视频音频提取、语音识别、字幕生成、多语言翻译、语音合成以及音视频合成等功能。系统采用模块化设计，支持单步或多步处理，方便用户根据需求灵活使用。

## 功能特性

### 1. 音频处理
- 从视频中提取音频
- 支持多种音频格式
- 自动调整采样率和声道
- 音频质量优化

### 2. 字幕生成
- 使用 Whisper 进行语音识别
- 自动生成带时间戳的字幕
- 支持多种语言识别
- 字幕格式标准化

### 3. 翻译功能
- 支持多语言翻译
- 使用 Azure Translator API
- 保持字幕时间轴对齐
- 翻译质量优化

### 4. 语音合成
- 使用 Edge TTS 进行语音合成
- 智能语速调整
- 多语言语音支持
- 自然的语音效果

### 5. 视频合成
- 视频字幕嵌入
- 音视频同步
- 支持多种视频格式
- 视频质量保持

## 安装说明

### 环境要求
- Python 3.8+
- FFmpeg
- Edge TTS
- Azure Translator API 密钥

### 安装步骤
```bash
# 1. 克隆项目
git clone https://github.com/bushkarl/video-processor.git
cd video-processor

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
export AZURE_TRANSLATOR_KEY=your_key_here    # Linux/Mac
set AZURE_TRANSLATOR_KEY=your_key_here       # Windows
```

## 使用方法

### 1. 单步处理

```bash
# 提取音频
./run.sh input.mp4 --steps extract_audio

# 生成字幕
./run.sh input.mp4 --steps generate_srt

# 翻译字幕
./run.sh input.mp4 --steps translate

# 生成配音
./run.sh input.mp4 --steps tts

# 移除原字幕
./run.sh input.mp4 --steps remove_subs

# 合成视频
./run.sh input.mp4 --steps compose
```

### 2. 多步处理

```bash
# 提取音频并生成字幕
./run.sh input.mp4 --steps extract_audio generate_srt

# 翻译并生成配音
./run.sh input.mp4 --steps translate tts

# 完整处理流程
./run.sh input.mp4 --steps all
```

### 3. 输出文件
每个步骤会生成对应的输出文件：
- `*_audio.wav`: 提取的音频文件
- `*_original.srt`: 原始字幕文件
- `*_translated.srt`: 翻译后的字幕文件
- `*_dubbed.wav`: 合成的配音文件
- `*_no_subs.mp4`: 移除字幕后的视频
- `*_final.mp4`: 最终合成的视频

### 4. 可选参数
- `-o, --output`: 指定输出文件路径
- `--remove-subs`: 移除原始字幕
- `--keep-temp`: 保留中间文件

## 注意事项
1. 确保已正确安装 FFmpeg
2. 配置 Azure Translator API 密钥
3. 保持网络连接稳定
4. 建议使用高质量的输入视频
5. 处理大文件时注意磁盘空间

## 常见问题
1. FFmpeg 相关错误
2. 网络连接问题
3. 内存使用问题
4. 临时文件清理
5. 字幕同步问题

## 开发计划
- [ ] 支持更多视频格式
- [ ] 优化语音识别准确度
- [ ] 添加批量处理功能
- [ ] 改进字幕样式定制
- [ ] 提供 Web 界面

## 贡献指南
欢迎提交 Issue 和 Pull Request

## 许可证
MIT License
