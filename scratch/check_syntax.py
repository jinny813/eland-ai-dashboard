
import py_compile
try:
    py_compile.compile(r'd:\AI Assortment Agent\core\scoring_logic.py', doraise=True)
    print("Syntax OK")
except py_compile.PyCompileError as e:
    print(f"Syntax Error: {e}")
