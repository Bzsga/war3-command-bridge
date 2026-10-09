"""Registered source entry example: emits the author's complete runtime JASS."""
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
Path(a.output).write_bytes((Path(__file__).parent/'source.j').read_bytes())
