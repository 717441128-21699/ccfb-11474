"""生成样本的命令行入口(兼容 py -I 隔离模式)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_samples import main

if __name__ == "__main__":
    main()
