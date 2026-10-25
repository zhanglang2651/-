"""把诊断脚本里的中文绝对路径改成相对路径（避免 PowerShell 编码破坏源码）。"""
import io
import re
import sys

p = r"D:\文旅助手\scripts\diag_sse_tool.py"
src = io.open(p, encoding="utf-8").read()
src = re.sub(r'OUT = io\.open\(r?"[^"]*", "w"', 'OUT = io.open("D:/shot_tmp/sse_tool.txt", "w"', src)
io.open(p, "w", encoding="utf-8").write(src)
print("patched")
