# engine/__init__.py
import sys
import os
from pathlib import Path

# 确保 ai_core/src 目录在 Python 路径中，以便能够导入 any2table 包
engine_dir = Path(__file__).parent
src_dir = engine_dir.parent / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from .schemas import *
from .engine import (
    handle_module_1_format,
    handle_module_2_extract,
    handle_module_3_fusion
)

__all__ = [
    # Schemas
    'Mod1_FormatInput', 'Mod1_FormatOutput',
    'Mod2_ExtractInput', 'Mod2_ExtractOutput',
    'Mod3_FusionInput', 'Mod3_FusionOutput',
    # Handlers
    'handle_module_1_format',
    'handle_module_2_extract',
    'handle_module_3_fusion'
]
