from setuptools import setup, find_packages

setup(
    name="video-processor",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-dotenv",
        "requests",
        "openai-whisper",
        "srt",
        "pyyaml"
    ],
    entry_points={
        "console_scripts": [
            "video-processor=videoprocessor.cli:main",
        ],
    },
    python_requires=">=3.11",
) 