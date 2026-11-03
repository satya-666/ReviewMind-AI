"""Local sentiment/aspect inference from real saved checkpoints."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.models.inference import ReviewPredictor
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True);p.add_argument('--text',required=True)
    p.add_argument('--category');p.add_argument('--device',default='cpu')
    a=p.parse_args()
    print(json.dumps(ReviewPredictor(a.model,device=a.device).single(a.text,a.category),ensure_ascii=False,indent=2))
