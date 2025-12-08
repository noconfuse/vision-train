#!/usr/bin/env python3
"""
统一日志配置模块
为behavior_annotator和incremental_trainer提供统一的日志配置
"""

import os
import logging
from datetime import datetime
from pathlib import Path

# 全局日志实例
_logger = None

def get_logger():
    """获取统一的日志实例"""
    global _logger
    
    if _logger is None:
        # 创建日志目录
        log_dir = Path(os.path.dirname(__file__)) / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # 日志文件名
        log_file = log_dir / f"behavior_annotator_{datetime.now().strftime('%Y%m%d')}.log"
        
        # 创建logger
        _logger = logging.getLogger('behavior_system')
        _logger.setLevel(logging.INFO)
        
        # 避免重复添加handler
        if not _logger.handlers:
            # 文件handler
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 控制台handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # 格式器
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # 添加handler
            _logger.addHandler(file_handler)
            _logger.addHandler(console_handler)
        
        _logger.info("🎯 统一日志系统启动")
        _logger.info(f"📝 日志文件: {log_file}")
    
    return _logger

# 导出logger实例
logger = get_logger()