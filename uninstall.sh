#!/bin/bash

# 停用虚拟环境（如果已激活）
deactivate 2>/dev/null || true

# 删除虚拟环境
rm -rf venv

# 删除构建文件
rm -rf build dist *.egg-info
rm -rf videoprocessor/*.egg-info

echo "卸载完成！" 