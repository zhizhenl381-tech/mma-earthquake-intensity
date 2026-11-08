"""Run the source checkout without installation."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from mma.cli import main
if __name__=='__main__':main()
