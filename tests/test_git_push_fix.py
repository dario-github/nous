"""验证 git push 不再触发 exec_destructive"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.fact_extractor import _extract_action_type as extract_action_type

# git push 应该不再是 exec_destructive
r1 = extract_action_type({"tool_name": "exec", "params": {"command": "git push origin main"}})
print(f"git push origin main → {r1}")
assert r1 != "exec_destructive", f"FAIL: git push still classified as exec_destructive"

r2 = extract_action_type({"tool_name": "exec", "params": {"command": "git push --force"}})
print(f"git push --force → {r2}")
assert r2 != "exec_destructive", f"FAIL: git push --force still classified as exec_destructive"

# npm publish 应该仍然拦截
r3 = extract_action_type({"tool_name": "exec", "params": {"command": "npm publish"}})
print(f"npm publish → {r3}")
assert r3 == "exec_destructive", f"FAIL: npm publish not classified as exec_destructive"

print("\n✅ All assertions passed — git push fix verified")
