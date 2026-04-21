#!/usr/bin/env python3
"""行业轮动分析 - 申万一级行业近20日/60日/YTD涨跌幅排名"""
import subprocess, csv, io, re, os

SCRIPT_DIR = os.path.expanduser("~/clawd-agents/research/skills/market-data/scripts")
TUSHARE = os.path.join(SCRIPT_DIR, "tushare.sh")

SW_INDUSTRIES = [
    ("801020.SI", "采掘"), ("801030.SI", "化工"), ("801040.SI", "钢铁"),
    ("801050.SI", "有色金属"), ("801710.SI", "建筑材料"), ("801720.SI", "建筑装饰"),
    ("801730.SI", "电气设备"), ("801890.SI", "机械设备"), ("801740.SI", "国防军工"),
    ("801880.SI", "汽车"), ("801110.SI", "家用电器"), ("801130.SI", "纺织服装"),
    ("801140.SI", "轻工制造"), ("801200.SI", "商业贸易"), ("801010.SI", "农林牧渔"),
    ("801120.SI", "食品饮料"), ("801210.SI", "休闲服务"), ("801150.SI", "医药生物"),
    ("801160.SI", "公用事业"), ("801170.SI", "交通运输"), ("801180.SI", "房地产"),
    ("801080.SI", "电子"), ("801750.SI", "计算机"), ("801760.SI", "传媒"),
    ("801770.SI", "通信"), ("801780.SI", "银行"), ("801790.SI", "非银金融"),
    ("801230.SI", "综合"),
]

def get_index_data(ts_code, start="20250901", end="20260416"):
    result = subprocess.run(
        ["bash", TUSHARE, "index_daily", ts_code, start, end],
        capture_output=True, text=True, cwd=SCRIPT_DIR
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    lines = result.stdout.strip().split('\n')
    normalized = '\n'.join(re.sub(r'[ \t]+', '\t', line.strip()) for line in lines)
    reader = csv.DictReader(io.StringIO(normalized), delimiter='\t')
    rows = []
    for r in reader:
        rows.append({'date': r['trade_date'].strip(), 'close': float(r['close'])})
    rows.sort(key=lambda x: x['date'])
    return rows

def main():
    print("### 申万一级行业轮动分析")
    print(f"分析日期: 2026-04-16\n")
    
    results = []
    for code, name in SW_INDUSTRIES:
        rows = get_index_data(code)
        if len(rows) < 60:
            print(f"  {name}({code}): 数据不足({len(rows)}日), 跳过")
            continue
        
        latest = rows[-1]['close']
        
        # 5日涨跌
        chg_5d = (latest / rows[-5]['close'] - 1) * 100 if len(rows) >= 5 else None
        # 20日涨跌
        chg_20d = (latest / rows[-20]['close'] - 1) * 100 if len(rows) >= 20 else None
        # 60日涨跌
        chg_60d = (latest / rows[-60]['close'] - 1) * 100 if len(rows) >= 60 else None
        # YTD
        ytd_rows = [r for r in rows if r['date'] >= '20260101']
        chg_ytd = (latest / ytd_rows[0]['close'] - 1) * 100 if len(ytd_rows) > 1 else None
        
        results.append({
            'name': name, 'code': code,
            'chg_5d': chg_5d, 'chg_20d': chg_20d, 'chg_60d': chg_60d, 'chg_ytd': chg_ytd,
        })
    
    # 按YTD排序
    results.sort(key=lambda x: x.get('chg_ytd') or -999, reverse=True)
    
    # 输出表格
    print(f"{'行业':<8} {'5日%':>7} {'20日%':>8} {'60日%':>8} {'YTD%':>8}")
    print("-" * 42)
    for r in results:
        vals = []
        for k in ['chg_5d', 'chg_20d', 'chg_60d', 'chg_ytd']:
            v = r.get(k)
            vals.append(f"{v:+.1f}" if v is not None else "N/A")
        print(f"{r['name']:<8} {vals[0]:>7} {vals[1]:>8} {vals[2]:>8} {vals[3]:>8}")
    
    # 强势行业
    print(f"\n**YTD强势行业(Top5)**: {', '.join(r['name'] for r in results[:5])}")
    print(f"**YTD弱势行业(Bottom5)**: {', '.join(r['name'] for r in results[-5:])}")
    
    # 近20日动量
    results_20d = sorted(results, key=lambda x: x.get('chg_20d') or -999, reverse=True)
    print(f"\n**近20日动量Top5**: {', '.join(r['name'] for r in results_20d[:5])}")
    print(f"**近20日动量Bottom5**: {', '.join(r['name'] for r in results_20d[-5:])}")

if __name__ == "__main__":
    main()
