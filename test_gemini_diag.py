import os
import sys
import json
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.ai_agent import AIAgent

load_dotenv()

agent = AIAgent()
brand_name = "테스트브랜드"
scores = {"comprehensive": 80}
data_summary = {"test": 123}
bp_summary = {"__past_summary": {}, "__nc_brand_summary": {}, "__nc_category_summary": {}, "__past_yr_summary": {}}

print("Generating report...")
res = agent.generate_report(brand_name, scores, data_summary, bp_summary, "comprehensive")

with open("d:\\AI Assortment Agent\\test_output.json", "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("Done")
