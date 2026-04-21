#!/usr/bin/env python3
"""A股市场环境深度分析 - 2026年4月
分析维度：估值分位数、大小盘风格、行业轮动、波动率与成交量、历史周期对比
"""
import subprocess
import json
import sys
import os
import csv
import io
from collections import defaultdict

SCRIPT_DIR = os.path.expanduser("~/clawd-agents/research/skills/market-data/scripts")
TUSHARE = os.path.join(SCRIPT_DIR, "tushare.sh")

def tushare_index_daily(ts_code, start="20200101", end="20260416"):
    """获取指数日线数据"""
    result = subprocess.run(
        ["bash", TUSHARE, "index_daily", ts_code, start, end],
        capture_output=True, text=True, cwd=SCRIPT_DIR
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    # Tushare output is multi-space separated, normalize per-line
    import re
    lines = result.stdout.strip().split('\n')
    normalized = '\n'.join(re.sub(r'[ \t]+', '\t', line.strip()) for line in lines)
    reader = csv.DictReader(io.StringIO(normalized), delimiter='\t')
    rows = []
    for r in reader:
        rows.append({
            'date': r['trade_date'].strip(),
            'open': float(r['open']),
            'high': float(r['high']),
            'low': float(r['low']),
            'close': float(r['close']),
            'pre_close': float(r['pre_close']),
            'pct_chg': float(r['pct_chg']),
            'vol': float(r['vol']),
            'amount': float(r['amount']),
        })
    rows.sort(key=lambda x: x['date'])
    return rows

def percentile_rank(data, value):
    """计算value在data中的分位数"""
    data = sorted(data)
    n = len(data)
    for i, v in enumerate(data):
        if v >= value:
            return i / n * 100
    return 100.0

def calc_percentile_table(rows, windows=[60, 120, 250, 500, 'all']):
    """计算收盘价的滚动分位数"""
    closes = [r['close'] for r in rows]
    latest = closes[-1]
    result = {}
    for w in windows:
        if w == 'all':
            data = closes
        else:
            data = closes[-w:]
        if len(data) > 10:
            result[str(w)] = round(percentile_rank(data, latest), 1)
    return result

def calc_ma_positions(rows):
    """计算均线位置关系"""
    closes = [r['close'] for r in rows]
    latest = closes[-1]
    mas = {}
    for period in [5, 10, 20, 60, 120, 250]:
        if len(closes) >= period:
            ma = sum(closes[-period:]) / period
            mas[f'MA{period}'] = round(ma, 2)
            mas[f'MA{period}_bias'] = round((latest - ma) / ma * 100, 2)
    return mas

def calc_volatility(rows, windows=[5, 10, 20, 60]):
    """计算波动率"""
    import math
    result = {}
    for w in windows:
        if len(rows) >= w + 1:
            rets = []
            for i in range(-w, 0):
                rets.append(rows[i]['pct_chg'] / 100)
            mean_r = sum(rets) / len(rets)
            var = sum((r - mean_r)**2 for r in rets) / len(rets)
            vol = math.sqrt(var) * math.sqrt(250) * 100  # 年化
            result[f'{w}d_vol'] = round(vol, 2)
    return result

def calc_volume_trend(rows, windows=[5, 10, 20, 60]):
    """成交量趋势"""
    vols = [r['vol'] for r in rows]
    amounts = [r['amount'] for r in rows]
    result = {}
    for w in windows:
        if len(vols) >= w:
            result[f'{w}d_avg_vol'] = round(sum(vols[-w:]) / w / 1e4, 0)  # 万手
            result[f'{w}d_avg_amount'] = round(sum(amounts[-w:]) / w / 1e6, 0)  # 亿元
    return result

def style_ratio_analysis(rows_large, rows_small):
    """大小盘风格分析 - 计算比值趋势"""
    # 对齐日期
    dates_large = {r['date']: r['close'] for r in rows_large}
    dates_small = {r['date']: r['close'] for r in rows_small}
    common_dates = sorted(set(dates_large.keys()) & set(dates_small.keys()))
    
    ratios = []
    for d in common_dates:
        ratio = dates_small[d] / dates_large[d]
        ratios.append({'date': d, 'ratio': ratio})
    
    if not ratios:
        return {}
    
    latest = ratios[-1]['ratio']
    result = {
        'latest_ratio': round(latest, 4),
        'date': ratios[-1]['date'],
    }
    
    for w in [20, 60, 120, 250]:
        if len(ratios) >= w:
            avg = sum(r['ratio'] for r in ratios[-w:]) / w
            result[f'{w}d_avg_ratio'] = round(avg, 4)
            result[f'{w}d_bias%'] = round((latest - avg) / avg * 100, 2)
    
    # 趋势判断
    if len(ratios) >= 60:
        ma20 = sum(r['ratio'] for r in ratios[-20:]) / 20
        ma60 = sum(r['ratio'] for r in ratios[-60:]) / 60
        if ma20 > ma60 * 1.02:
            result['trend'] = '小盘占优'
        elif ma20 < ma60 * 0.98:
            result['trend'] = '大盘占优'
        else:
            result['trend'] = '风格均衡'
    
    return result

def main():
    print("=" * 70)
    print("A股市场环境深度分析 — 2026年4月16日")
    print("=" * 70)
    
    # === 1. 主要指数概况 ===
    print("\n## 一、主要指数最新状态\n")
    
    indices = {
        '000001.SH': '上证指数',
        '000300.SH': '沪深300',
        '000905.SH': '中证500',
        '000852.SH': '中证1000',
    }
    
    all_data = {}
    for code, name in indices.items():
        rows = tushare_index_daily(code)
        all_data[code] = rows
        if rows:
            latest = rows[-1]
            pct_tbl = calc_percentile_table(rows)
            vol_info = calc_volatility(rows)
            ma_info = calc_ma_positions(rows)
            
            print(f"### {name} ({code})")
            print(f"  最新收盘: {latest['close']:.2f} ({latest['date']})")
            print(f"  日涨跌: {latest['pct_chg']:+.2f}%")
            
            # 区间涨跌
            for label, days in [('5日', 5), ('20日', 20), ('60日', 60), ('YTD', None)]:
                if label == 'YTD':
                    # 找到2026年初的数据
                    ytd_rows = [r for r in rows if r['date'] >= '20260101']
                    if len(ytd_rows) > 1:
                        chg = (latest['close'] / ytd_rows[0]['close'] - 1) * 100
                        print(f"  YTD涨跌: {chg:+.2f}%")
                elif len(rows) > days:
                    chg = (latest['close'] / rows[-days]['close'] - 1) * 100
                    print(f"  {label}涨跌: {chg:+.2f}%")
            
            print(f"  估值分位数(收盘价在历史中):")
            for period, pct in pct_tbl.items():
                period_label = {'60': '近60日', '120': '近120日', '250': '近1年', '500': '近2年', 'all': '2020年以来'}
                print(f"    {period_label.get(period, period)}: {pct:.1f}%分位")
            
            print(f"  均线乖离:")
            for k, v in ma_info.items():
                if 'bias' in k:
                    print(f"    {k}: {v:+.2f}%")
            
            print(f"  波动率(年化):")
            for k, v in vol_info.items():
                print(f"    {k}: {v:.2f}%")
            print()
    
    # === 2. 大小盘风格分析 ===
    print("\n## 二、大小盘风格演绎\n")
    
    # 沪深300 vs 中证500 vs 中证1000
    if all_data['000300.SH'] and all_data['000905.SH'] and all_data['000852.SH']:
        style_500_300 = style_ratio_analysis(all_data['000300.SH'], all_data['000905.SH'])
        style_1000_300 = style_ratio_analysis(all_data['000300.SH'], all_data['000852.SH'])
        
        print("### 中证500/沪深300 比值")
        for k, v in style_500_300.items():
            print(f"  {k}: {v}")
        print()
        
        print("### 中证1000/沪深300 比值")
        for k, v in style_1000_300.items():
            print(f"  {k}: {v}")
        print()
        
        # 直接看各指数YTD表现对比
        for code, name in [('000300.SH', '沪深300'), ('000905.SH', '中证500'), ('000852.SH', '中证1000')]:
            rows = all_data[code]
            ytd = [r for r in rows if r['date'] >= '20260101']
            if len(ytd) > 1:
                chg = (rows[-1]['close'] / ytd[0]['close'] - 1) * 100
                print(f"  {name} YTD: {chg:+.2f}%")
    
    # === 3. 成交量趋势 ===
    print("\n## 三、成交量与流动性趋势\n")
    
    for code, name in [('000001.SH', '全市场')]:
        rows = all_data[code]
        vol_info = calc_volume_trend(rows)
        print(f"### {name}")
        for k, v in vol_info.items():
            if 'amount' in k:
                print(f"  {k}: {v:.0f}亿元")
        
        # 量能趋势
        if rows:
            recent_5 = sum(r['amount'] for r in rows[-5:]) / 5
            recent_20 = sum(r['amount'] for r in rows[-20:]) / 20
            recent_60 = sum(r['amount'] for r in rows[-60:]) / 60
            
            print(f"  5日均额: {recent_5/1e6:.0f}亿  20日均额: {recent_20/1e6:.0f}亿  60日均额: {recent_60/1e6:.0f}亿")
            print(f"  5日均额/20日均额: {recent_5/recent_20:.2f}")
            print(f"  20日均额/60日均额: {recent_20/recent_60:.2f}")
            
            # 量价关系
            recent_5_chg = rows[-1]['close'] / rows[-5]['close'] - 1
            if recent_5_chg > 0 and recent_5 > recent_20:
                print(f"  量价状态: 量增价涨 (多头信号)")
            elif recent_5_chg < 0 and recent_5 < recent_20:
                print(f"  量价状态: 缩量下跌 (动能衰减)")
            elif recent_5_chg > 0 and recent_5 < recent_20:
                print(f"  量价状态: 缩量上涨 (上涨动能不足)")
            elif recent_5_chg < 0 and recent_5 > recent_20:
                print(f"  量价状态: 放量下跌 (恐慌/分歧)")
    
    # === 4. 波动率分析 ===
    print("\n## 四、波动率环境\n")
    
    for code, name in indices.items():
        rows = all_data[code]
        if rows:
            vol = calc_volatility(rows)
            pct_tbl = calc_percentile_table(rows)
            
            # 历史20日波动率分位数
            import math
            closes = [r['close'] for r in rows]
            vols_history = []
            for i in range(20, len(closes)):
                rets = [(closes[j] - closes[j-1]) / closes[j-1] for j in range(i-20, i)]
                mean_r = sum(rets) / len(rets)
                var = sum((r - mean_r)**2 for r in rets) / len(rets)
                vol20 = math.sqrt(var) * math.sqrt(250) * 100
                vols_history.append(vol20)
            
            current_vol20 = vol.get('20d_vol', 0)
            vol_pct = percentile_rank(vols_history, current_vol20) if vols_history else 0
            
            print(f"  {name}: 20日波动率={current_vol20:.1f}%, 历史{len(vols_history)}日分位={vol_pct:.0f}%")
    
    # === 5. 历史周期对比 ===
    print("\n## 五、历史周期对比\n")
    
    rows_sh = all_data['000001.SH']
    if rows_sh:
        # 找出历史上与当前位置类似的阶段
        current_close = rows_sh[-1]['close']
        print(f"  上证指数当前: {current_close:.2f}")
        
        # 计算当前250日收益率
        if len(rows_sh) > 250:
            yr_return = (current_close / rows_sh[-250]['close'] - 1) * 100
            print(f"  过去1年涨幅: {yr_return:+.1f}%")
        
        # 历史上相近位置
        similar = []
        for r in rows_sh[:-20]:  # 排除近20日
            if abs(r['close'] / current_close - 1) < 0.03:
                similar.append(r['date'])
        if similar:
            print(f"  历史上相近点位({current_close*0.97:.0f}-{current_close*1.03:.0f})的日期:")
            for d in similar[-5:]:
                print(f"    {d}")
        
        # MACD-like 趋势判断
        if len(rows_sh) > 60:
            ma5 = sum(r['close'] for r in rows_sh[-5:]) / 5
            ma10 = sum(r['close'] for r in rows_sh[-10:]) / 10
            ma20 = sum(r['close'] for r in rows_sh[-20:]) / 20
            ma60 = sum(r['close'] for r in rows_sh[-60:]) / 60
            
            print(f"\n  均线排列:")
            if ma5 > ma10 > ma20 > ma60:
                print(f"    多头排列 (MA5>MA10>MA20>MA60) ★")
            elif ma5 < ma10 < ma20 < ma60:
                print(f"    空头排列 (MA5<MA10<MA20<MA60) ✗")
            else:
                print(f"    交叉排列 (方向不明)")
                if ma5 > ma20:
                    print(f"    短期偏多 (MA5>MA20)")
                else:
                    print(f"    短期偏空 (MA5<MA20)")
            
            # 比较各均线位置
            print(f"    MA5={ma5:.1f} MA10={ma10:.1f} MA20={ma20:.1f} MA60={ma60:.1f}")
    
    # === 6. 行业轮动特征（基于指数成分） ===
    print("\n## 六、近期市场节奏\n")
    
    if rows_sh:
        # 近10日走势
        recent = rows_sh[-10:]
        print("### 近10个交易日走势")
        for r in recent:
            bar = "▲" if r['pct_chg'] > 0 else "▼"
            print(f"  {r['date']} {bar} {r['pct_chg']:+.2f}% 收:{r['close']:.1f} 额:{r['amount']/1e6:.0f}亿")
    
    print("\n" + "=" * 70)
    print("分析完成。数据来源: Tushare Pro，分析区间: 2020-2026.4.16")
    print("=" * 70)

if __name__ == "__main__":
    main()
