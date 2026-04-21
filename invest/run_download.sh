#!/bin/bash
# 下载扩展股票池数据脚本
cd /Users/yan/clawd-agents/research/nous-invest
source .venv/bin/activate
python update_tushare_extended.py 2>&1 | tee logs/download_extended.log
