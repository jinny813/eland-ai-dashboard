import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
import os
import io
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.data_loader import load_dashboard_data

def evaluate_color(actual_score, target_score):
    """
    점수 달성률을 기반으로 신호등 색상을 반환합니다.
    80% 이상: 초록 (00B050)
    30% 이하: 빨강 (FF0000)
    그 외: 노랑 (FFFF00)
    """
    if target_score <= 0:
        if actual_score > 0: return "00B050"
        return "FFFF00" # 점수가 할당 안 된(평가 제외) 셀은 노란색으로 처리
        
    ratio = (actual_score / target_score)
    if ratio >= 0.8:
        return "00B050"
    elif ratio <= 0.3:
        return "FF0000"
    else:
        return "FFFF00"

def export_to_excel_bytes(data=None, store_filter="전체 지점", cat_filter="전체 카테고리"):
    if not data:
        data = load_dashboard_data()
        if "error" in data:
            return None
    
    brands = data.get("BRANDS", [])
    detail_data = data.get("DETAIL", {})
    
    # 필터링 적용
    filtered_brands = []
    for b in brands:
        if store_filter != "전체 지점" and b.get("store") != store_filter:
            continue
        if cat_filter != "전체 카테고리" and b.get("category") != cat_filter:
            continue
        filtered_brands.append(b)
        
    if not filtered_brands:
        return None
        
    wb = Workbook()
    ws = wb.active
    ws.title = "상품구색 평가"
    
    # ─── 스타일 정의 ───
    font_bold = Font(bold=True)
    font_white_bold = Font(bold=True, color="FFFFFF")
    font_black = Font(color="000000")
    
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    border_thin = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    fill_header_gray = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    
    # 지표별 가중치 (만점)
    weight_map = {
        "dis": 40,
        "best": 20,
        "fresh": 15,
        "season": 15,
        "item": 10
    }
    
    headers_l1 = [
        ("랭크", 1), ("지점", 1), ("브랜드", 1), ("총\n점수\n(100점)", 1), ("총보유\n재고액", 1),
        (f"할인율({weight_map['dis']}점)", 6),
        (f"BEST상품({weight_map['best']}점)", 2),
        (f"신선도({weight_map['fresh']}점)", 3),
        (f"시즌({weight_map['season']}점)", 3),
        (f"아이템({weight_map['item']}점)", 6)
    ]
    
    col_idx = 1
    for title, colspan in headers_l1:
        ws.cell(row=1, column=col_idx, value=title)
        ws.merge_cells(start_row=1, start_column=col_idx, end_row=1, end_column=col_idx + colspan - 1)
        if colspan == 1:
            ws.merge_cells(start_row=1, start_column=col_idx, end_row=2, end_column=col_idx)
        col_idx += colspan
        
    headers_l2 = [
        "랭크", "지점", "브랜드", "총점수", "총재고",
        # 할인율
        "합계", "70%이상", "50~69%", "30~49%", "1~29%", "정상가",
        # BEST
        "합계", "판매\nTOP10",
        # 신선도
        "합계", "신상", "기획",
        # 시즌
        "합계", "봄(SS)", "여름(SS)",
        # 아이템 
        "합계", "아우터", "상의", "하의", "스커트", "원피스"
    ]
    
    for i, title in enumerate(headers_l2):
        cell = ws.cell(row=2, column=i+1)
        if type(cell).__name__ != 'MergedCell':
            cell.value = title
    
    for r in range(1, 3):
        for c in range(1, sum([span for _, span in headers_l1]) + 1):
            cell = ws.cell(row=r, column=c)
            cell.font = font_bold
            cell.alignment = align_center
            cell.border = border_thin
            cell.fill = fill_header_gray
            
    # 각 브랜드별 총점 재계산 (환산 점수의 합)
    for b in filtered_brands:
        tot = 0
        for m_id, m_w in weight_map.items():
            raw_score = b.get(m_id, 0)
            earned = round(raw_score * (m_w / 100.0), 1)
            tot += earned
        b['calculated_total'] = round(tot, 1)
        
    # 총점 내림차순 정렬
    sorted_brands = sorted(filtered_brands, key=lambda x: x.get('calculated_total', 0), reverse=True)
    
    row_idx = 3
    for rank, b in enumerate(sorted_brands, 1):
        store = b.get('store', '')
        b_name = b.get('name', '')
        b_type = b.get('type_label', '')
        
        ws.cell(row=row_idx, column=1, value=rank).alignment = align_center
        ws.cell(row=row_idx, column=2, value=store).alignment = align_center
        ws.cell(row=row_idx, column=3, value=b_name).alignment = align_center
        
        tot_score = b.get('calculated_total', 0)
        tot_amt = b.get('sM', 0)
        
        c_tot = ws.cell(row=row_idx, column=4, value=f"{tot_score}점")
        c_tot.fill = PatternFill(start_color=evaluate_color(tot_score, 100), end_color=evaluate_color(tot_score, 100), fill_type="solid")
        c_tot.font = font_white_bold if evaluate_color(tot_score, 100) != "FFFF00" else font_black
        
        c_amt = ws.cell(row=row_idx, column=5, value=f"{tot_amt}")
        c_amt.fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
        c_amt.font = font_white_bold
        
        b_detail = detail_data.get(store, {}).get(b_name, {}).get(b_type, {})
        col_offset = 6
        
        metrics = [
            ("dis", ["d70", "d50", "d30", "d10", "d0"]),
            ("best", ["best"]),
            ("fresh", ["new", "plan"]),
            ("season", ["spring", "summer"]),
            ("item", ["Outer", "Top", "Bottom", "Skirt", "Dress"])
        ]
        
        for m_id, seg_keys in metrics:
            m_data = b_detail.get(m_id, {})
            m_weight = weight_map.get(m_id, 100)
            
            raw_score = b.get(m_id, 0)
            earned_score = round(raw_score * (m_weight / 100.0), 1)
            
            # 합계 점수 출력
            c_sum = ws.cell(row=row_idx, column=col_offset, value=f"{earned_score}점")
            c_sum.fill = PatternFill(start_color=evaluate_color(earned_score, m_weight), end_color=evaluate_color(earned_score, m_weight), fill_type="solid")
            c_sum.font = font_white_bold if evaluate_color(earned_score, m_weight) != "FFFF00" else font_black
            col_offset += 1
            
            if not m_data or not m_data.get('segs'):
                for _ in range(len(seg_keys)):
                    # 미수집 구간 처리 (점수 미할당으로 간주)
                    c_empty = ws.cell(row=row_idx, column=col_offset, value="-\n(-)")
                    c_empty.fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
                    c_empty.font = font_black
                    col_offset += 1
                continue
                
            segs = m_data.get('segs', [])
            
            for key in seg_keys:
                seg = next((s for s in segs if s['key'] == key), None)
                if seg:
                    valM = seg.get('valM', 0)
                    pct = seg.get('pct', 0)
                    opt_pct = seg.get('opt_pct', 0)
                    
                    # 지표별 만점에 따른 하위 세그먼트 환산 만점
                    seg_max_pt = m_weight * (opt_pct / 100.0)
                    # 실제 획득 점수
                    earned_pt = round(seg_max_pt * (pct / 100.0), 1)
                    
                    if seg_max_pt <= 0:
                        txt = f"{valM}\n(-)"
                    else:
                        txt = f"{valM}\n({earned_pt}점)"
                    
                    c_seg = ws.cell(row=row_idx, column=col_offset, value=txt)
                    c_color = evaluate_color(earned_pt, seg_max_pt)
                    c_seg.fill = PatternFill(start_color=c_color, end_color=c_color, fill_type="solid")
                    c_seg.font = font_white_bold if c_color != "FFFF00" else font_black
                    
                    # 2행(헤더)에 환산 점수 명시 (최초 1회 갱신)
                    if row_idx == 3:
                        lbl = str(ws.cell(row=2, column=col_offset).value).split('\n')[0]
                        if seg_max_pt > 0:
                            ws.cell(row=2, column=col_offset, value=f"{lbl}\n{round(seg_max_pt,1)}점")
                        else:
                            ws.cell(row=2, column=col_offset, value=lbl)
                else:
                    c_empty = ws.cell(row=row_idx, column=col_offset, value="-\n(-)")
                    c_empty.fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
                    c_empty.font = font_black
                col_offset += 1
                
        for c in range(1, col_offset):
            cell = ws.cell(row=row_idx, column=c)
            cell.alignment = align_center
            cell.border = border_thin
            
        row_idx += 1
        
    from openpyxl.utils import get_column_letter
    for col_idx in range(1, ws.max_column + 1):
        max_length = 0
        column = get_column_letter(col_idx)
        for row_idx in range(1, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            try:
                if cell.value:
                    lines = str(cell.value).split('\n')
                    for line in lines:
                        if len(line) > max_length:
                            max_length = len(line)
            except:
                pass
        ws.column_dimensions[column].width = (max_length + 2)
        
    excel_file = io.BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)
    return excel_file.getvalue()
