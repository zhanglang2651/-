import io
import re

p = r"D:\文旅助手\scripts\manual_poi_queries.py"
src = io.open(p, encoding="utf-8").read()
# 修复被 PowerShell 编码破坏的行：替换掉含乱码的那一条
lines = src.split("\n")
out = []
for ln in lines:
    if "golden beach qingdao" in ln:
        out.append('        "金沙滩": ["golden beach qingdao", "qingdao beach", "china sand beach"],')
    elif " Panshan tianjin" in ln:
        out.append('        "盘山": ["panshan tianjin", "tianjin mountain temple", "china mountain gate"],')
    else:
        out.append(ln)
io.open(p, "w", encoding="utf-8").write("\n".join(out))
print("fixed")
