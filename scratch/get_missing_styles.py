from core.data_loader import load_dashboard_data
import json

def main():
    d = load_dashboard_data()
    missing_styles = set()
    
    best_items = d.get('BEST_ITEMS', {})
    for store_name, brands in best_items.items():
        for brand_name, types in brands.items():
            for type_label, info in types.items():
                if not isinstance(info, dict) or 'store' not in info:
                    continue
                
                # 상설 매장인 경우만 처리 (type_label에 상설 또는 outlet 포함)
                if '상설' in type_label or 'outlet' in type_label.lower():
                    for item in info['store']:
                        s_code = item.get('style_code')
                        s_name = item.get('style_name')
                        if s_code and (not s_name or s_name in ['—', 'nan', '']):
                            missing_styles.add(s_code)
                            
    print(json.dumps(list(missing_styles)))

if __name__ == "__main__":
    main()
