"""
Nous Invest - 全自动每日 Loop
每日自动：1) 下载数据 2) 运行模型 3) 生成信号 4) 发送通知
"""
import os
import sys
import json
import time
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/daily_loop.log')
    ]
)
logger = logging.getLogger('nous_daily')

# Paths
PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / 'data'
SIGNALS_DIR = PROJECT_DIR / 'signals'
LOGS_DIR = PROJECT_DIR / 'logs'

# Ensure directories exist
for d in [DATA_DIR, SIGNALS_DIR, LOGS_DIR]:
    d.mkdir(exist_ok=True)

# Notification settings (from env or config)
DISCORD_WEBHOOK = os.getenv('NOUS_DISCORD_WEBHOOK', '')
FEISHU_WEBHOOK = os.getenv('NOUS_FEISHU_WEBHOOK', '')


def send_discord_notification(title: str, message: str, fields: list = None):
    """Send notification to Discord via webhook"""
    if not DISCORD_WEBHOOK:
        logger.info("Discord webhook not configured, skipping")
        return
    
    try:
        import requests
        
        embed = {
            "title": title,
            "description": message,
            "color": 0x00ff00 if "✅" in title else 0xff6600,
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "Nous Invest Daily Loop"}
        }
        
        if fields:
            embed["fields"] = [
                {"name": f["name"], "value": f["value"], "inline": f.get("inline", True)}
                for f in fields
            ]
        
        payload = {"embeds": [embed]}
        
        response = requests.post(
            DISCORD_WEBHOOK,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        response.raise_for_status()
        logger.info(f"✅ Discord notification sent")
    except Exception as e:
        logger.error(f"❌ Discord notification failed: {e}")


def send_feishu_notification(title: str, message: str, fields: list = None):
    """Send notification to Feishu via webhook"""
    if not FEISHU_WEBHOOK:
        logger.info("Feishu webhook not configured, skipping")
        return
    
    try:
        import requests
        
        # Build card content
        elements = [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**{title}**\n{message}"}
            }
        ]
        
        if fields:
            field_text = "\n".join([f"**{f['name']}**: {f['value']}" for f in fields])
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": field_text}
            })
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "elements": elements
            }
        }
        
        response = requests.post(
            FEISHU_WEBHOOK,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        response.raise_for_status()
        logger.info(f"✅ Feishu notification sent")
    except Exception as e:
        logger.error(f"❌ Feishu notification failed: {e}")


def send_notification(title: str, message: str, fields: list = None):
    """Send to all configured channels"""
    send_discord_notification(title, message, fields)
    send_feishu_notification(title, message, fields)


def download_latest_data():
    """Download latest Tushare data"""
    logger.info("=" * 60)
    logger.info("📥 STEP 1: Downloading latest Tushare data")
    logger.info("=" * 60)
    
    try:
        # Run update_tushare_daily.py (incremental update)
        result = subprocess.run(
            [sys.executable, 'update_tushare_daily.py'],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=1800  # 30 min timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Data download failed: {result.stderr}")
            return False
        
        logger.info("✅ Data download completed")
        return True
    except subprocess.TimeoutExpired:
        logger.error("❌ Data download timed out (>30 min)")
        return False
    except Exception as e:
        logger.error(f"❌ Data download error: {e}")
        return False


def run_stock_selection_model():
    """Run LightGBM model and generate signals"""
    logger.info("=" * 60)
    logger.info("🧠 STEP 2: Running stock selection model")
    logger.info("=" * 60)
    
    try:
        # Run the model
        result = subprocess.run(
            [sys.executable, 'run_round2_simple.py'],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5 min timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Model failed: {result.stderr}")
            return None
        
        # Parse output to get signal file path
        output = result.stdout
        logger.info("Model output:\n" + output[-2000:] if len(output) > 2000 else output)  # Last 2000 chars
        
        # Find the latest signal file
        signal_files = list(SIGNALS_DIR.glob('signal_*_round2_simple.csv'))
        if not signal_files:
            logger.error("No signal file generated")
            return None
        
        latest_signal = max(signal_files, key=lambda p: p.stat().st_mtime)
        logger.info(f"✅ Signal generated: {latest_signal.name}")
        
        return latest_signal
    except subprocess.TimeoutExpired:
        logger.error("❌ Model timed out (>5 min)")
        return None
    except Exception as e:
        logger.error(f"❌ Model error: {e}")
        return None


def load_metrics():
    """Load latest metrics JSON"""
    metrics_files = list(SIGNALS_DIR.glob('metrics_*_round2_simple.json'))
    if not metrics_files:
        return None
    
    latest_metrics = max(metrics_files, key=lambda p: p.stat().st_mtime)
    
    try:
        with open(latest_metrics) as f:
            return json.load(f)
    except:
        return None


def load_top_signals(signal_file: Path, n: int = 10):
    """Load top N signals from CSV"""
    try:
        df = pd.read_csv(signal_file)
        df = df.sort_values('pred', ascending=False)
        return df.head(n)[['ts_code', 'pred', 'close']].to_dict('records')
    except:
        return []


def run_daily_loop(test_mode: bool = False):
    """Main daily loop"""
    start_time = datetime.now()
    logger.info(f"\n{'='*60}")
    logger.info(f"🚀 Nous Invest Daily Loop Started - {start_time}")
    logger.info(f"{'='*60}\n")
    
    # Send start notification
    send_notification(
        "🚀 Daily Loop Started",
        f"Nous Invest automated pipeline started at {start_time.strftime('%H:%M:%S')}",
        [{"name": "Mode", "value": "Test" if test_mode else "Production", "inline": True}]
    )
    
    success = True
    results = {}
    
    # Step 1: Download data (skip in test mode if data exists)
    if test_mode and (DATA_DIR / 'tushare_csi300_202310_202604.csv').exists():
        logger.info("📦 Test mode: Using existing data")
        results['data_download'] = True
    else:
        results['data_download'] = download_latest_data()
        if not results['data_download']:
            success = False
            send_notification(
                "⚠️ Data Download Failed",
                "Tushare data download failed. Check logs for details."
            )
            # Continue with existing data if available
    
    # Step 2: Run model
    signal_file = run_stock_selection_model()
    results['model_run'] = signal_file is not None
    if not results['model_run']:
        success = False
        send_notification(
            "❌ Model Run Failed",
            "LightGBM model failed to generate signals. Check logs for details."
        )
    
    # Step 3: Load results and send notification
    if results['model_run'] and signal_file:
        metrics = load_metrics()
        top_signals = load_top_signals(signal_file, n=5)
        
        # Build notification fields
        fields = []
        if metrics:
            fields.extend([
                {"name": "📊 IC Mean", "value": f"{metrics.get('ic_mean', 0):.4f}", "inline": True},
                {"name": "📈 ICIR", "value": f"{metrics.get('icir', 0):.4f}", "inline": True},
                {"name": "📅 Signal Date", "value": metrics.get('date', 'N/A'), "inline": True},
            ])
        
        # Add top signals
        if top_signals:
            signal_text = "\n".join([
                f"{i+1}. `{s['ts_code']}` score={s['pred']:+.4f} @ {s['close']:.2f}"
                for i, s in enumerate(top_signals)
            ])
            fields.append({"name": "🎯 Top 5 Signals", "value": signal_text, "inline": False})
        
        send_notification(
            "✅ Daily Loop Complete" if success else "⚠️ Daily Loop Partial Success",
            f"Pipeline completed in {(datetime.now() - start_time).total_seconds()/60:.1f} minutes",
            fields
        )
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🏁 Daily Loop Finished - {end_time}")
    logger.info(f"   Duration: {duration/60:.1f} minutes")
    logger.info(f"   Success: {success}")
    logger.info(f"   Data: {'✅' if results.get('data_download') else '❌'}")
    logger.info(f"   Model: {'✅' if results.get('model_run') else '❌'}")
    logger.info(f"{'='*60}\n")
    
    return 0 if success else 1


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Nous Invest Daily Loop')
    parser.add_argument('--test', action='store_true', help='Test mode (skip data download if exists)')
    parser.add_argument('--notify-only', action='store_true', help='Send test notification only')
    args = parser.parse_args()
    
    if args.notify_only:
        send_notification(
            "🧪 Test Notification",
            "This is a test notification from Nous Invest daily loop.",
            [
                {"name": "Status", "value": "Test Mode", "inline": True},
                {"name": "Time", "value": datetime.now().strftime('%H:%M:%S'), "inline": True}
            ]
        )
        sys.exit(0)
    
    try:
        exit_code = run_daily_loop(test_mode=args.test)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("⚠️ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"💥 Unexpected error: {e}")
        send_notification(
            "💥 Daily Loop Crashed",
            f"Unexpected error: {str(e)[:500]}"
        )
        sys.exit(1)
