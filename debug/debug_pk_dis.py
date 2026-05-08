import pandas as pd
import sys
import os

# 프로젝트 경로 설정
sys.path.append(os.getcwd())

from core.scoring_logic import AssortmentScorer
from database.gsheet_manager import GSheetManager

def debug_pk():
    mgr = GSheetManager()
    df = pd.DataFrame(mgr.spreadsheet.worksheet('Records').get_all_records())
    pk = df[df['brand_name'] == '프로젝트키즈'].copy()
    
    print(f"Total rows for PK: {len(pk)}")
    print(f"Sample discount_rate raw: {pk['discount_rate'].head().tolist()}")
    
    pk['_dis_rate'] = pk['discount_rate'].apply(AssortmentScorer._parse_discount_rate)
    print(f"Sample _dis_rate parsed: {pk['_dis_rate'].head().tolist()}")
    
    # 50~70% 구간 확인
    mask_50_70 = (pk['_dis_rate'] >= 50) & (pk['_dis_rate'] < 70)
    print(f"Rows in 50-70% bucket: {mask_50_70.sum()}")
    
    if mask_50_70.sum() > 0:
        print(f"Sample amt in 50-70%: {pk[mask_50_70]['stock_amt'].head().tolist()}")

if __name__ == "__main__":
    debug_pk()
