import os
import json
from ai_agent import AIAgent

def test_diagnosis():
    agent = AIAgent()
    brand_name = "나이스클랍"
    scores = {"total": 85, "dis": 90, "fresh": 80, "best": 85, "season": 90}
    data_summary = {"item": "jacket", "pct": 45}
    bp_summary = {"item": "jacket", "pct": 50}
    indicator_id = "item"
    
    print(f"Testing AIAgent with model: {agent.MODEL}")
    try:
        result = agent.generate_report(brand_name, scores, data_summary, bp_summary, indicator_id)
        print("Diagnosis Result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if "진단 준비 중" in result.get("core_title", ""):
            print("ERROR: Fallback message returned. API call failed.")
        else:
            print("SUCCESS: AI Report generated successfully.")
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    test_diagnosis()
