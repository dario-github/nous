"""
获取行业分类和市值数据 (用于行业中性化和市值分层)
"""
import tushare as ts
import pandas as pd
from pathlib import Path
import json
import os

def fetch_stock_basic():
    """获取股票基础信息(行业、地区等)"""
    pro = ts.pro_api()
    
    # 获取所有股票基础信息
    df = pro.stock_basic(exchange='', list_status='L', 
                         fields='ts_code,symbol,name,area,industry,list_date')
    return df

def fetch_daily_basic(trade_date: str):
    """获取每日指标(市值、PE等)"""
    pro = ts.pro_api()
    df = pro.daily_basic(trade_date=trade_date, 
                         fields='ts_code,trade_date,close,turnover_rate,volume_ratio,'
                                'pe,pb,ps,dv_ratio,total_share,float_share,'
                                'free_share,total_mv,circ_mv')
    return df

def build_industry_mapping(output_dir: Path):
    """构建行业映射表"""
    print("获取股票基础信息...")
    df = fetch_stock_basic()
    
    # 保存行业映射
    industry_map = dict(zip(df['ts_code'], df['industry']))
    area_map = dict(zip(df['ts_code'], df['area']))
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'industry_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(industry_map, f, ensure_ascii=False, indent=2)
    
    with open(output_dir / 'area_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(area_map, f, ensure_ascii=False, indent=2)
    
    # 保存完整信息
    df.to_csv(output_dir / 'stock_basic.csv', index=False, encoding='utf-8')
    
    print(f"✅ 已保存行业映射: {len(industry_map)} 只股票")
    print(f"行业分布:\n{df['industry'].value_counts().head(10)}")
    
    return df

def build_market_cap_data(output_dir: Path, start_date: str = '20231009', end_date: str = '20260415'):
    """构建市值数据历史"""
    print(f"获取市值数据: {start_date} ~ {end_date}")
    
    # 获取交易日历
    pro = ts.pro_api()
    trade_cal = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date, is_open='1')
    trade_dates = trade_cal['cal_date'].tolist()
    
    all_data = []
    for i, date in enumerate(trade_dates):
        if i % 20 == 0:
            print(f"  处理: {date} ({i+1}/{len(trade_dates)})")
        try:
            df = fetch_daily_basic(date)
            all_data.append(df)
        except Exception as e:
            print(f"  ⚠️ {date} 获取失败: {e}")
    
    # 合并
    result = pd.concat(all_data, ignore_index=True)
    
    # 保存
    result.to_csv(output_dir / 'market_cap_history.csv', index=False, encoding='utf-8')
    
    # 构建透视表
    total_mv_pivot = result.pivot(index='trade_date', columns='ts_code', values='total_mv')
    circ_mv_pivot = result.pivot(index='trade_date', columns='ts_code', values='circ_mv')
    
    total_mv_pivot.to_csv(output_dir / 'total_mv_matrix.csv', encoding='utf-8')
    circ_mv_pivot.to_csv(output_dir / 'circ_mv_matrix.csv', encoding='utf-8')
    
    print(f"✅ 市值数据已保存: {len(result)} 条记录")
    return result

if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import TUSHARE_TOKEN
    
    ts.set_token(TUSHARE_TOKEN)
    
    output_dir = Path(__file__).parent / 'data' / 'auxiliary'
    
    # 获取行业信息
    build_industry_mapping(output_dir)
    
    # 获取市值数据
    build_market_cap_data(output_dir)