# Nous Invest - 全自动每日 Loop 安装指南

## 📋 功能概览

全自动每日 Pipeline：
1. ⏰ **定时触发** - 工作日 18:00 自动运行
2. 📥 **数据下载** - 自动获取最新 Tushare 数据
3. 🧠 **模型运行** - LightGBM 选股模型生成信号
4. 💾 **信号保存** - 自动保存到 `signals/` 目录
5. 📱 **通知推送** - Discord/飞书实时推送结果

## 🚀 快速设置

### 1. 安装依赖

```bash
cd /Users/yan/clawd-agents/research/nous-invest
source .venv/bin/activate
pip install requests
```

### 2. 配置通知 Webhook（可选）

#### Discord Webhook
1. 在 Discord 服务器创建 Webhook
2. 复制 Webhook URL
3. 添加到环境变量：
```bash
# ~/.zshrc 或 ~/.bash_profile
export NOUS_DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."
```

#### 飞书 Webhook
1. 在飞书群设置 → 群机器人 → 添加自定义机器人
2. 复制 Webhook URL
3. 添加到环境变量：
```bash
export NOUS_FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/..."
```

### 3. 测试运行

```bash
# 测试通知功能
python daily_loop.py --notify-only

# 测试完整流程（使用现有数据，跳过下载）
python daily_loop.py --test

# 正式运行（完整流程含数据下载）
python daily_loop.py
```

### 4. 设置 Cron 定时任务

编辑 crontab：
```bash
crontab -e
```

添加以下行（工作日 18:00 运行）：
```cron
# Nous Invest - Daily Loop
0 18 * * mon-fri /Users/yan/clawd-agents/research/nous-invest/run_daily.sh >> /Users/yan/clawd-agents/research/nous-invest/logs/cron_master.log 2>&1
```

或手动运行：
```bash
chmod +x run_daily.sh
./run_daily.sh
```

## 📁 生成文件

运行后会生成以下文件：

```
signals/
├── signal_YYYYMMDD_round2_simple.csv   # 每日选股信号
├── metrics_YYYYMMDD_round2_simple.json  # 每日模型指标

logs/
├── daily_loop.log                        # 主日志
├── cron_run_YYYYMMDD_HHMMSS.log          # Cron 运行日志
└── cron_master.log                       # Cron master 日志
```

## 🔧 手动控制

```bash
# 查看今日信号
ls -la signals/signal_$(date +%Y%m%d)*

# 查看最新日志
tail -f logs/daily_loop.log

# 手动运行
cd /Users/yan/clawd-agents/research/nous-invest
source .venv/bin/activate
python daily_loop.py
```

## 📊 信号文件格式

**CSV 格式：**
```csv
ts_code,date,pred,close
000001.SZ,2026-04-08,0.0234,12.50
000002.SZ,2026-04-08,0.0189,15.30
...
```

**JSON 指标格式：**
```json
{
  "date": "2026-04-08",
  "ic_mean": 0.0456,
  "icir": 0.2345,
  "ic_positive_ratio": 0.67,
  ...
}
```

## 🐛 故障排查

| 问题 | 解决方法 |
|------|----------|
| Cron 不运行 | 检查 `run_daily.sh` 是否有执行权限 `chmod +x run_daily.sh` |
| 数据下载失败 | 检查 Tushare token 文件 `~/.config/tushare/token` |
| 模型报错 | 查看 `logs/daily_loop.log` 详细日志 |
| 通知未收到 | 检查 webhook URL 环境变量是否设置正确 |

## 📝 环境变量汇总

```bash
# ~/.zshrc
export NOUS_DISCORD_WEBHOOK="your_discord_webhook_url"
export NOUS_FEISHU_WEBHOOK="your_feishu_webhook_url"
```

## 🎉 完成

设置完成后，系统将在每个工作日 18:00 自动：
1. 下载最新市场数据
2. 运行选股模型
3. 生成 Top 20 信号
4. 推送结果到 Discord/飞书

手动运行：`python daily_loop.py`
