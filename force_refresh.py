import os
import sys
from datetime import datetime, timezone, timedelta
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from main import get_gsheet_manager, cached_load_all_dashboard_data, serialize_dashboard_json, _save_to_pkl, REPORT_VERSION, _PKL_PATH, _cached_get_raw_records

def force_refresh():
    logger.info("Forcing data refresh...")
    check_mgr = get_gsheet_manager()
    if os.path.exists(_PKL_PATH):
        try: os.remove(_PKL_PATH)
        except Exception as e: logger.error(f"Error removing pkl: {e}")
    
    _ref_max = check_mgr._get_max_no() or 1
    
    # getting available months
    months = set()
    raw_recs = _cached_get_raw_records(check_mgr, _ref_max)
    if raw_recs:
        import unicodedata
        for r in raw_recs:
            m = str(r.get('data_month', '')).strip()
            if m:
                m_nfc = unicodedata.normalize('NFC', m)
                months.add(m_nfc)
    
    def _get_m_num(m_str):
        try: return int(str(m_str).replace('월', '').strip())
        except: return 0
    
    _ref_mons = sorted(list(months), key=_get_m_num, reverse=True)
    
    _ref_data = cached_load_all_dashboard_data(check_mgr, _ref_mons)
    if _ref_data and isinstance(_ref_data, dict) and "error" not in _ref_data:
        _ref_am = sorted(_ref_data.keys(), key=_get_m_num, reverse=True)
        for _ref_m, _ref_d in _ref_data.items():
            if isinstance(_ref_d, dict) and "error" not in _ref_d:
                _ref_d["AVAILABLE_MONTHS"] = _ref_am
                _ref_d["SELECTED_MONTH"] = _ref_m
        _ref_json = serialize_dashboard_json(_ref_data)
        _ref_ts = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
        _ref_ok = check_mgr.write_scored_cache(_ref_json, _ref_ts, REPORT_VERSION)
        _save_to_pkl(_ref_ts, _ref_data)
        
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(backup_dir, exist_ok=True)
        with open(os.path.join(backup_dir, "dashboard_backup.json"), "w", encoding="utf-8") as f:
            f.write(_ref_json)
            
        logger.info(f"✅ 갱신 완료! ({_ref_ts}) - GSheet {'Success' if _ref_ok else 'Failed'}")
    else:
        logger.error("Data load failed.")

if __name__ == '__main__':
    force_refresh()
