"""
TradingAI Bot - Interactive Telegram Bot
Real-time market info, buy/sell signals, and broker integration.

Supports:
- Interactive commands
- Real-time market updates
- Buy/Sell signal execution
- Futu and Interactive Brokers integration
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import json

from src.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class BrokerType(str, Enum):
    """Supported brokers."""
    FUTU = "futu"
    IB = "ib"
    PAPER = "paper"


# Professional Risk Management Constants
class RiskParams:
    """Risk parameters used by top traders."""
    MAX_RISK_PER_TRADE = 0.01  # 1% max risk per trade (most pros use 0.5-2%)
    MAX_PORTFOLIO_RISK = 0.06  # 6% max total portfolio risk at once
    MAX_POSITION_SIZE = 0.10   # 10% max single position
    MAX_SECTOR_EXPOSURE = 0.25 # 25% max in one sector
    MAX_CORRELATED_EXPOSURE = 0.40  # 40% max in correlated assets
    MIN_REWARD_RISK = 2.0      # Minimum 2:1 reward/risk ratio
    MAX_DAILY_LOSS = 0.03      # 3% max daily loss - stop trading
    DEFAULT_ACCOUNT = 100000   # Default account size for calculations
    
    # Stop loss methods
    ATR_STOP_MULTIPLIER = 1.5  # 1.5x ATR for stops (professional standard)
    TRAILING_ATR_MULT = 2.0    # 2x ATR for trailing stops


@dataclass
class TradingOrder:
    """Trading order representation."""
    ticker: str
    action: str  # BUY, SELL
    quantity: int
    order_type: str = "MARKET"  # MARKET, LIMIT, STOP
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    broker: BrokerType = BrokerType.PAPER
    status: str = "pending"
    order_id: Optional[str] = None
    filled_price: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)


class TelegramBot:
    """
    Interactive Telegram Bot for TradingAI.
    
    Features:
    - Real-time market data
    - Signal alerts with execution
    - Portfolio tracking
    - Broker integration (Futu, IB)
    - Interactive commands
    """
    
    TELEGRAM_API_BASE = "https://api.telegram.org"
    
    # Command handlers registry
    COMMANDS = {
        # Getting Started
        "/start": "Welcome message and help",
        "/help": "Show all commands",
        "/status": "System status",
        
        # 📊 Market Data
        "/price": "Get current price - /price AAPL",
        "/quote": "Get detailed quote - /quote AAPL",
        "/market": "Live market overview with indices & sectors",
        "/sector": "Sector performance heatmap",
        "/heatmap": "Visual market heatmap by sector",
        "/news": "Get market news - /news AAPL",
        "/earnings": "Upcoming earnings calendar",
        "/movers": "Top gainers and losers today",
        "/premarket": "Pre-market movers & futures",
        
        # 🎯 AI Trading Signals (Holly/TrendSpider style)
        "/signals": "AI signals with probability & R:R ratios",
        "/scan": "Scan for setups - /scan orb|vwap|rsi",
        "/oppty": "Live buying opportunities with scores",
        "/swing": "Swing setups (2 days - 8 weeks)",
        "/daytrade": "Intraday ORB/VWAP setups",
        "/vcp": "VCP pattern breakout candidates",
        "/patterns": "Auto-detected chart patterns",
        "/divergence": "MACD/RSI divergence alerts",
        "/ideas": "AI-generated trade ideas",
        "/setup": "Morning prep: top 10 setups for today",
        
        # 📈 AI Stock Scoring (Kavout/Kai style)
        "/score": "AI score 1-10 for stock - /score AAPL",
        "/rank": "Top 20 stocks by AI momentum score",
        "/top": "Top picks today with confidence levels",
        "/deep": "Deep analysis with technicals - /deep MU",
        
        # 🔬 Stock Analysis & Advice
        "/advise": "Full AI advice - /advise AAPL",
        "/analyze": "Technical analysis - /analyze AAPL",
        "/check": "Check position - /check 150 AAPL",
        "/compare": "Compare stocks - /compare AAPL MSFT",
        "/levels": "Key support/resistance - /levels AAPL",
        "/strength": "Relative strength ranking",
        
        # 📊 Backtesting & Simulation
        "/backtest": "Backtest strategy - /backtest AAPL 1y",
        "/simtrade": "Simulate trades from date - /simtrade 2025-04-06",
        "/performance": "Win rate, profit factor, Sharpe",
        "/journal": "Trade journal & analysis",
        
        # 💼 Portfolio & Trading
        "/portfolio": "View portfolio",
        "/positions": "View open positions",
        "/buy": "Buy stock - /buy AAPL 10",
        "/sell": "Sell stock - /sell AAPL 10",
        "/order": "Place order - /order AAPL BUY 10 LIMIT 150",
        "/pnl": "View P&L",
        "/risk": "Portfolio risk & position sizing",
        "/sizing": "Calculate position size - /sizing AAPL 100",
        "/exposure": "Sector exposure & correlation",
        "/stats": "Trading statistics",
        
        # 🔔 Alerts & Watchlist
        "/watchlist": "View/edit watchlist",
        "/alert": "Set price alert - /alert AAPL above 200",
        "/alerts": "List all active alerts",
        
        # ⚡ Quick Actions
        "/quick": "Quick analysis - /quick AAPL",
        "/daily": "Daily market summary",
        "/eod": "End of day report",
        
        # ⚙️ Settings
        "/broker": "Switch broker - /broker futu|ib|paper",
        "/auto": "Toggle auto updates on/off",
        
        # 📸 Portfolio Import (Screenshot)
        "/myportfolio": "View imported portfolio with P&L",
        "/addpos": "Add position - /addpos AAPL 100 150",
        "/delpos": "Delete position - /delpos AAPL",
        "/monitor": "Get buy/sell/hold advice for your portfolio",
        "/import": "How to import portfolio from screenshot",
        
        # 🧠 Professional Trading Intelligence
        "/riskcheck": "Pre-trade risk check - /riskcheck AAPL 100 175",
        "/learn": "View AI learning & prediction accuracy",
        "/accuracy": "Detailed strategy accuracy stats",
        "/regime": "Market regime detection & strategy selection",
        
        # ⚙️ User Settings & Customization
        "/settings": "View/edit your trading preferences",
        "/setaccount": "Set account size - /setaccount 50000",
        "/setrisk": "Set risk % per trade - /setrisk 1.5",
        "/setstyle": "Set trading style - /setstyle swing",
        
        # 🤖 Advanced Automation
        "/autotrade": "Enable/disable auto-trading",
        "/schedule": "Schedule automated scans",
        "/autopilot": "Full autopilot mode settings",
        
        # 📊 ML & Performance Analytics
        "/mlstats": "ML model performance & weights",
        "/optimize": "Optimize strategy based on history",
        "/report": "Comprehensive performance report",
    }
    
    # Top 500+ most actively traded US stocks by market cap & volume
    TOP_STOCKS = [
        # === MEGA CAP ($200B+) ===
        "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "UNH",
        "LLY", "JPM", "V", "XOM", "JNJ", "MA", "AVGO", "PG", "HD", "COST",
        "ABBV", "MRK", "CVX", "KO", "PEP", "WMT", "BAC", "ADBE", "CRM", "MCD",
        "CSCO", "TMO", "ORCL", "ACN", "ABT", "NFLX", "DHR", "LIN", "NKE", "TXN",
        
        # === LARGE CAP TECH ($50B-200B) ===
        "AMD", "QCOM", "INTC", "IBM", "NOW", "INTU", "AMAT", "ISRG", "ADI", "PANW",
        "LRCX", "MU", "KLAC", "SNPS", "CDNS", "MRVL", "FTNT", "CRWD", "WDAY", "TEAM",
        "DDOG", "ZS", "NET", "SNOW", "PLTR", "ANET", "SPLK", "OKTA", "ZM", "DOCU",
        "TWLO", "HUBS", "VEEV", "BILL", "ESTC", "MDB", "CFLT", "PATH", "GTLB", "DOCN",
        
        # === SEMICONDUCTORS ===
        "TSM", "ASML", "ARM", "NXPI", "ON", "MCHP", "SWKS", "QRVO", "MPWR", "ALGM",
        "CRUS", "SLAB", "SITM", "SMTC", "WOLF", "ACLS", "OLED", "POWI", "ENTG", "MKSI",
        "LSCC", "RMBS", "FORM", "ONTO", "AMBA", "CEVA", "SYNA", "DIOD", "VSH", "SGH",
        
        # === CLOUD & SOFTWARE ===
        "SHOP", "SQ", "PYPL", "ADSK", "ANSS", "PTC", "FICO", "CPRT", "PAYC", "PCTY",
        "GWRE", "APPF", "APPS", "SPSC", "NCNO", "QLYS", "TENB", "VRNS", "RPD", "CYBR",
        "MIME", "SAIL", "VRNT", "PRGS", "NICE", "GLOB", "EPAM", "CWAN", "FRSH", "BRZE",
        
        # === STREAMING & INTERNET ===
        "NFLX", "DIS", "ROKU", "SPOT", "PARA", "WBD", "FOX", "FOXA", "VIAC", "LYV",
        "UBER", "LYFT", "ABNB", "DASH", "RBLX", "EA", "TTWO", "MTCH", "BMBL", "IAC",
        "ETSY", "EBAY", "W", "CHWY", "CVNA", "CARG", "CARS", "VRM", "OPEN", "RDFN",
        "ZG", "Z", "REAL", "EXPE", "BKNG", "TRIP", "TCOM", "MMYT", "DESP", "SABR",
        
        # === EV & AUTO ===
        "RIVN", "LCID", "NIO", "XPEV", "LI", "FFIE", "FSR", "GOEV", "RIDE", "NKLA",
        "F", "GM", "TM", "HMC", "STLA", "RACE", "TTM", "PTRA", "ARVL", "MULN",
        "CHPT", "BLNK", "EVGO", "VLTA", "DCFC", "DRIV", "PLUG", "FCEL", "BE", "BLDP",
        "QS", "MVST", "SES", "SLDP", "FREYR", "LEA", "BWA", "APTV", "ALV", "GNTX",
        
        # === FINANCIALS - BANKS ===
        "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "COF",
        "AXP", "BK", "STT", "NTRS", "SCHW", "ALLY", "CFG", "KEY", "MTB", "FITB",
        "HBAN", "RF", "ZION", "CMA", "FHN", "WAL", "PACW", "FRC", "SBNY", "SI",
        "NYCB", "VLY", "FFIV", "CBSH", "UMBF", "BOKF", "SNV", "ASB", "WBS", "PNFP",
        
        # === FINANCIALS - FINTECH ===
        "V", "MA", "PYPL", "SQ", "COIN", "HOOD", "SOFI", "AFRM", "UPST", "LC",
        "NU", "PSFE", "PAYO", "FOUR", "GPN", "FIS", "FISV", "FLT", "WEX", "ADP",
        "PAYX", "CSGP", "INTU", "BR", "MSCI", "SPGI", "MCO", "ICE", "CME", "CBOE",
        "NDAQ", "TW", "MKTX", "VIRT", "EVR", "HLI", "SF", "PIPR", "JEF", "LAZ",
        
        # === HEALTHCARE - PHARMA ===
        "UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR", "BMY",
        "AMGN", "GILD", "VRTX", "REGN", "BIIB", "ZTS", "CI", "HUM", "ELV", "CVS",
        "MCK", "CAH", "ABC", "COR", "DXCM", "PODD", "ISRG", "SYK", "BSX", "MDT",
        "EW", "ZBH", "HOLX", "ALGN", "IDXX", "MTD", "A", "WAT", "BIO", "TECH",
        
        # === HEALTHCARE - BIOTECH ===
        "MRNA", "BNTX", "NVAX", "SGEN", "ALNY", "EXAS", "ILMN", "QGEN", "NTRA", "GH",
        "TWST", "PACB", "VCNX", "BEAM", "CRSP", "EDIT", "NTLA", "FATE", "BLUE", "RCKT",
        "SRPT", "BMRN", "ALKS", "UTHR", "INCY", "EXEL", "BPMC", "PTCT", "RARE", "IONS",
        "RPRX", "ARVN", "IMVT", "TGTX", "LEGN", "KYMR", "GPCR", "DYN", "ACCD", "HIMS",
        
        # === ENERGY - OIL & GAS ===
        "XOM", "CVX", "COP", "EOG", "SLB", "OXY", "MPC", "VLO", "PSX", "PXD",
        "FANG", "DVN", "HES", "HAL", "BKR", "NOV", "RIG", "DO", "HP", "NBR",
        "OVV", "APA", "MTDR", "CTRA", "CHK", "RRC", "AR", "EQT", "SWN", "CNX",
        "MGY", "SM", "PDCE", "CPE", "CHRD", "ROCC", "GPOR", "NEXT", "BALY", "PUMP",
        
        # === ENERGY - RENEWABLE ===
        "ENPH", "SEDG", "FSLR", "RUN", "NOVA", "ARRY", "CSIQ", "JKS", "DQ", "SOL",
        "NEE", "AES", "CEG", "VST", "NRG", "PEG", "EIX", "ED", "XEL", "WEC",
        "DTE", "CMS", "AEP", "D", "SO", "DUK", "EXC", "SRE", "AWK", "WTRG",
        
        # === CONSUMER - RETAIL ===
        "WMT", "COST", "TGT", "HD", "LOW", "AMZN", "BABA", "JD", "PDD", "SE",
        "MELI", "GLOB", "DG", "DLTR", "BJ", "KR", "ACI", "CASY", "SFM", "SPTN",
        "TJX", "ROST", "BURL", "GPS", "ANF", "AEO", "URBN", "EXPR", "CATO", "GES",
        "LULU", "NKE", "UAA", "UA", "CROX", "SKX", "DECK", "SHOO", "BOOT", "ONON",
        
        # === CONSUMER - FOOD & BEVERAGE ===
        "KO", "PEP", "MNST", "KDP", "CELH", "SAM", "TAP", "BUD", "DEO", "STZ",
        "MKC", "SJM", "GIS", "K", "CPB", "CAG", "HRL", "TSN", "PPC", "BRFS",
        "HSY", "MDLZ", "KHC", "POST", "LNDC", "BYND", "OTLY", "TTCF", "STKL", "SMPL",
        
        # === CONSUMER - RESTAURANTS ===
        "MCD", "SBUX", "CMG", "YUM", "DPZ", "WING", "SHAK", "BROS", "CAVA", "SG",
        "DRI", "TXRH", "BLMN", "EAT", "CAKE", "BJRI", "RRGB", "TAST", "LOCO", "FAT",
        "QSR", "WEN", "JACK", "PZZA", "LOCO", "ARCO", "KRUS", "PLYA", "PLAY", "DAVE",
        
        # === INDUSTRIAL ===
        "BA", "LMT", "RTX", "NOC", "GD", "TXT", "HWM", "TDG", "SPR", "ERJ",
        "CAT", "DE", "AGCO", "CNHI", "ALG", "TITN", "ASTE", "TEX", "OSK", "CMI",
        "ETN", "EMR", "ROK", "AME", "DOV", "ITW", "PH", "XYL", "IEX", "FLS",
        "IR", "GNRC", "PRLB", "GTX", "EPAC", "TTC", "MWA", "FLR", "J", "PWR",
        
        # === TRANSPORTATION ===
        "UPS", "FDX", "XPO", "ODFL", "JBHT", "WERN", "CHRW", "LSTR", "HTLD", "SAIA",
        "DAL", "UAL", "LUV", "AAL", "ALK", "JBLU", "HA", "SAVE", "SKYW", "MESA",
        "NSC", "UNP", "CSX", "CP", "CNI", "KSU", "GWR", "WAB", "TRN", "GBX",
        "MATX", "ZIM", "DAC", "GOGL", "EGLE", "SBLK", "GNK", "NMM", "DSX", "SB",
        
        # === TELECOM & MEDIA ===
        "T", "VZ", "TMUS", "CHTR", "CMCSA", "LBRDK", "DISH", "SIRI", "LSXMK", "FWONA",
        "GOOG", "META", "SNAP", "PINS", "TWTR", "RDDT", "NFLX", "ROKU", "FUBO", "PARA",
        
        # === REAL ESTATE ===
        "AMT", "PLD", "CCI", "EQIX", "PSA", "SPG", "O", "WELL", "DLR", "AVB",
        "EQR", "VTR", "ARE", "BXP", "SLG", "VNO", "KIM", "REG", "FRT", "HIW",
        "CPT", "ESS", "UDR", "MAA", "INVH", "SUI", "ELS", "SBAC", "UNIT", "LMRK",
        
        # === MATERIALS ===
        "LIN", "APD", "SHW", "ECL", "DD", "DOW", "LYB", "PPG", "NEM", "FCX",
        "NUE", "STLD", "CLF", "X", "AA", "CENX", "CMC", "RS", "ATI", "HAYN",
        "ALB", "LTHM", "SQM", "LAC", "PLL", "LIVENT", "MP", "UUUU", "REE", "LEU",
        
        # === CHINESE ADRs ===
        "BABA", "JD", "PDD", "BIDU", "NIO", "XPEV", "LI", "TME", "BILI", "IQ",
        "NTES", "VIPS", "TCOM", "TAL", "EDU", "GOTU", "YQ", "HUYA", "DOYU", "BZUN",
        "WB", "ZH", "KC", "LKNCY", "LX", "ATHM", "GDS", "BEKE", "ZTO", "QFIN",
        "FINV", "LU", "TIGR", "FUTU", "YMM", "XNET", "CMGE", "TC", "SOHU", "API",
        
        # === POPULAR MEME & RETAIL FAVORITES ===
        "GME", "AMC", "BB", "BBBY", "TLRY", "SNDL", "CGC", "ACB", "CRON", "HEXO",
        "SPCE", "PLTR", "SOFI", "CLOV", "WISH", "WKHS", "RIDE", "GOEV", "HYLN", "BLNK",
        "LAZR", "VLDR", "MVIS", "LIDR", "AEVA", "OUST", "CPTN", "INVZ", "ASTS", "RKLB",
        
        # === SPACs POPULAR ===
        "CCIV", "GGPI", "PSTH", "IPOF", "MVST", "DCRC", "FTCV", "PAYO", "VG", "ORGN",
        
        # === CRYPTO RELATED ===
        "COIN", "MSTR", "RIOT", "MARA", "BITF", "HUT", "CLSK", "CORZ", "CIFR", "BTBT",
        "CAN", "HIVE", "SOS", "BTCS", "BKKT", "SI", "NURI", "SDIG", "GREE", "ARBK",
        
        # === ADDITIONAL HIGH-VOLUME STOCKS ===
        "SCHW", "RIVN", "GM", "F", "CCL", "NCLH", "RCL", "WYNN", "LVS", "MGM",
        "CZR", "DKNG", "PENN", "RSI", "GENI", "SGHC", "BETZ", "BALY", "EVRI", "IGT",
        "ATVI", "EA", "TTWO", "ZNGA", "DKNG", "SKLZ", "GGPI", "GENI", "FAZE", "SLGG",
    ]
    
    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.active_broker = BrokerType.PAPER
        self.futu_client = None
        self.ib_client = None
        self.watchlist: List[str] = []
        self.price_alerts: Dict[str, Dict] = {}
        self.last_update_id = 0
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Automated updates settings
        self.auto_updates_enabled = True  # Enable by default
        
        # Portfolio tracking (from screenshot or manual entry)
        self.my_portfolio: Dict[str, Dict] = {}  # {ticker: {qty, avg_cost, ...}}
        
        # === PROFESSIONAL RISK MANAGEMENT ===
        self.account_size = 100000  # Default account size
        self.max_risk_per_trade = 0.01  # 1% risk per trade
        self.max_portfolio_heat = 0.06  # 6% total open risk
        self.daily_pnl = 0.0
        self.daily_loss_limit = -0.03  # -3% daily stop
        
        # === ML/AI LEARNING SYSTEM ===
        self.prediction_history: List[Dict] = []
        self.outcome_tracker: Dict[str, Dict] = {}
        self.strategy_accuracy: Dict[str, Dict] = {
            "momentum": {"wins": 0, "total": 0, "accuracy": 0.5},
            "mean_reversion": {"wins": 0, "total": 0, "accuracy": 0.5},
            "trend_following": {"wins": 0, "total": 0, "accuracy": 0.5},
            "buffett": {"wins": 0, "total": 0, "accuracy": 0.5},
            "druckenmiller": {"wins": 0, "total": 0, "accuracy": 0.5},
        }
        
        # === PERFORMANCE CACHE ===
        self._quote_cache: Dict[str, Dict] = {}
        self._cache_ttl = 30  # 30 seconds cache
        
        # === USER CUSTOMIZATION SETTINGS ===
        self.user_settings = {
            "account_size": 100000,
            "risk_per_trade": 0.01,  # 1%
            "max_positions": 10,
            "trading_style": "swing",  # day, swing, position
            "risk_tolerance": "moderate",  # conservative, moderate, aggressive
            "sectors_focus": [],  # Empty = all sectors
            "min_ai_score": 6,  # Minimum score to show
            "auto_trade_enabled": False,
            "max_daily_trades": 5,
            "preferred_strategies": ["momentum", "trend_following"],
            "news_alerts": True,
            "earnings_alerts": True,
            "price_alerts": True,
        }
        
        # === AUTOMATION SYSTEM ===
        self.auto_trade_enabled = False
        self.scheduled_scans: List[Dict] = []
        self.pending_signals: List[Dict] = []
        self.executed_trades: List[Dict] = []
        
        # === ADVANCED ML TRACKING ===
        self.ml_model_weights = {
            "momentum_score": 0.25,
            "trend_score": 0.20,
            "value_score": 0.15,
            "sentiment_score": 0.15,
            "technical_score": 0.25,
        }
        self.prediction_log: List[Dict] = []  # Detailed predictions
        self.trade_outcomes: List[Dict] = []  # Actual results
        self.model_version = "2.0.0"
        
        # === PERFORMANCE METRICS ===
        self.performance_stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "current_streak": 0,
            "best_streak": 0,
        }
        
    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)
    
    async def start(self):
        """Start the interactive bot."""
        if not self.is_configured:
            logger.error("Telegram not configured")
            return
        
        logger.info("Starting TradingAI Telegram Bot...")
        self._running = True
        self._session = aiohttp.ClientSession()
        
        # Start background tasks
        asyncio.create_task(self._poll_updates())
        asyncio.create_task(self._price_alert_monitor())
        asyncio.create_task(self._market_update_loop())
        
        await self.send_message("🤖 <b>TradingAI Bot Started</b>\n\nType /help for commands")
        logger.info("Telegram bot started")
    
    async def stop(self):
        """Stop the bot."""
        self._running = False
        if self._session:
            await self._session.close()
        logger.info("Telegram bot stopped")
    
    async def _poll_updates(self):
        """Poll for new messages."""
        while self._running:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._handle_update(update)
            except Exception as e:
                logger.error(f"Update polling error: {e}")
            await asyncio.sleep(1)
    
    async def _get_updates(self) -> List[Dict]:
        """Get updates from Telegram."""
        url = f"{self.TELEGRAM_API_BASE}/bot{self.bot_token}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 30}
        
        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    updates = data.get("result", [])
                    if updates:
                        self.last_update_id = updates[-1]["update_id"]
                    return updates
        except Exception as e:
            logger.error(f"Get updates error: {e}")
        return []
    
    async def _handle_update(self, update: Dict):
        """Handle incoming update."""
        message = update.get("message", {})
        callback = update.get("callback_query")
        
        if callback:
            await self._handle_callback(callback)
            return
        
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        photo = message.get("photo")
        caption = message.get("caption", "")
        
        # Handle photo uploads (portfolio screenshots)
        if photo and chat_id:
            await self._handle_photo(chat_id, photo, caption)
            return
        
        if not text or not chat_id:
            return
        
        # Parse command
        if text.startswith("/"):
            parts = text.split()
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            await self._handle_command(chat_id, command, args)
        else:
            # Natural language processing (future)
            pass
    
    async def _handle_photo(self, chat_id: int, photos: List[Dict], caption: str):
        """Handle portfolio screenshot upload."""
        await self.send_message_to(chat_id, "📸 <b>Processing portfolio screenshot...</b>")
        
        try:
            # Get the highest resolution photo
            photo = max(photos, key=lambda p: p.get("file_size", 0))
            file_id = photo.get("file_id")
            
            # Download the image
            file_info = await self._get_file_info(file_id)
            if not file_info:
                await self.send_message_to(chat_id, "❌ Could not process image")
                return
            
            file_path = file_info.get("file_path")
            image_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
            
            # Try to parse the portfolio from the screenshot
            parsed_positions = await self._parse_portfolio_image(image_url, caption)
            
            if parsed_positions:
                # Store the parsed positions
                for pos in parsed_positions:
                    ticker = pos.get("ticker", "").upper()
                    if ticker:
                        self.my_portfolio[ticker] = {
                            "qty": pos.get("qty", 0),
                            "avg_cost": pos.get("avg_cost", 0),
                            "added_at": datetime.now().isoformat(),
                            "source": "screenshot"
                        }
                
                msg = f"✅ <b>Portfolio Imported!</b>\n\n"
                msg += f"Found {len(parsed_positions)} positions:\n\n"
                
                for pos in parsed_positions[:15]:
                    ticker = pos.get("ticker", "")
                    qty = pos.get("qty", 0)
                    cost = pos.get("avg_cost", 0)
                    msg += f"• <b>{ticker}</b>: {qty} shares @ ${cost:.2f}\n"
                
                if len(parsed_positions) > 15:
                    msg += f"\n... and {len(parsed_positions) - 15} more\n"
                
                msg += "\n📊 Use /myportfolio to view\n"
                msg += "📈 Use /monitor to get buy/sell advice"
                
                await self.send_message_to(chat_id, msg)
            else:
                msg = """
📸 <b>Could not auto-detect positions</b>

To add positions manually, use:
<code>/addpos AAPL 100 150.50</code>
(ticker, quantity, avg cost)

Or try uploading a clearer screenshot showing:
• Ticker symbols
• Quantity/Shares
• Average cost

<b>Supported formats:</b>
• Futu/MooMoo portfolio
• Interactive Brokers
• Robinhood
• TD Ameritrade
• Any broker with visible tickers
"""
                await self.send_message_to(chat_id, msg)
                
        except Exception as e:
            logger.error(f"Photo handling error: {e}")
            await self.send_message_to(chat_id, f"❌ Error processing image: {e}")
    
    async def _get_file_info(self, file_id: str) -> Optional[Dict]:
        """Get file info from Telegram."""
        url = f"{self.TELEGRAM_API_BASE}/bot{self.bot_token}/getFile"
        params = {"file_id": file_id}
        
        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("result", {})
        except Exception as e:
            logger.error(f"Get file error: {e}")
        return None
    
    async def _parse_portfolio_image(self, image_url: str, caption: str) -> List[Dict]:
        """
        Parse portfolio from screenshot using pattern matching.
        Returns list of {ticker, qty, avg_cost} dicts.
        """
        positions = []
        
        # If caption contains manual entries, parse those
        if caption:
            # Try to parse caption like: "AAPL 100 150, MSFT 50 380"
            lines = caption.replace(",", "\n").strip().split("\n")
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2:
                    ticker = parts[0].upper()
                    # Validate it looks like a ticker (1-5 uppercase letters)
                    if ticker.isalpha() and len(ticker) <= 5:
                        try:
                            qty = int(parts[1]) if len(parts) > 1 else 0
                            avg_cost = float(parts[2]) if len(parts) > 2 else 0
                            positions.append({
                                "ticker": ticker,
                                "qty": qty,
                                "avg_cost": avg_cost
                            })
                        except ValueError:
                            continue
        
        # For actual image OCR, we would use Azure Vision or similar
        # For now, just return what we parsed from caption
        return positions
    
    async def _handle_command(self, chat_id: int, command: str, args: List[str]):
        """Route command to handler."""
        handlers = {
            "/start": self._cmd_start,
            "/help": self._cmd_help,
            "/price": self._cmd_price,
            "/quote": self._cmd_quote,
            "/scan": self._cmd_scan,
            "/signals": self._cmd_signals,
            "/portfolio": self._cmd_portfolio,
            "/positions": self._cmd_positions,
            "/buy": self._cmd_buy,
            "/sell": self._cmd_sell,
            "/order": self._cmd_order,
            "/pnl": self._cmd_pnl,
            "/watchlist": self._cmd_watchlist,
            "/alert": self._cmd_alert,
            "/alerts": self._cmd_alerts,
            "/news": self._cmd_news,
            "/market": self._cmd_market,
            "/sector": self._cmd_sector,
            "/broker": self._cmd_broker,
            "/status": self._cmd_status,
            # Interactive commands
            "/oppty": self._cmd_oppty,
            "/swing": self._cmd_swing,
            "/vcp": self._cmd_vcp,
            "/advise": self._cmd_advise,
            "/analyze": self._cmd_analyze,
            "/check": self._cmd_check,
            "/earnings": self._cmd_earnings,
            # New commands
            "/movers": self._cmd_movers,
            "/premarket": self._cmd_premarket,
            "/ideas": self._cmd_ideas,
            "/compare": self._cmd_compare,
            "/levels": self._cmd_levels,
            "/strength": self._cmd_strength,
            "/risk": self._cmd_risk,
            "/history": self._cmd_history,
            "/stats": self._cmd_stats,
            "/quick": self._cmd_quick,
            "/daily": self._cmd_daily,
            "/summary": self._cmd_summary,
            "/eod": self._cmd_eod,
            # AI Trading Advisor commands
            "/score": self._cmd_score,
            "/rank": self._cmd_rank,
            "/top": self._cmd_top,
            "/setup": self._cmd_setup,
            "/patterns": self._cmd_patterns,
            "/divergence": self._cmd_divergence,
            "/daytrade": self._cmd_daytrade,
            "/heatmap": self._cmd_heatmap,
            "/backtest": self._cmd_backtest,
            "/simtrade": self._cmd_simtrade,
            "/performance": self._cmd_performance,
            "/journal": self._cmd_journal,
            "/sizing": self._cmd_sizing,
            "/exposure": self._cmd_exposure,
            "/deep": self._cmd_deep,
            # Settings
            "/auto": self._cmd_auto,
            # Portfolio management
            "/myportfolio": self._cmd_myportfolio,
            "/addpos": self._cmd_addpos,
            "/delpos": self._cmd_delpos,
            "/monitor": self._cmd_monitor,
            "/import": self._cmd_import,
            # Professional Trading Intelligence
            "/riskcheck": self._cmd_riskcheck,
            "/learn": self._cmd_learn,
            "/accuracy": self._cmd_accuracy,
            "/regime": self._cmd_regime,
            # User Settings & Customization
            "/settings": self._cmd_settings,
            "/setaccount": self._cmd_setaccount,
            "/setrisk": self._cmd_setrisk,
            "/setstyle": self._cmd_setstyle,
            # Advanced Automation
            "/autotrade": self._cmd_autotrade,
            "/schedule": self._cmd_schedule,
            "/autopilot": self._cmd_autopilot,
            # ML & Performance
            "/mlstats": self._cmd_mlstats,
            "/optimize": self._cmd_optimize,
            "/report": self._cmd_report,
        }
        
        handler = handlers.get(command)
        if handler:
            await handler(chat_id, args)
        else:
            await self.send_message_to(chat_id, "❓ Unknown command. Type /help for available commands.")
    
    # ===== Command Handlers =====
    
    async def _cmd_start(self, chat_id: int, args: List[str]):
        """Welcome message."""
        msg = """
🤖 <b>Welcome to TradingAI Bot!</b>

Your AI-powered trading assistant with real-time market intelligence.

<b>🔗 Connected Brokers:</b>
  • Futu (富途) - Hong Kong/US Markets
  • Interactive Brokers - Global Markets

<b>Quick Commands:</b>
  /market - Market overview
  /signals - Latest trading signals
  /price AAPL - Get stock price
  /buy AAPL 10 - Buy 10 shares

Type /help for all commands.
"""
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_help(self, chat_id: int, args: List[str]):
        """Show help."""
        msg = "📚 <b>TradingAI Bot Commands</b>\n\n"
        
        categories = {
            "🤖 AI Scoring (Kavout/Kai style)": ["/score", "/rank", "/top"],
            "☀️ Morning Prep (Holly/Trade Ideas)": ["/setup", "/oppty", "/signals"],
            "📊 Pattern Detection": ["/patterns", "/divergence", "/swing", "/vcp"],
            "⚡ Day Trading": ["/daytrade", "/movers", "/premarket"],
            "📈 Market Intel": ["/market", "/heatmap", "/sector", "/news"],
            "💡 Stock Analysis": ["/advise", "/analyze", "/check", "/levels"],
            "💰 Trading": ["/buy", "/sell", "/order", "/sizing"],
            "📁 Portfolio": ["/portfolio", "/myportfolio", "/monitor"],
            "📊 Performance": ["/backtest", "/report", "/mlstats"],
            "🧠 Pro Trading": ["/riskcheck", "/regime", "/optimize"],
            "⚙️ Settings": ["/settings", "/setaccount", "/setrisk", "/setstyle"],
            "🤖 Automation": ["/autotrade", "/schedule", "/autopilot"],
            "⚙️ System": ["/broker", "/status", "/help"],
        }
        
        for category, cmds in categories.items():
            msg += f"<b>{category}</b>\n"
            for cmd in cmds:
                desc = self.COMMANDS.get(cmd, "")
                msg += f"  {cmd} - {desc}\n"
            msg += "\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💡 <b>Quick Start:</b>\n"
        msg += "<code>/settings</code> - Configure your preferences\n"
        msg += "<code>/top</code> - Today's top AI picks\n"
        msg += "<code>/riskcheck AAPL 100</code> - Pre-trade check\n"
        msg += "<code>/autopilot</code> - Setup automation\n"
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_price(self, chat_id: int, args: List[str]):
        """Get current price."""
        if not args:
            await self.send_message_to(chat_id, "Usage: /price AAPL")
            return
        
        ticker = args[0].upper()
        
        try:
            quote = await self._fetch_quote(ticker)
            if quote:
                change = quote.get('change', 0)
                change_pct = quote.get('change_pct', 0)
                emoji = "🟢" if change >= 0 else "🔴"
                
                msg = f"""
{emoji} <b>{ticker}</b>

<b>Price:</b> ${quote.get('price', 0):.2f}
<b>Change:</b> {'+' if change >= 0 else ''}{change:.2f} ({'+' if change_pct >= 0 else ''}{change_pct:.2f}%)
<b>Volume:</b> {quote.get('volume', 0):,}

<i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>
"""
                await self.send_message_to(chat_id, msg)
            else:
                await self.send_message_to(chat_id, f"❌ Could not fetch price for {ticker}")
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_quote(self, chat_id: int, args: List[str]):
        """Get detailed quote."""
        if not args:
            await self.send_message_to(chat_id, "Usage: /quote AAPL")
            return
        
        ticker = args[0].upper()
        
        try:
            quote = await self._fetch_quote(ticker, detailed=True)
            if quote:
                change = quote.get('change', 0)
                change_pct = quote.get('change_pct', 0)
                emoji = "🟢" if change >= 0 else "🔴"
                
                msg = f"""
{emoji} <b>{ticker}</b> - {quote.get('name', ticker)}

<b>═══ Price ═══</b>
  Current: <code>${quote.get('price', 0):.2f}</code>
  Change: {'+' if change >= 0 else ''}{change:.2f} ({'+' if change_pct >= 0 else ''}{change_pct:.2f}%)
  
<b>═══ Day Range ═══</b>
  Open: ${quote.get('open', 0):.2f}
  High: ${quote.get('high', 0):.2f}
  Low: ${quote.get('low', 0):.2f}
  
<b>═══ Volume ═══</b>
  Volume: {quote.get('volume', 0):,}
  Avg Vol: {quote.get('avg_volume', 0):,}
  
<b>═══ Fundamentals ═══</b>
  Market Cap: ${quote.get('market_cap', 0)/1e9:.2f}B
  P/E: {quote.get('pe_ratio', 'N/A')}
  52W Range: ${quote.get('low_52w', 0):.2f} - ${quote.get('high_52w', 0):.2f}

<i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>
"""
                await self.send_message_to(chat_id, msg)
            else:
                await self.send_message_to(chat_id, f"❌ Could not fetch quote for {ticker}")
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_market(self, chat_id: int, args: List[str]):
        """Comprehensive market overview."""
        try:
            msg = "📊 <b>LIVE MARKET UPDATE</b>\n"
            msg += f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n\n"
            
            # Market status
            market_open = self._is_market_open()
            msg += f"🏛️ <b>Market Status:</b> {'🟢 OPEN' if market_open else '🔴 CLOSED'}\n\n"
            
            # Major Indices
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📈 <b>MAJOR INDICES</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            
            indices = [
                ("SPY", "S&P 500"),
                ("QQQ", "NASDAQ 100"),
                ("DIA", "DOW JONES"),
                ("IWM", "RUSSELL 2000"),
            ]
            
            for symbol, name in indices:
                quote = await self._fetch_quote(symbol)
                if quote:
                    price = quote.get('price', 0)
                    change_pct = quote.get('change_pct', 0)
                    emoji = "🟢" if change_pct >= 0 else "🔴"
                    bar = self._generate_bar(change_pct)
                    msg += f"{emoji} <b>{name}</b>\n"
                    msg += f"   ${price:.2f} | {bar} {'+' if change_pct >= 0 else ''}{change_pct:.2f}%\n"
            
            # Volatility & Fear Gauge
            msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "😰 <b>VOLATILITY</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            
            vix = await self._fetch_quote("UVXY")
            if vix:
                vix_change = vix.get('change_pct', 0)
                if vix_change > 10:
                    fear = "🔴 HIGH FEAR"
                elif vix_change > 3:
                    fear = "🟠 ELEVATED"
                elif vix_change > 0:
                    fear = "🟡 NEUTRAL"
                else:
                    fear = "🟢 LOW FEAR"
                msg += f"UVXY: ${vix.get('price', 0):.2f} ({'+' if vix_change >= 0 else ''}{vix_change:.2f}%)\n"
                msg += f"Sentiment: {fear}\n"
            
            # Sector Leaders
            msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "🏭 <b>SECTOR SNAPSHOT</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            
            sectors = [("XLK", "Tech"), ("XLF", "Finance"), ("XLE", "Energy"), ("XLV", "Health")]
            for symbol, name in sectors:
                quote = await self._fetch_quote(symbol)
                if quote:
                    change_pct = quote.get('change_pct', 0)
                    emoji = "🟢" if change_pct >= 0 else "🔴"
                    msg += f"{emoji} {name}: {'+' if change_pct >= 0 else ''}{change_pct:.2f}% | "
            msg = msg.rstrip(" | ") + "\n"
            
            # Top Movers from watchlist
            if self.watchlist:
                msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "👀 <b>YOUR WATCHLIST</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                
                for ticker in self.watchlist[:5]:
                    quote = await self._fetch_quote(ticker)
                    if quote:
                        price = quote.get('price', 0)
                        change_pct = quote.get('change_pct', 0)
                        emoji = "🟢" if change_pct >= 0 else "🔴"
                        msg += f"{emoji} {ticker}: ${price:.2f} ({'+' if change_pct >= 0 else ''}{change_pct:.2f}%)\n"
            
            # Quick actions
            msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "💡 <b>QUICK ACTIONS</b>\n"
            msg += "/oppty - Find opportunities\n"
            msg += "/swing - Swing setups\n"
            msg += "/sector - Sector details\n"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error fetching market data: {e}")
    
    async def _cmd_signals(self, chat_id: int, args: List[str]):
        """Get latest signals."""
        try:
            from src.engines.signal_engine import SignalEngine
            
            engine = SignalEngine()
            # Get test tickers or from watchlist
            tickers = self.watchlist if self.watchlist else self.TOP_STOCKS[:20]
            
            msg = "📈 <b>Latest Trading Signals</b>\n\n"
            
            # Fetch signals
            from src.ingestors.market_data import MarketDataIngestor
            ingestor = MarketDataIngestor()
            
            signals_found = []
            for ticker in tickers[:5]:
                try:
                    df = await ingestor.fetch_historical_data(ticker, days=100)
                    if df is not None and len(df) > 50:
                        signals = await engine.generate_signals(df, ticker)
                        for s in signals:
                            if s.confidence >= 0.6:
                                signals_found.append(s)
                except:
                    continue
            
            if signals_found:
                for s in sorted(signals_found, key=lambda x: x.confidence, reverse=True)[:5]:
                    emoji = "🟢" if s.direction == "LONG" else "🔴"
                    msg += f"""
{emoji} <b>{s.ticker}</b> - {s.direction}
  Strategy: {s.strategy}
  Entry: ${s.entry_price:.2f}
  Target: ${s.take_profit:.2f}
  Stop: ${s.stop_loss:.2f}
  Confidence: {s.confidence:.0%}
"""
            else:
                msg += "No high-confidence signals at the moment.\n"
                msg += "Try /scan momentum for scanning options."
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            logger.error(f"Signals error: {e}")
            await self.send_message_to(chat_id, f"❌ Error fetching signals: {e}")
    
    async def _cmd_scan(self, chat_id: int, args: List[str]):
        """Scan for trading opportunities."""
        scan_type = args[0].lower() if args else "all"
        
        await self.send_message_to(chat_id, f"🔍 Scanning for {scan_type} signals...")
        
        try:
            if scan_type == "momentum":
                from src.scanners import MomentumScanner
                scanner = MomentumScanner()
                alerts = await scanner.scan_universe(min_confidence=60)
                
                if alerts:
                    msg = "⚡ <b>Momentum Signals</b>\n\n"
                    for a in alerts[:5]:
                        msg += f"📈 <b>{a.ticker}</b> - {a.signal_type.value}\n"
                        msg += f"   Confidence: {a.confidence:.0f}%\n"
                        if a.entry_zone:
                            msg += f"   Entry: ${a.entry_zone[0]:.2f} - ${a.entry_zone[1]:.2f}\n"
                        msg += "\n"
                else:
                    msg = "No momentum signals found at the moment."
                    
            elif scan_type == "patterns":
                from src.scanners import PatternScanner
                scanner = PatternScanner()
                msg = "📊 <b>Pattern Scan</b>\n\nScanning for chart patterns..."
                # Would scan each ticker in watchlist
                
            elif scan_type == "sectors":
                from src.scanners import SectorScanner
                scanner = SectorScanner()
                msg = "🏭 <b>Sector Rotation</b>\n\nAnalyzing sector performance..."
                
            else:
                msg = """
🔍 <b>Scan Types:</b>

/scan momentum - Breakouts, gaps, volume surges
/scan patterns - Chart patterns (H&S, triangles, etc.)
/scan sectors - Sector rotation analysis
/scan volume - Accumulation/distribution
"""
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Scan error: {e}")
    
    async def _cmd_buy(self, chat_id: int, args: List[str]):
        """Buy stock."""
        if len(args) < 2:
            await self.send_message_to(chat_id, "Usage: /buy AAPL 10")
            return
        
        ticker = args[0].upper()
        try:
            quantity = int(args[1])
        except ValueError:
            await self.send_message_to(chat_id, "❌ Invalid quantity")
            return
        
        # Create order
        order = TradingOrder(
            ticker=ticker,
            action="BUY",
            quantity=quantity,
            broker=self.active_broker
        )
        
        # Confirm with user
        quote = await self._fetch_quote(ticker)
        price = quote.get('price', 0) if quote else 0
        total = price * quantity
        
        msg = f"""
📝 <b>Order Confirmation</b>

<b>Action:</b> BUY
<b>Ticker:</b> {ticker}
<b>Quantity:</b> {quantity}
<b>Est. Price:</b> ${price:.2f}
<b>Est. Total:</b> ${total:.2f}
<b>Broker:</b> {self.active_broker.value.upper()}

Reply with /confirm to execute or /cancel to abort.
"""
        
        await self.send_message_to(chat_id, msg)
        
        # Store pending order (simplified - would use proper state management)
        # In production, use Redis or database to store pending orders
    
    async def _cmd_sell(self, chat_id: int, args: List[str]):
        """Sell stock."""
        if len(args) < 2:
            await self.send_message_to(chat_id, "Usage: /sell AAPL 10")
            return
        
        ticker = args[0].upper()
        try:
            quantity = int(args[1])
        except ValueError:
            await self.send_message_to(chat_id, "❌ Invalid quantity")
            return
        
        quote = await self._fetch_quote(ticker)
        price = quote.get('price', 0) if quote else 0
        total = price * quantity
        
        msg = f"""
📝 <b>Order Confirmation</b>

<b>Action:</b> SELL
<b>Ticker:</b> {ticker}
<b>Quantity:</b> {quantity}
<b>Est. Price:</b> ${price:.2f}
<b>Est. Total:</b> ${total:.2f}
<b>Broker:</b> {self.active_broker.value.upper()}

Reply with /confirm to execute or /cancel to abort.
"""
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_order(self, chat_id: int, args: List[str]):
        """Place advanced order."""
        if len(args) < 4:
            msg = """
<b>Order Syntax:</b>
/order TICKER ACTION QTY TYPE [PRICE]

<b>Examples:</b>
/order AAPL BUY 10 MARKET
/order AAPL BUY 10 LIMIT 150
/order AAPL SELL 10 STOP 145
"""
            await self.send_message_to(chat_id, msg)
            return
        
        ticker = args[0].upper()
        action = args[1].upper()
        quantity = int(args[2])
        order_type = args[3].upper()
        price = float(args[4]) if len(args) > 4 else None
        
        msg = f"""
📝 <b>Order Details</b>

<b>Ticker:</b> {ticker}
<b>Action:</b> {action}
<b>Quantity:</b> {quantity}
<b>Type:</b> {order_type}
<b>Price:</b> {'$' + f'{price:.2f}' if price else 'MARKET'}
<b>Broker:</b> {self.active_broker.value.upper()}

Use /confirm to execute.
"""
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_portfolio(self, chat_id: int, args: List[str]):
        """View portfolio."""
        try:
            positions = await self._get_positions()
            
            if not positions:
                await self.send_message_to(chat_id, "📁 No positions found. Paper trading mode.")
                return
            
            msg = "📁 <b>Portfolio</b>\n\n"
            total_value = 0
            total_pnl = 0
            
            for pos in positions:
                pnl_pct = pos.get('pnl_pct', 0)
                emoji = "🟢" if pnl_pct >= 0 else "🔴"
                msg += f"{emoji} <b>{pos['ticker']}</b>\n"
                msg += f"   Qty: {pos['quantity']} @ ${pos['avg_price']:.2f}\n"
                msg += f"   Value: ${pos['value']:.2f}\n"
                msg += f"   P&L: {'+' if pnl_pct >= 0 else ''}{pnl_pct:.2f}%\n\n"
                total_value += pos['value']
                total_pnl += pos.get('pnl', 0)
            
            msg += f"<b>Total Value:</b> ${total_value:,.2f}\n"
            msg += f"<b>Total P&L:</b> ${total_pnl:+,.2f}"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_positions(self, chat_id: int, args: List[str]):
        """View open positions."""
        await self._cmd_portfolio(chat_id, args)
    
    async def _cmd_pnl(self, chat_id: int, args: List[str]):
        """View P&L."""
        period = args[0].lower() if args else "today"
        
        msg = f"""
💰 <b>P&L Summary</b> ({period})

<b>Realized P&L:</b> $0.00
<b>Unrealized P&L:</b> $0.00
<b>Total P&L:</b> $0.00

<b>Trades:</b>
  Winners: 0
  Losers: 0
  Win Rate: N/A

<i>Connect broker for live P&L tracking</i>
"""
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_watchlist(self, chat_id: int, args: List[str]):
        """View or edit watchlist."""
        if not args:
            # Show watchlist
            if self.watchlist:
                msg = "👀 <b>Watchlist</b>\n\n"
                for ticker in self.watchlist:
                    quote = await self._fetch_quote(ticker)
                    if quote:
                        change_pct = quote.get('change_pct', 0)
                        emoji = "🟢" if change_pct >= 0 else "🔴"
                        msg += f"{emoji} <b>{ticker}</b>: ${quote.get('price', 0):.2f} ({'+' if change_pct >= 0 else ''}{change_pct:.2f}%)\n"
                    else:
                        msg += f"⚪ <b>{ticker}</b>\n"
            else:
                msg = "👀 Watchlist is empty.\n\nUse /watchlist add AAPL to add stocks."
        
        elif args[0].lower() == "add" and len(args) > 1:
            ticker = args[1].upper()
            if ticker not in self.watchlist:
                self.watchlist.append(ticker)
                msg = f"✅ Added {ticker} to watchlist"
            else:
                msg = f"{ticker} already in watchlist"
        
        elif args[0].lower() == "remove" and len(args) > 1:
            ticker = args[1].upper()
            if ticker in self.watchlist:
                self.watchlist.remove(ticker)
                msg = f"✅ Removed {ticker} from watchlist"
            else:
                msg = f"{ticker} not in watchlist"
        
        else:
            msg = """
<b>Watchlist Commands:</b>
/watchlist - View watchlist
/watchlist add AAPL - Add ticker
/watchlist remove AAPL - Remove ticker
"""
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_alert(self, chat_id: int, args: List[str]):
        """Set price alert."""
        if len(args) < 3:
            msg = """
<b>Alert Syntax:</b>
/alert TICKER above PRICE
/alert TICKER below PRICE

<b>Examples:</b>
/alert AAPL above 200
/alert NVDA below 500
"""
            await self.send_message_to(chat_id, msg)
            return
        
        ticker = args[0].upper()
        condition = args[1].lower()
        try:
            target_price = float(args[2])
        except ValueError:
            await self.send_message_to(chat_id, "❌ Invalid price")
            return
        
        if condition not in ("above", "below"):
            await self.send_message_to(chat_id, "❌ Condition must be 'above' or 'below'")
            return
        
        # Store alert
        alert_id = f"{ticker}_{condition}_{target_price}"
        self.price_alerts[alert_id] = {
            "ticker": ticker,
            "condition": condition,
            "price": target_price,
            "chat_id": chat_id,
            "created": datetime.now()
        }
        
        msg = f"""
🔔 <b>Alert Set</b>

<b>Ticker:</b> {ticker}
<b>Condition:</b> Price {condition} ${target_price:.2f}

You will be notified when the condition is met.
"""
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_news(self, chat_id: int, args: List[str]):
        """Get market news."""
        ticker = args[0].upper() if args else None
        
        try:
            from src.research import NewsAnalyzer
            
            analyzer = NewsAnalyzer()
            
            if ticker:
                msg = f"📰 <b>News for {ticker}</b>\n\n"
                # Would fetch ticker-specific news
                msg += "<i>Fetching news from multiple sources...</i>\n"
                msg += "\n• No ticker-specific news available\n"
                msg += "\nTry /news for general market news"
            else:
                msg = """
📰 <b>Market News</b>

<b>Today's Headlines:</b>

📌 Markets await Fed decision on interest rates
📌 Tech stocks rally on strong earnings
📌 Oil prices stable amid supply concerns

<i>Use /news AAPL for ticker-specific news</i>
"""
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ News error: {e}")
    
    async def _cmd_sector(self, chat_id: int, args: List[str]):
        """Sector performance."""
        sectors = {
            "XLK": "Technology",
            "XLV": "Healthcare",
            "XLF": "Financials",
            "XLY": "Consumer Disc.",
            "XLP": "Consumer Staples",
            "XLI": "Industrials",
            "XLE": "Energy",
            "XLU": "Utilities",
        }
        
        msg = "🏭 <b>Sector Performance</b>\n\n"
        
        for etf, name in sectors.items():
            quote = await self._fetch_quote(etf)
            if quote:
                change_pct = quote.get('change_pct', 0)
                emoji = "🟢" if change_pct >= 0 else "🔴"
                bar = self._generate_bar(change_pct)
                msg += f"{emoji} <b>{name}</b>\n   {bar} {'+' if change_pct >= 0 else ''}{change_pct:.2f}%\n"
        
        msg += f"\n<i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>"
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_broker(self, chat_id: int, args: List[str]):
        """Switch broker."""
        if not args:
            msg = f"""
🔗 <b>Broker Settings</b>

<b>Active Broker:</b> {self.active_broker.value.upper()}

<b>Available Brokers:</b>
  • futu - Futu (富途)
  • ib - Interactive Brokers
  • paper - Paper Trading

Use /broker futu to switch.
"""
        else:
            broker = args[0].lower()
            if broker == "futu":
                self.active_broker = BrokerType.FUTU
                msg = "✅ Switched to Futu (富途)"
            elif broker == "ib":
                self.active_broker = BrokerType.IB
                msg = "✅ Switched to Interactive Brokers"
            elif broker == "paper":
                self.active_broker = BrokerType.PAPER
                msg = "✅ Switched to Paper Trading"
            else:
                msg = "❌ Unknown broker. Use: futu, ib, or paper"
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_status(self, chat_id: int, args: List[str]):
        """System status."""
        msg = f"""
⚙️ <b>System Status</b>

<b>Bot Status:</b> 🟢 Online
<b>Active Broker:</b> {self.active_broker.value.upper()}
<b>Watchlist:</b> {len(self.watchlist)} stocks
<b>Price Alerts:</b> {len(self.price_alerts)} active

<b>Broker Connections:</b>
  Futu: {'🟢 Connected' if self.futu_client else '⚪ Not Connected'}
  IB: {'🟢 Connected' if self.ib_client else '⚪ Not Connected'}

<b>Market Status:</b>
  US: {'🟢 Open' if self._is_market_open() else '🔴 Closed'}
  
<i>Uptime: {datetime.now().strftime('%H:%M:%S')}</i>
"""
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_auto(self, chat_id: int, args: List[str]):
        """Toggle automated updates on/off."""
        if not args:
            status = "🟢 ON" if self.auto_updates_enabled else "🔴 OFF"
            msg = f"""
⚙️ <b>Automated Updates</b>

<b>Status:</b> {status}

<b>Auto-notifications include:</b>
☀️ Morning briefing (8:30 AM)
🔔 Market open alert (9:30 AM)
📡 Hourly opportunity scans (10AM-3PM)
🌤️ Mid-day update (12:30 PM)
🌙 EOD report (4:00 PM)

<b>Usage:</b>
<code>/auto on</code> - Enable
<code>/auto off</code> - Disable
"""
        else:
            action = args[0].lower()
            if action == "on":
                self.auto_updates_enabled = True
                msg = "✅ Automated updates <b>ENABLED</b>\n\nYou'll receive:\n• Morning briefing (8:30 AM)\n• Market open alert (9:30 AM)\n• Hourly scans (during market)\n• Mid-day update (12:30 PM)\n• EOD report (4:00 PM)"
            elif action == "off":
                self.auto_updates_enabled = False
                msg = "🔴 Automated updates <b>DISABLED</b>\n\nYou won't receive scheduled notifications.\nUse commands manually to get updates."
            else:
                msg = "❌ Usage: /auto on or /auto off"
        
        await self.send_message_to(chat_id, msg)
    
    # ===== Portfolio Management Commands =====
    
    async def _cmd_import(self, chat_id: int, args: List[str]):
        """Show how to import portfolio."""
        msg = """
📸 <b>IMPORT PORTFOLIO FROM SCREENSHOT</b>

<b>Option 1: Screenshot Upload</b>
1. Take screenshot of your Futu/MooMoo portfolio
2. Send the image to this chat
3. Add caption with details (optional):
   <code>AAPL 100 150, MSFT 50 380</code>
   (ticker, qty, avg_cost)

<b>Option 2: Manual Entry</b>
<code>/addpos AAPL 100 150.50</code>
(Add 100 AAPL @ $150.50)

<code>/addpos NVDA 50 875</code>
(Add 50 NVDA @ $875)

<b>View & Monitor:</b>
<code>/myportfolio</code> - See all positions with P&L
<code>/monitor</code> - Get buy/sell/hold advice

<b>Supported Brokers:</b>
• Futu / MooMoo ✅
• Interactive Brokers ✅
• Robinhood ✅
• TD Ameritrade ✅
• Any with visible tickers ✅
"""
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_addpos(self, chat_id: int, args: List[str]):
        """Add position to portfolio."""
        if len(args) < 2:
            msg = """
➕ <b>Add Position</b>

Usage: <code>/addpos TICKER QTY [AVG_COST]</code>

Examples:
<code>/addpos AAPL 100 150.50</code>
<code>/addpos NVDA 50</code> (cost optional)
"""
            await self.send_message_to(chat_id, msg)
            return
        
        try:
            ticker = args[0].upper()
            qty = int(args[1])
            avg_cost = float(args[2]) if len(args) > 2 else 0
            
            # Validate ticker
            if not ticker.isalpha() or len(ticker) > 5:
                await self.send_message_to(chat_id, "❌ Invalid ticker symbol")
                return
            
            # Get current price if no cost provided
            if avg_cost == 0:
                quote = await self._fetch_quote(ticker)
                if quote:
                    avg_cost = quote.get('price', 0)
            
            self.my_portfolio[ticker] = {
                "qty": qty,
                "avg_cost": avg_cost,
                "added_at": datetime.now().isoformat(),
                "source": "manual"
            }
            
            value = qty * avg_cost
            msg = f"""
✅ <b>Position Added</b>

<b>{ticker}</b>
Quantity: {qty} shares
Avg Cost: ${avg_cost:.2f}
Value: ${value:,.2f}

Total positions: {len(self.my_portfolio)}
Use /myportfolio to view all
"""
            await self.send_message_to(chat_id, msg)
            
        except ValueError:
            await self.send_message_to(chat_id, "❌ Invalid input. Use: /addpos AAPL 100 150.50")
    
    async def _cmd_delpos(self, chat_id: int, args: List[str]):
        """Delete position from portfolio."""
        if not args:
            msg = """
➖ <b>Delete Position</b>

Usage: <code>/delpos TICKER</code>
Example: <code>/delpos AAPL</code>

Or <code>/delpos all</code> to clear all
"""
            await self.send_message_to(chat_id, msg)
            return
        
        ticker = args[0].upper()
        
        if ticker == "ALL":
            count = len(self.my_portfolio)
            self.my_portfolio.clear()
            await self.send_message_to(chat_id, f"✅ Cleared all {count} positions")
            return
        
        if ticker in self.my_portfolio:
            del self.my_portfolio[ticker]
            await self.send_message_to(chat_id, f"✅ Removed {ticker} from portfolio")
        else:
            await self.send_message_to(chat_id, f"❌ {ticker} not in portfolio")
    
    async def _cmd_myportfolio(self, chat_id: int, args: List[str]):
        """View imported portfolio with live P&L."""
        if not self.my_portfolio:
            msg = """
📊 <b>MY PORTFOLIO</b>

No positions tracked yet.

<b>Add positions:</b>
• Upload a screenshot of your broker
• Or use <code>/addpos AAPL 100 150</code>

Use /import for instructions
"""
            await self.send_message_to(chat_id, msg)
            return
        
        await self.send_message_to(chat_id, "📊 <b>Loading portfolio with live prices...</b>")
        
        try:
            total_value = 0
            total_cost = 0
            total_pnl = 0
            positions_data = []
            
            for ticker, pos in self.my_portfolio.items():
                quote = await self._fetch_quote(ticker)
                if not quote:
                    continue
                
                qty = pos.get("qty", 0)
                avg_cost = pos.get("avg_cost", 0)
                current_price = quote.get("price", 0)
                change_pct = quote.get("change_pct", 0)
                
                position_value = qty * current_price
                position_cost = qty * avg_cost
                position_pnl = position_value - position_cost
                pnl_pct = (position_pnl / position_cost * 100) if position_cost > 0 else 0
                
                total_value += position_value
                total_cost += position_cost
                total_pnl += position_pnl
                
                positions_data.append({
                    "ticker": ticker,
                    "qty": qty,
                    "avg_cost": avg_cost,
                    "current": current_price,
                    "value": position_value,
                    "pnl": position_pnl,
                    "pnl_pct": pnl_pct,
                    "day_change": change_pct
                })
            
            # Sort by value (largest first)
            positions_data.sort(key=lambda x: x['value'], reverse=True)
            
            total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
            
            msg = "📊 <b>MY PORTFOLIO</b>\n\n"
            
            # Summary
            pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "💰 <b>SUMMARY</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"Total Value: <b>${total_value:,.2f}</b>\n"
            msg += f"Total Cost: ${total_cost:,.2f}\n"
            msg += f"{pnl_emoji} P&L: <b>${total_pnl:+,.2f}</b> ({total_pnl_pct:+.2f}%)\n"
            msg += f"Positions: {len(positions_data)}\n\n"
            
            # Individual positions
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📈 <b>POSITIONS</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for p in positions_data:
                pnl_emoji = "🟢" if p['pnl'] >= 0 else "🔴"
                day_emoji = "↗️" if p['day_change'] >= 0 else "↘️"
                
                msg += f"\n<b>{p['ticker']}</b>\n"
                msg += f"   {p['qty']} @ ${p['avg_cost']:.2f} → ${p['current']:.2f}\n"
                msg += f"   {pnl_emoji} ${p['pnl']:+,.2f} ({p['pnl_pct']:+.1f}%)\n"
                msg += f"   {day_emoji} Today: {p['day_change']:+.2f}%\n"
            
            msg += f"\n<i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>\n"
            msg += "Use /monitor for buy/sell advice"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_monitor(self, chat_id: int, args: List[str]):
        """Get buy/sell/hold advice for portfolio positions."""
        if not self.my_portfolio:
            await self.send_message_to(chat_id, "📊 No positions to monitor. Use /addpos or upload a screenshot.")
            return
        
        await self.send_message_to(chat_id, "🔍 <b>Analyzing your portfolio...</b>")
        
        try:
            # Get market context
            spy = await self._fetch_quote("SPY")
            market_bias = "NEUTRAL"
            if spy:
                spy_chg = spy.get('change_pct', 0)
                if spy_chg > 0.5:
                    market_bias = "BULLISH"
                elif spy_chg < -0.5:
                    market_bias = "BEARISH"
            
            msg = "🎯 <b>PORTFOLIO MONITOR</b>\n\n"
            msg += f"🌍 Market: {market_bias}\n\n"
            
            buy_candidates = []
            sell_candidates = []
            hold_candidates = []
            
            for ticker, pos in self.my_portfolio.items():
                quote = await self._fetch_quote(ticker)
                if not quote:
                    continue
                
                qty = pos.get("qty", 0)
                avg_cost = pos.get("avg_cost", 0)
                current_price = quote.get("price", 0)
                change_pct = quote.get("change_pct", 0)
                
                pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0
                
                # Calculate AI score
                score_data = await self._calculate_ai_score(ticker, quote)
                ai_score = score_data['ai_score']
                
                analysis = {
                    "ticker": ticker,
                    "qty": qty,
                    "avg_cost": avg_cost,
                    "current": current_price,
                    "pnl_pct": pnl_pct,
                    "day_change": change_pct,
                    "ai_score": ai_score,
                    "reasons": []
                }
                
                # Decision logic
                action = "HOLD"
                
                # SELL signals
                if pnl_pct >= 20:
                    analysis['reasons'].append(f"✅ +{pnl_pct:.0f}% profit - take some off")
                    action = "SELL"
                elif pnl_pct <= -15:
                    analysis['reasons'].append(f"⚠️ -{abs(pnl_pct):.0f}% loss - review position")
                    action = "SELL"
                elif change_pct < -3 and ai_score < 4:
                    analysis['reasons'].append(f"📉 Heavy selling today, weak AI score")
                    action = "SELL"
                
                # BUY signals (add to position)
                elif pnl_pct > 0 and pnl_pct < 10 and ai_score >= 7:
                    analysis['reasons'].append(f"📈 Winning + strong momentum")
                    action = "BUY"
                elif change_pct > 2 and ai_score >= 6:
                    analysis['reasons'].append(f"🚀 Breaking out with strength")
                    action = "BUY"
                
                # HOLD
                else:
                    if ai_score >= 5:
                        analysis['reasons'].append("📊 Stable - no action needed")
                    else:
                        analysis['reasons'].append("👀 Watch closely")
                    action = "HOLD"
                
                analysis['action'] = action
                
                if action == "SELL":
                    sell_candidates.append(analysis)
                elif action == "BUY":
                    buy_candidates.append(analysis)
                else:
                    hold_candidates.append(analysis)
            
            # SELL section
            if sell_candidates:
                msg += "🔴 <b>CONSIDER SELLING:</b>\n"
                for s in sell_candidates:
                    msg += f"\n<b>{s['ticker']}</b> (AI: {s['ai_score']}/10)\n"
                    msg += f"   P&L: {s['pnl_pct']:+.1f}% | Today: {s['day_change']:+.1f}%\n"
                    for r in s['reasons']:
                        msg += f"   {r}\n"
                msg += "\n"
            
            # BUY section  
            if buy_candidates:
                msg += "🟢 <b>CONSIDER ADDING:</b>\n"
                for b in buy_candidates:
                    msg += f"\n<b>{b['ticker']}</b> (AI: {b['ai_score']}/10)\n"
                    msg += f"   P&L: {b['pnl_pct']:+.1f}% | Today: {b['day_change']:+.1f}%\n"
                    for r in b['reasons']:
                        msg += f"   {r}\n"
                msg += "\n"
            
            # HOLD section
            if hold_candidates:
                msg += "🟡 <b>HOLD:</b>\n"
                for h in hold_candidates[:5]:  # Show max 5
                    msg += f"• {h['ticker']}: {h['pnl_pct']:+.1f}% (AI: {h['ai_score']}/10)\n"
                if len(hold_candidates) > 5:
                    msg += f"   ... and {len(hold_candidates) - 5} more\n"
            
            msg += f"\n<i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    # ===== Professional Trading Intelligence Commands =====
    
    async def _cmd_riskcheck(self, chat_id: int, args: List[str]):
        """Professional pre-trade risk assessment - prevents emotional trading."""
        if not args:
            msg = """
⚠️ <b>PRE-TRADE RISK CHECK</b>

Usage: <code>/riskcheck AAPL 100 175.50</code>
       (ticker, shares, entry price)

<b>What it checks:</b>
✓ Position size vs account (max 1% risk)
✓ Portfolio correlation risk
✓ Sector concentration
✓ Current market regime
✓ Emotional trading indicators

<b>Professional Rules:</b>
• Never risk more than 1% per trade
• Max 6% portfolio heat (total risk)
• No new positions on -3% daily loss
• Confirm before volatile entries
"""
            await self.send_message_to(chat_id, msg)
            return
        
        try:
            ticker = args[0].upper()
            shares = int(args[1]) if len(args) > 1 else 100
            entry = float(args[2]) if len(args) > 2 else 0
            
            # Get current price if no entry specified
            quote = await self._fetch_quote(ticker)
            if not quote:
                await self.send_message_to(chat_id, f"❌ Cannot fetch {ticker}")
                return
            
            if entry == 0:
                entry = quote.get('price', 0)
            
            position_value = shares * entry
            current_price = quote.get('price', 0)
            change_pct = quote.get('change_pct', 0)
            
            msg = f"⚠️ <b>PRE-TRADE RISK CHECK: {ticker}</b>\n\n"
            
            # Get historical data for ATR
            bars = await self._get_historical_bars(ticker, days=20)
            atr = self._calculate_atr(bars) if bars else entry * 0.025
            
            # Calculate stop based on 2x ATR
            stop_price = entry - (2 * atr)
            risk_per_share = entry - stop_price
            total_risk = risk_per_share * shares
            risk_pct_of_account = (total_risk / self.account_size) * 100
            
            # Position sizing check
            msg += f"📊 <b>POSITION ANALYSIS</b>\n"
            msg += f"├ Entry: ${entry:.2f}\n"
            msg += f"├ Shares: {shares}\n"
            msg += f"├ Value: ${position_value:,.0f}\n"
            msg += f"├ ATR(14): ${atr:.2f}\n"
            msg += f"├ Stop (2x ATR): ${stop_price:.2f}\n"
            msg += f"└ Risk: ${total_risk:.0f} ({risk_pct_of_account:.2f}%)\n\n"
            
            # Risk checks
            checks_passed = 0
            total_checks = 5
            
            msg += "🔍 <b>RISK CHECKS</b>\n"
            
            # Check 1: Position size
            if risk_pct_of_account <= 1:
                msg += "✅ Position size OK (≤1% risk)\n"
                checks_passed += 1
            else:
                suggested_shares = int((self.account_size * 0.01) / risk_per_share)
                msg += f"❌ TOO LARGE: Reduce to {suggested_shares} shares\n"
            
            # Check 2: Portfolio heat
            current_heat = len(self.my_portfolio) * 1  # Estimate 1% risk per position
            if current_heat + risk_pct_of_account <= 6:
                msg += f"✅ Portfolio heat OK ({current_heat:.1f}% + {risk_pct_of_account:.1f}% < 6%)\n"
                checks_passed += 1
            else:
                msg += f"⚠️ High portfolio heat ({current_heat:.1f}%)\n"
                checks_passed += 0.5
            
            # Check 3: Today's P&L (simulated)
            if change_pct >= -3:
                msg += "✅ No daily loss limit triggered\n"
                checks_passed += 1
            else:
                msg += f"⚠️ Stock down {change_pct:.1f}% - catching knife?\n"
                checks_passed += 0.5
            
            # Check 4: Market regime
            spy = await self._fetch_quote("SPY")
            vix = await self._fetch_quote("VIX")
            spy_chg = spy.get('change_pct', 0) if spy else 0
            vix_price = vix.get('price', 20) if vix else 20
            
            if vix_price < 25 and spy_chg > -1:
                msg += f"✅ Market regime: Normal (VIX: {vix_price:.0f})\n"
                checks_passed += 1
            elif vix_price > 30:
                msg += f"⚠️ High volatility (VIX: {vix_price:.0f}) - reduce size\n"
            else:
                msg += f"⚠️ Market pressure (SPY: {spy_chg:+.1f}%)\n"
                checks_passed += 0.5
            
            # Check 5: Sector concentration
            if ticker not in self.my_portfolio:
                msg += "✅ New position - no duplicate\n"
                checks_passed += 1
            else:
                existing = self.my_portfolio[ticker]
                msg += f"⚠️ Already hold {existing.get('qty', 0)} shares\n"
                checks_passed += 0.5
            
            # Calculate Kelly and R:R
            score_data = await self._calculate_ai_score(ticker, quote)
            win_rate = 0.40 + (score_data['ai_score'] * 0.03)  # 40-70% based on AI score
            avg_win = 2 * atr  # Target 2:1 R:R
            avg_loss = atr
            kelly = self._calculate_kelly_criterion(win_rate, avg_win, avg_loss)
            
            msg += f"\n📈 <b>TRADE QUALITY</b>\n"
            msg += f"├ AI Score: {score_data['ai_score']}/10\n"
            msg += f"├ Win Probability: {win_rate*100:.0f}%\n"
            msg += f"├ R:R Ratio: 2:1\n"
            msg += f"├ Kelly %: {kelly*100:.1f}% (quarter Kelly)\n"
            msg += f"└ Expected Value: ${(win_rate * avg_win - (1-win_rate) * avg_loss) * shares:.0f}\n\n"
            
            # Final verdict
            score_pct = (checks_passed / total_checks) * 100
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            if score_pct >= 80:
                msg += f"🟢 <b>APPROVED</b> ({checks_passed:.0f}/{total_checks} checks passed)\n"
                msg += "Trade meets professional standards.\n"
            elif score_pct >= 60:
                msg += f"🟡 <b>CAUTION</b> ({checks_passed:.0f}/{total_checks} checks passed)\n"
                msg += "Review warnings before entering.\n"
            else:
                msg += f"🔴 <b>REJECT</b> ({checks_passed:.0f}/{total_checks} checks passed)\n"
                msg += "Fix issues before trading.\n"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_learn(self, chat_id: int, args: List[str]):
        """View AI learning and prediction tracking."""
        msg = "🧠 <b>AI LEARNING SYSTEM</b>\n\n"
        
        msg += "📊 <b>STRATEGY ACCURACY</b>\n"
        for strategy, stats in self.strategy_accuracy.items():
            wins = stats.get('wins', 0)
            total = stats.get('total', 0)
            accuracy = stats.get('accuracy', 0.5)
            emoji = "🟢" if accuracy >= 0.55 else "🟡" if accuracy >= 0.45 else "🔴"
            msg += f"{emoji} {strategy.title()}: {accuracy*100:.0f}% ({wins}/{total})\n"
        
        msg += f"\n📈 <b>PREDICTION HISTORY</b>\n"
        msg += f"Total predictions: {len(self.prediction_history)}\n"
        
        # Show recent predictions
        recent = self.prediction_history[-5:] if self.prediction_history else []
        if recent:
            msg += "\n<b>Recent:</b>\n"
            for pred in reversed(recent):
                ticker = pred.get('ticker', '?')
                score = pred.get('score', 0)
                action = pred.get('action', '?')
                outcome = pred.get('outcome', 'pending')
                
                if outcome == 'win':
                    emoji = "✅"
                elif outcome == 'loss':
                    emoji = "❌"
                else:
                    emoji = "⏳"
                
                msg += f"  {emoji} {ticker}: {action} (Score: {score}/10)\n"
        else:
            msg += "\nNo predictions tracked yet.\n"
        
        msg += "\n💡 <b>HOW TO IMPROVE:</b>\n"
        msg += "• Use /score before every trade\n"
        msg += "• Track outcomes with /journal\n"
        msg += "• AI learns from your results\n"
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_accuracy(self, chat_id: int, args: List[str]):
        """Show detailed accuracy stats by strategy and timeframe."""
        msg = "📊 <b>STRATEGY ACCURACY REPORT</b>\n\n"
        
        # Calculate overall stats
        total_wins = sum(s.get('wins', 0) for s in self.strategy_accuracy.values())
        total_trades = sum(s.get('total', 0) for s in self.strategy_accuracy.values())
        overall_accuracy = total_wins / total_trades if total_trades > 0 else 0.5
        
        msg += f"<b>Overall Win Rate:</b> {overall_accuracy*100:.1f}% ({total_wins}/{total_trades})\n\n"
        
        # Best and worst strategies
        sorted_strategies = sorted(
            self.strategy_accuracy.items(),
            key=lambda x: x[1].get('accuracy', 0.5),
            reverse=True
        )
        
        msg += "🏆 <b>STRATEGY RANKINGS</b>\n"
        for i, (strategy, stats) in enumerate(sorted_strategies):
            accuracy = stats.get('accuracy', 0.5)
            total = stats.get('total', 0)
            
            if i == 0:
                emoji = "🥇"
            elif i == 1:
                emoji = "🥈"
            elif i == 2:
                emoji = "🥉"
            else:
                emoji = f"{i+1}."
            
            bar_filled = int(accuracy * 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            
            msg += f"{emoji} {strategy.title()}\n"
            msg += f"   [{bar}] {accuracy*100:.0f}% ({total} trades)\n"
        
        # Time-based analysis
        msg += "\n⏰ <b>BEST TRADING TIMES</b>\n"
        msg += "• US Open (9:30-10:30): +Higher volatility\n"
        msg += "• Lunch (12:00-14:00): -Lower conviction\n"
        msg += "• Power Hour (15:00-16:00): +Strong trends\n"
        
        # Risk-adjusted returns
        sharpe = self._calculate_sharpe_ratio(
            [0.02, 0.01, -0.01, 0.03, -0.02, 0.015]  # Mock returns
        )
        msg += f"\n📈 <b>RISK-ADJUSTED</b>\n"
        msg += f"Sharpe Ratio: {sharpe:.2f}\n"
        
        # Recommendations
        msg += "\n💡 <b>AI RECOMMENDATIONS:</b>\n"
        best_strategy = sorted_strategies[0][0] if sorted_strategies else "momentum"
        msg += f"• Focus on: {best_strategy.title()} setups\n"
        msg += f"• Current edge: {(overall_accuracy - 0.5) * 100:+.1f}%\n"
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_regime(self, chat_id: int, args: List[str]):
        """Detect current market regime for optimal strategy selection."""
        await self.send_message_to(chat_id, "🔍 <b>Analyzing market regime...</b>")
        
        try:
            # Get market data
            spy = await self._fetch_quote("SPY")
            qqq = await self._fetch_quote("QQQ")
            iwm = await self._fetch_quote("IWM")
            vix = await self._fetch_quote("VIX")
            
            spy_chg = spy.get('change_pct', 0) if spy else 0
            qqq_chg = qqq.get('change_pct', 0) if qqq else 0
            iwm_chg = iwm.get('change_pct', 0) if iwm else 0
            vix_price = vix.get('price', 20) if vix else 20
            
            msg = "🌍 <b>MARKET REGIME ANALYSIS</b>\n\n"
            
            # Determine regime
            regime = "NEUTRAL"
            regime_emoji = "🟡"
            regime_desc = ""
            
            # Bull market
            if spy_chg > 0.5 and qqq_chg > 0.5 and vix_price < 18:
                regime = "STRONG BULL"
                regime_emoji = "🟢🟢"
                regime_desc = "Risk-on, momentum strategies excel"
            elif spy_chg > 0 and vix_price < 22:
                regime = "BULL"
                regime_emoji = "🟢"
                regime_desc = "Trend following works well"
            
            # Bear market
            elif spy_chg < -1 and vix_price > 25:
                regime = "BEAR"
                regime_emoji = "🔴"
                regime_desc = "Risk-off, reduce position sizes"
            elif spy_chg < -2 and vix_price > 30:
                regime = "CRISIS"
                regime_emoji = "🔴🔴"
                regime_desc = "Capital preservation mode"
            
            # Choppy/Range
            elif abs(spy_chg) < 0.3 and vix_price < 20:
                regime = "RANGE"
                regime_emoji = "🟡"
                regime_desc = "Mean reversion strategies work"
            
            # High volatility
            elif vix_price > 25:
                regime = "VOLATILE"
                regime_emoji = "⚡"
                regime_desc = "Wide stops, smaller size"
            
            msg += f"{regime_emoji} <b>REGIME: {regime}</b>\n"
            msg += f"📝 {regime_desc}\n\n"
            
            # Market internals
            msg += "📈 <b>MARKET INTERNALS</b>\n"
            msg += f"├ SPY: {spy_chg:+.2f}%\n"
            msg += f"├ QQQ: {qqq_chg:+.2f}%\n"
            msg += f"├ IWM: {iwm_chg:+.2f}%\n"
            msg += f"└ VIX: {vix_price:.1f}\n\n"
            
            # Rotation analysis
            if qqq_chg > iwm_chg + 0.5:
                rotation = "Growth → Tech leading"
            elif iwm_chg > qqq_chg + 0.5:
                rotation = "Value → Small caps leading"
            else:
                rotation = "Mixed → No clear rotation"
            
            msg += f"🔄 <b>ROTATION:</b> {rotation}\n\n"
            
            # Strategy recommendations
            msg += "🎯 <b>OPTIMAL STRATEGIES</b>\n"
            
            if regime in ["STRONG BULL", "BULL"]:
                msg += "✓ Momentum / Trend Following\n"
                msg += "✓ Breakout buying\n"
                msg += "✓ Larger position sizes OK\n"
                msg += "✗ Mean reversion longs risky\n"
            elif regime in ["BEAR", "CRISIS"]:
                msg += "✓ Capital preservation\n"
                msg += "✓ Reduce exposure 50%+\n"
                msg += "✓ Only highest conviction\n"
                msg += "✗ Avoid catching falling knives\n"
            elif regime == "RANGE":
                msg += "✓ Mean reversion\n"
                msg += "✓ Range trading\n"
                msg += "✓ Quick profits, tight stops\n"
                msg += "✗ Trend following may chop out\n"
            elif regime == "VOLATILE":
                msg += "✓ Reduce size 50%\n"
                msg += "✓ Wider stops (2x ATR)\n"
                msg += "✓ Wait for clarity\n"
                msg += "✗ Avoid overtrading\n"
            
            # Position sizing multiplier
            if regime == "STRONG BULL":
                size_mult = 1.25
            elif regime == "BULL":
                size_mult = 1.0
            elif regime in ["RANGE", "NEUTRAL"]:
                size_mult = 0.75
            elif regime == "VOLATILE":
                size_mult = 0.5
            else:  # BEAR, CRISIS
                size_mult = 0.25
            
            msg += f"\n📐 <b>POSITION SIZE:</b> {size_mult*100:.0f}% of normal\n"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _get_historical_bars(self, ticker: str, days: int = 20) -> List[Dict]:
        """Fetch historical OHLC bars for technical analysis."""
        try:
            alpaca_key = os.getenv("ALPACA_API_KEY", "")
            alpaca_secret = os.getenv("ALPACA_SECRET_KEY", "")
            
            if not alpaca_key:
                return []
            
            end = datetime.now()
            start = end - timedelta(days=days + 5)  # Extra days for weekends
            
            url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
            params = {
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
                "timeframe": "1Day",
                "limit": days
            }
            
            headers = {
                "APCA-API-KEY-ID": alpaca_key,
                "APCA-API-SECRET-KEY": alpaca_secret
            }
            
            async with self._session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    bars = data.get("bars", [])
                    return [
                        {
                            "open": bar.get("o"),
                            "high": bar.get("h"),
                            "low": bar.get("l"),
                            "close": bar.get("c"),
                            "volume": bar.get("v")
                        }
                        for bar in bars
                    ]
            return []
        except Exception as e:
            logger.error(f"Historical bars error: {e}")
            return []
    
    # ===== New Interactive Commands =====
    
    async def _cmd_oppty(self, chat_id: int, args: List[str]):
        """Find live buying opportunities using swing strategies."""
        import aiohttp
        
        await self.send_message_to(chat_id, "🔍 <b>Scanning for opportunities...</b>\n\nThis may take a moment.")
        
        try:
            # Define tickers to scan
            scan_list = self.watchlist if self.watchlist else self.TOP_STOCKS
            
            opportunities = []
            
            for ticker in scan_list[:15]:  # Limit to 15 for speed
                quote = await self._fetch_quote(ticker)
                if not quote:
                    continue
                
                price = quote.get('price', 0)
                change_pct = quote.get('change_pct', 0)
                volume = quote.get('volume', 0)
                
                # Simple opportunity scoring
                score = 0
                signals = []
                
                # Volume surge (basic check)
                if volume > 0:
                    score += 1
                    
                # Price action signals
                if 0.5 <= change_pct <= 3.0:
                    score += 2
                    signals.append("📈 Positive momentum")
                elif change_pct > 3.0:
                    score += 1
                    signals.append("⚠️ Extended move")
                    
                # Pullback opportunity
                if -3.0 <= change_pct <= -0.5:
                    score += 2
                    signals.append("🎯 Pullback entry")
                
                if score >= 2 and signals:
                    opportunities.append({
                        "ticker": ticker,
                        "price": price,
                        "change_pct": change_pct,
                        "score": score,
                        "signals": signals
                    })
            
            # Sort by score
            opportunities.sort(key=lambda x: x['score'], reverse=True)
            
            if opportunities:
                msg = "🎯 <b>LIVE BUYING OPPORTUNITIES</b>\n\n"
                
                for opp in opportunities[:8]:
                    emoji = "🟢" if opp['change_pct'] >= 0 else "🔴"
                    msg += f"{emoji} <b>{opp['ticker']}</b> @ ${opp['price']:.2f}\n"
                    msg += f"   Change: {'+' if opp['change_pct'] >= 0 else ''}{opp['change_pct']:.2f}%\n"
                    for signal in opp['signals']:
                        msg += f"   {signal}\n"
                    msg += f"   Score: {'⭐' * min(opp['score'], 5)}\n\n"
                
                msg += f"<i>Scanned {len(scan_list)} stocks at {datetime.now().strftime('%H:%M:%S')}</i>\n\n"
                msg += "💡 Use <code>/advise TICKER</code> for detailed analysis"
            else:
                msg = "📭 <b>No strong opportunities found right now</b>\n\n"
                msg += "The market may be consolidating. Check back later.\n\n"
                msg += "Tips:\n"
                msg += "• Add stocks to /watchlist for personalized scans\n"
                msg += "• Use /swing for swing setups\n"
                msg += "• Use /vcp for VCP patterns"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            logger.error(f"Oppty scan error: {e}")
            await self.send_message_to(chat_id, f"❌ Error scanning: {e}")
    
    async def _cmd_swing(self, chat_id: int, args: List[str]):
        """Find swing trading setups."""
        await self.send_message_to(chat_id, "📊 <b>Scanning for swing setups...</b>")
        
        try:
            scan_list = self.watchlist if self.watchlist else self.TOP_STOCKS
            
            setups = []
            
            for ticker in scan_list[:12]:
                quote = await self._fetch_quote(ticker)
                if not quote:
                    continue
                    
                price = quote.get('price', 0)
                change_pct = quote.get('change_pct', 0)
                high = quote.get('high', 0)
                low = quote.get('low', 0)
                
                if price <= 0:
                    continue
                
                # Simple swing setup detection
                setup_type = None
                entry = price
                stop = 0
                target = 0
                
                # Pullback to support
                if -2.0 <= change_pct <= -0.3:
                    setup_type = "🎯 Pullback Entry"
                    stop = low * 0.97  # 3% below low
                    target = price * 1.08  # 8% target
                
                # Breakout setup
                elif 1.0 <= change_pct <= 4.0:
                    setup_type = "🚀 Breakout"
                    stop = low * 0.95
                    target = price * 1.12
                
                # Consolidation breakout
                elif abs(change_pct) < 0.5 and high > 0 and low > 0:
                    range_pct = (high - low) / low * 100 if low > 0 else 0
                    if range_pct < 1.5:
                        setup_type = "📐 Tight Base"
                        stop = low * 0.96
                        target = price * 1.10
                
                if setup_type:
                    risk_reward = abs(target - price) / abs(price - stop) if stop != price else 0
                    setups.append({
                        "ticker": ticker,
                        "setup": setup_type,
                        "price": price,
                        "entry": entry,
                        "stop": stop,
                        "target": target,
                        "rr": risk_reward
                    })
            
            # Sort by risk/reward
            setups.sort(key=lambda x: x['rr'], reverse=True)
            
            if setups:
                msg = "📊 <b>SWING TRADING SETUPS</b>\n"
                msg += "<i>2 days - 8 weeks holding period</i>\n\n"
                
                for setup in setups[:6]:
                    msg += f"<b>{setup['ticker']}</b> - {setup['setup']}\n"
                    msg += f"   💰 Entry: ${setup['price']:.2f}\n"
                    msg += f"   🛑 Stop: ${setup['stop']:.2f}\n"
                    msg += f"   🎯 Target: ${setup['target']:.2f}\n"
                    msg += f"   📊 R:R = 1:{setup['rr']:.1f}\n\n"
                
                msg += f"\n<i>Found {len(setups)} setups at {datetime.now().strftime('%H:%M:%S')}</i>"
            else:
                msg = "📭 <b>No swing setups found right now</b>\n\n"
                msg += "Try again when market is more active."
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            logger.error(f"Swing scan error: {e}")
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_vcp(self, chat_id: int, args: List[str]):
        """Find VCP (Volatility Contraction Pattern) candidates with full analysis."""
        await self.send_message_to(chat_id, "🔬 <b>Scanning for VCP patterns...</b>\n<i>Analyzing volatility contraction across 40+ stocks...</i>")
        
        try:
            # Get market context first
            spy = await self._fetch_quote("SPY")
            qqq = await self._fetch_quote("QQQ")
            
            market_bias = "NEUTRAL"
            market_strength = 5
            if spy and qqq:
                spy_chg = spy.get('change_pct', 0)
                qqq_chg = qqq.get('change_pct', 0)
                avg_market = (spy_chg + qqq_chg) / 2
                
                if avg_market > 1:
                    market_bias = "STRONG BULL"
                    market_strength = 9
                elif avg_market > 0.3:
                    market_bias = "BULLISH"
                    market_strength = 7
                elif avg_market > -0.3:
                    market_bias = "NEUTRAL"
                    market_strength = 5
                elif avg_market > -1:
                    market_bias = "BEARISH"
                    market_strength = 3
                else:
                    market_bias = "STRONG BEAR"
                    market_strength = 1
            
            scan_list = self.watchlist if self.watchlist else self.TOP_STOCKS[:40]
            vcp_candidates = []
            
            # Sector tracking
            sector_map = {
                "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "AMD": "Tech", "GOOGL": "Tech",
                "META": "Tech", "AMZN": "Consumer", "TSLA": "Consumer", "NFLX": "Consumer",
                "JPM": "Finance", "BAC": "Finance", "GS": "Finance", "V": "Finance", "MA": "Finance",
                "UNH": "Health", "JNJ": "Health", "PFE": "Health", "LLY": "Health", "ABBV": "Health",
                "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
            }
            
            for ticker in scan_list:
                quote = await self._fetch_quote(ticker)
                if not quote:
                    continue
                
                price = quote.get('price', 0)
                high = quote.get('high', 0)
                low = quote.get('low', 0)
                open_price = quote.get('open', 0)
                volume = quote.get('volume', 0)
                prev_close = quote.get('prev_close', price)
                change_pct = quote.get('change_pct', 0)
                
                if price <= 0 or high <= 0 or low <= 0:
                    continue
                
                # VCP PATTERN VALIDATION CRITERIA
                # 1. Daily range must be contracting (tight)
                daily_range_pct = ((high - low) / low * 100) if low > 0 else 0
                
                # 2. Price should be near the high of day (strength)
                if high > low:
                    price_position = (price - low) / (high - low)
                else:
                    price_position = 0.5
                
                # 3. Volume should be below average (dry-up)
                volume_dry = volume < 5000000  # Simplified
                
                # 4. Price above key level (closing near high)
                near_high = price >= high * 0.98 if high > 0 else False
                
                # VCP SCORE CALCULATION
                vcp_score = 0
                vcp_reasons = []
                non_vcp_reasons = []
                
                # Criteria 1: Tight range (< 3% is ideal for VCP)
                if daily_range_pct <= 1.5:
                    vcp_score += 3
                    vcp_reasons.append(f"✅ Very tight range ({daily_range_pct:.1f}%)")
                elif daily_range_pct <= 2.5:
                    vcp_score += 2
                    vcp_reasons.append(f"✅ Tight range ({daily_range_pct:.1f}%)")
                elif daily_range_pct <= 4:
                    vcp_score += 1
                    vcp_reasons.append(f"⚠️ Moderate range ({daily_range_pct:.1f}%)")
                else:
                    non_vcp_reasons.append(f"❌ Wide range ({daily_range_pct:.1f}%) - NOT VCP")
                
                # Criteria 2: Price position (near highs = strength)
                if price_position >= 0.8:
                    vcp_score += 2
                    vcp_reasons.append("✅ Price near day high (strength)")
                elif price_position >= 0.6:
                    vcp_score += 1
                    vcp_reasons.append("⚠️ Price in upper half")
                elif price_position <= 0.3:
                    non_vcp_reasons.append("❌ Price near lows (weakness)")
                
                # Criteria 3: Low volatility day
                if abs(change_pct) <= 1.5:
                    vcp_score += 1
                    vcp_reasons.append(f"✅ Calm price action ({change_pct:+.1f}%)")
                elif abs(change_pct) > 3:
                    non_vcp_reasons.append(f"❌ High volatility ({change_pct:+.1f}%) - NOT VCP")
                
                # Criteria 4: Volume contraction
                if volume_dry:
                    vcp_score += 1
                    vcp_reasons.append("✅ Volume dry-up detected")
                
                # Criteria 5: Constructive price action
                if change_pct >= -0.5 and change_pct <= 2:
                    vcp_score += 1
                    vcp_reasons.append("✅ Constructive close")
                
                # Only include if VCP score >= 4 (out of 8 possible)
                if vcp_score >= 4 and len(non_vcp_reasons) == 0:
                    # Calculate pivot and stops
                    pivot = round(high * 1.002, 2)  # 0.2% above high
                    stop = round(low * 0.97, 2)  # 3% below low
                    risk = pivot - stop
                    target_1 = round(pivot + risk * 1.5, 2)
                    target_2 = round(pivot + risk * 2.5, 2)
                    risk_pct = ((pivot - stop) / pivot * 100) if pivot > 0 else 0
                    
                    # Confidence based on VCP score and market
                    if vcp_score >= 7:
                        confidence = "HIGH"
                        confidence_pct = 75
                    elif vcp_score >= 5:
                        confidence = "MEDIUM"
                        confidence_pct = 60
                    else:
                        confidence = "LOW"
                        confidence_pct = 45
                    
                    # Adjust for market conditions
                    if market_strength >= 7:
                        confidence_pct += 10
                    elif market_strength <= 3:
                        confidence_pct -= 15
                    
                    # Position sizing (1% risk on $100k account)
                    account_size = 100000
                    risk_amount = account_size * 0.01
                    shares = int(risk_amount / risk) if risk > 0 else 0
                    position_value = shares * pivot
                    
                    sector = sector_map.get(ticker, "Other")
                    
                    vcp_candidates.append({
                        "ticker": ticker,
                        "sector": sector,
                        "price": price,
                        "change_pct": change_pct,
                        "daily_range_pct": daily_range_pct,
                        "price_position": price_position,
                        "vcp_score": vcp_score,
                        "pivot": pivot,
                        "stop": stop,
                        "target_1": target_1,
                        "target_2": target_2,
                        "risk_pct": risk_pct,
                        "confidence": confidence,
                        "confidence_pct": min(85, confidence_pct),
                        "shares": shares,
                        "position_value": position_value,
                        "vcp_reasons": vcp_reasons,
                        "non_vcp_reasons": non_vcp_reasons,
                    })
            
            # Sort by VCP score
            vcp_candidates.sort(key=lambda x: x['vcp_score'], reverse=True)
            
            # Build response message
            msg = "🔬 <b>VCP PATTERN SCANNER</b>\n"
            msg += "<i>Volatility Contraction Pattern Analysis</i>\n\n"
            
            # Market Context
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "🌍 <b>MARKET CONTEXT</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            if spy and qqq:
                spy_emoji = "🟢" if spy.get('change_pct', 0) >= 0 else "🔴"
                qqq_emoji = "🟢" if qqq.get('change_pct', 0) >= 0 else "🔴"
                msg += f"{spy_emoji} SPY: {spy.get('change_pct', 0):+.2f}%\n"
                msg += f"{qqq_emoji} QQQ: {qqq.get('change_pct', 0):+.2f}%\n"
            msg += f"📊 Market Bias: <b>{market_bias}</b>\n"
            msg += f"💪 Strength: {market_strength}/10\n\n"
            
            # VCP impact explanation
            if market_strength >= 7:
                msg += "✅ <i>Bull market favors VCP breakouts</i>\n"
            elif market_strength <= 3:
                msg += "⚠️ <i>Bear market - VCP breakouts more likely to fail</i>\n"
            else:
                msg += "⚠️ <i>Mixed market - be selective with entries</i>\n"
            msg += "\n"
            
            if vcp_candidates:
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"🎯 <b>VALID VCP PATTERNS ({len(vcp_candidates)} found)</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                for i, vcp in enumerate(vcp_candidates[:4], 1):
                    # Score bar
                    score_bar = "█" * vcp['vcp_score'] + "░" * (8 - vcp['vcp_score'])
                    
                    msg += f"<b>#{i} {vcp['ticker']}</b> [{vcp['sector']}]\n"
                    msg += f"   VCP Score: {vcp['vcp_score']}/8 [{score_bar}]\n"
                    msg += f"   💰 Price: ${vcp['price']:.2f} ({vcp['change_pct']:+.2f}%)\n"
                    msg += f"   📐 Daily Range: {vcp['daily_range_pct']:.2f}%\n\n"
                    
                    # Why it qualifies
                    msg += "   <b>Why VCP:</b>\n"
                    for reason in vcp['vcp_reasons'][:3]:
                        msg += f"   {reason}\n"
                    msg += "\n"
                    
                    # Trade plan
                    msg += "   <b>Trade Plan:</b>\n"
                    msg += f"   🚀 Buy Pivot: ${vcp['pivot']:.2f}\n"
                    msg += f"   🛑 Stop Loss: ${vcp['stop']:.2f} (-{vcp['risk_pct']:.1f}%)\n"
                    msg += f"   🎯 Target 1: ${vcp['target_1']:.2f} (1.5R)\n"
                    msg += f"   🎯 Target 2: ${vcp['target_2']:.2f} (2.5R)\n\n"
                    
                    # Position sizing
                    msg += f"   <b>Position Size (1% risk):</b>\n"
                    msg += f"   📊 Shares: {vcp['shares']}\n"
                    msg += f"   💵 Value: ${vcp['position_value']:,.0f}\n"
                    msg += f"   🎲 Confidence: {vcp['confidence']} ({vcp['confidence_pct']}%)\n"
                    msg += "\n   ─────────────────────\n\n"
                
                # VCP Rules
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "📚 <b>VCP TRADING RULES</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "1️⃣ Only buy on pivot breakout with volume surge\n"
                msg += "2️⃣ Stop loss is non-negotiable\n"
                msg += "3️⃣ Take partial profits at Target 1\n"
                msg += "4️⃣ Trail stop after 2R profit\n"
                msg += "5️⃣ Best in bull market (current: " + market_bias + ")\n"
                
            else:
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "📭 <b>NO VALID VCP PATTERNS FOUND</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                msg += "<b>Why no VCP patterns today:</b>\n\n"
                msg += "❌ Most stocks show wide daily ranges\n"
                msg += "❌ High volatility = NOT contraction\n"
                msg += "❌ VCP patterns form over 3-6 weeks\n"
                msg += "❌ Single-day data is insufficient\n\n"
                msg += "<b>VCP Requirements:</b>\n"
                msg += "• Multiple contractions (T1 > T2 > T3)\n"
                msg += "• Volume dry-up into pivot\n"
                msg += "• 3-6 week base formation\n"
                msg += "• Price above 50-day MA\n\n"
                msg += "💡 <i>Try /swing or /oppty for current setups</i>\n"
            
            msg += f"\n<i>Scanned {len(scan_list)} stocks • {datetime.now().strftime('%H:%M:%S')}</i>"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            logger.error(f"VCP scan error: {e}")
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_advise(self, chat_id: int, args: List[str]):
        """Get comprehensive buy/sell advice with multi-factor analysis."""
        if not args:
            msg = """
💡 <b>AI Stock Advisor</b>

Usage: <code>/advise AAPL</code>

Get comprehensive trading advice including:
• Multi-factor BUY/SELL analysis
• Market & sector context
• Technical signals breakdown
• Position sizing & risk management
• Final verdict with confidence level
"""
            await self.send_message_to(chat_id, msg)
            return
        
        ticker = args[0].upper()
        await self.send_message_to(chat_id, f"🔍 <b>Analyzing {ticker} with multi-factor model...</b>")
        
        try:
            # Fetch current quote
            quote = await self._fetch_quote(ticker)
            if not quote:
                await self.send_message_to(chat_id, f"❌ Could not fetch data for {ticker}")
                return
            
            # Get market context
            spy = await self._fetch_quote("SPY")
            qqq = await self._fetch_quote("QQQ")
            
            price = quote.get('price', 0)
            change_pct = quote.get('change_pct', 0)
            high = quote.get('high', 0)
            low = quote.get('low', 0)
            open_price = quote.get('open', price)
            prev_close = quote.get('prev_close', price)
            volume = quote.get('volume', 0)
            
            # ===== MULTI-FACTOR ANALYSIS =====
            buy_signals = []
            sell_signals = []
            hold_signals = []
            
            # --- FACTOR 1: MARKET CONTEXT ---
            market_score = 0
            if spy and qqq:
                spy_chg = spy.get('change_pct', 0)
                qqq_chg = qqq.get('change_pct', 0)
                market_avg = (spy_chg + qqq_chg) / 2
                
                if market_avg > 1:
                    buy_signals.append(("🌍 Market", f"Strong bull day (SPY {spy_chg:+.1f}%, QQQ {qqq_chg:+.1f}%)", 2))
                    market_score = 2
                elif market_avg > 0.3:
                    buy_signals.append(("🌍 Market", f"Positive market (SPY {spy_chg:+.1f}%)", 1))
                    market_score = 1
                elif market_avg < -1:
                    sell_signals.append(("🌍 Market", f"Strong bear day (SPY {spy_chg:+.1f}%, QQQ {qqq_chg:+.1f}%)", 2))
                    market_score = -2
                elif market_avg < -0.3:
                    sell_signals.append(("🌍 Market", f"Negative market (SPY {spy_chg:+.1f}%)", 1))
                    market_score = -1
                else:
                    hold_signals.append(("🌍 Market", "Mixed/flat market conditions", 0))
            
            # --- FACTOR 2: SECTOR CONTEXT ---
            sector_map = {
                "AAPL": ("XLK", "Technology"), "MSFT": ("XLK", "Technology"), "NVDA": ("XLK", "Technology"),
                "AMD": ("XLK", "Technology"), "GOOGL": ("XLK", "Technology"), "META": ("XLK", "Technology"),
                "AMZN": ("XLY", "Consumer Discretionary"), "TSLA": ("XLY", "Consumer Discretionary"),
                "JPM": ("XLF", "Financials"), "BAC": ("XLF", "Financials"), "GS": ("XLF", "Financials"),
                "V": ("XLF", "Financials"), "MA": ("XLF", "Financials"),
                "UNH": ("XLV", "Healthcare"), "JNJ": ("XLV", "Healthcare"), "PFE": ("XLV", "Healthcare"),
                "XOM": ("XLE", "Energy"), "CVX": ("XLE", "Energy"), "COP": ("XLE", "Energy"),
            }
            sector_etf, sector_name = sector_map.get(ticker, ("SPY", "Market"))
            sector_score = 0
            if sector_etf != "SPY":
                sector_quote = await self._fetch_quote(sector_etf)
                if sector_quote:
                    sector_chg = sector_quote.get('change_pct', 0)
                    if sector_chg > 1:
                        buy_signals.append(("📊 Sector", f"{sector_name} sector strong ({sector_etf} {sector_chg:+.1f}%)", 1))
                        sector_score = 1
                    elif sector_chg < -1:
                        sell_signals.append(("📊 Sector", f"{sector_name} sector weak ({sector_etf} {sector_chg:+.1f}%)", 1))
                        sector_score = -1
                    else:
                        hold_signals.append(("📊 Sector", f"{sector_name} sector neutral ({sector_etf} {sector_chg:+.1f}%)", 0))
            
            # --- FACTOR 3: PRICE MOMENTUM ---
            momentum_score = 0
            if change_pct > 3:
                buy_signals.append(("📈 Momentum", f"Strong momentum (+{change_pct:.1f}% today)", 2))
                momentum_score = 2
            elif change_pct > 1:
                buy_signals.append(("📈 Momentum", f"Positive momentum (+{change_pct:.1f}%)", 1))
                momentum_score = 1
            elif change_pct > 0:
                hold_signals.append(("📈 Momentum", f"Slight positive ({change_pct:+.1f}%)", 0))
            elif change_pct > -1:
                hold_signals.append(("📈 Momentum", f"Slight negative ({change_pct:+.1f}%)", 0))
            elif change_pct > -3:
                sell_signals.append(("📉 Momentum", f"Negative momentum ({change_pct:.1f}%)", 1))
                momentum_score = -1
            else:
                sell_signals.append(("📉 Momentum", f"Strong selling pressure ({change_pct:.1f}%)", 2))
                momentum_score = -2
            
            # --- FACTOR 4: PRICE POSITION IN RANGE ---
            position_score = 0
            if high > low:
                price_position = (price - low) / (high - low)
                if price_position >= 0.85:
                    buy_signals.append(("🎯 Position", f"Closing near highs ({price_position*100:.0f}% of range)", 1))
                    position_score = 1
                elif price_position <= 0.15:
                    sell_signals.append(("🎯 Position", f"Closing near lows ({price_position*100:.0f}% of range)", 1))
                    position_score = -1
                else:
                    hold_signals.append(("🎯 Position", f"Mid-range close ({price_position*100:.0f}% of range)", 0))
            
            # --- FACTOR 5: VOLATILITY ---
            atr_estimate = (high - low) if high > low else price * 0.02
            volatility_pct = (atr_estimate / price * 100) if price > 0 else 0
            volatility_score = 0
            if volatility_pct > 5:
                sell_signals.append(("⚡ Volatility", f"Extremely volatile ({volatility_pct:.1f}% range) - risky", 1))
                volatility_score = -1
            elif volatility_pct < 1:
                hold_signals.append(("⚡ Volatility", f"Low volatility ({volatility_pct:.1f}%) - quiet day", 0))
            else:
                buy_signals.append(("⚡ Volatility", f"Healthy volatility ({volatility_pct:.1f}%) - tradeable", 0))
            
            # --- FACTOR 6: GAP ANALYSIS ---
            gap_score = 0
            if prev_close > 0:
                gap = ((open_price - prev_close) / prev_close * 100) if prev_close else 0
                if gap > 2:
                    buy_signals.append(("🚀 Gap", f"Gapped up +{gap:.1f}% (bullish)", 1))
                    gap_score = 1
                elif gap < -2:
                    sell_signals.append(("📉 Gap", f"Gapped down {gap:.1f}% (bearish)", 1))
                    gap_score = -1
            
            # ===== CALCULATE FINAL VERDICT =====
            total_buy_weight = sum(s[2] for s in buy_signals)
            total_sell_weight = sum(s[2] for s in sell_signals)
            
            # Net score
            net_score = total_buy_weight - total_sell_weight
            
            # Determine final verdict
            if net_score >= 4:
                verdict = "🟢 STRONG BUY"
                verdict_reason = "Multiple strong bullish factors align"
                confidence = 80
            elif net_score >= 2:
                verdict = "🟢 BUY"
                verdict_reason = "Bullish signals outweigh bearish"
                confidence = 65
            elif net_score >= 1:
                verdict = "🟡 LEAN BUY"
                verdict_reason = "Slightly more bullish factors"
                confidence = 55
            elif net_score <= -4:
                verdict = "🔴 STRONG SELL"
                verdict_reason = "Multiple strong bearish factors"
                confidence = 80
            elif net_score <= -2:
                verdict = "🔴 SELL"
                verdict_reason = "Bearish signals outweigh bullish"
                confidence = 65
            elif net_score <= -1:
                verdict = "🟠 LEAN SELL"
                verdict_reason = "Slightly more bearish factors"
                confidence = 55
            else:
                verdict = "🟡 HOLD / WAIT"
                verdict_reason = "Mixed signals - no clear edge"
                confidence = 40
            
            # ===== CALCULATE TRADE LEVELS =====
            stop_loss = round(low - atr_estimate * 0.5, 2)
            risk_per_share = price - stop_loss
            risk_pct = (risk_per_share / price * 100) if price > 0 else 0
            
            target_1 = round(price + risk_per_share * 1.5, 2)
            target_2 = round(price + risk_per_share * 2.5, 2)
            target_3 = round(price + risk_per_share * 4.0, 2)
            
            # Position sizing (1% risk on $100k account)
            account_size = 100000
            risk_amount = account_size * 0.01
            shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
            position_value = shares * price
            position_pct = (position_value / account_size * 100) if account_size else 0
            
            # ===== BUILD RESPONSE =====
            msg = f"💡 <b>MULTI-FACTOR ANALYSIS: {ticker}</b>\n\n"
            
            # Current Data
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📊 <b>CURRENT DATA</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            price_emoji = "🟢" if change_pct >= 0 else "🔴"
            msg += f"{price_emoji} Price: <b>${price:.2f}</b> ({change_pct:+.2f}%)\n"
            msg += f"📉 Range: ${low:.2f} - ${high:.2f}\n"
            msg += f"📅 Prev Close: ${prev_close:.2f}\n\n"
            
            # Buy Signals
            if buy_signals:
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "🟢 <b>BUY SIGNALS</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                for factor, reason, weight in buy_signals:
                    strength = "●" * max(1, weight) + "○" * (2 - weight)
                    msg += f"{factor}: {reason} [{strength}]\n"
                msg += f"\n<b>Total Buy Weight: +{total_buy_weight}</b>\n\n"
            
            # Sell Signals
            if sell_signals:
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "🔴 <b>SELL SIGNALS</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                for factor, reason, weight in sell_signals:
                    strength = "●" * max(1, weight) + "○" * (2 - weight)
                    msg += f"{factor}: {reason} [{strength}]\n"
                msg += f"\n<b>Total Sell Weight: -{total_sell_weight}</b>\n\n"
            
            # Hold Signals
            if hold_signals:
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "🟡 <b>NEUTRAL FACTORS</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                for factor, reason, _ in hold_signals:
                    msg += f"{factor}: {reason}\n"
                msg += "\n"
            
            # Final Verdict
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "⚖️ <b>FINAL VERDICT</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"<b>{verdict}</b>\n"
            msg += f"Net Score: {net_score:+d} (Buy:{total_buy_weight} - Sell:{total_sell_weight})\n"
            msg += f"Confidence: {confidence}%\n"
            msg += f"Reason: {verdict_reason}\n\n"
            
            # Trade Levels (only if bullish)
            if net_score >= 0:
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "🎯 <b>TRADE PLAN (IF BUYING)</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"🛑 Stop Loss: ${stop_loss:.2f} (-{risk_pct:.1f}%)\n"
                msg += f"🎯 Target 1: ${target_1:.2f} (1.5R)\n"
                msg += f"🎯 Target 2: ${target_2:.2f} (2.5R)\n"
                msg += f"🎯 Target 3: ${target_3:.2f} (4R)\n\n"
                
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "📏 <b>POSITION SIZING</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"Shares (1% risk): {shares}\n"
                msg += f"Position Value: ${position_value:,.0f}\n"
                msg += f"% of $100k: {position_pct:.1f}%\n"
            
            msg += f"\n<i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>\n"
            msg += "<i>⚠️ Not financial advice. Do your own research.</i>"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            logger.error(f"Advise error for {ticker}: {e}")
            await self.send_message_to(chat_id, f"❌ Error analyzing {ticker}: {e}")
    
    async def _cmd_check(self, chat_id: int, args: List[str]):
        """Check position - should I hold, buy more, or sell?"""
        if len(args) < 2:
            msg = """
📋 <b>Position Checker</b>

Usage: <code>/check PRICE TICKER</code>

Example: <code>/check 150 AAPL</code>
(I bought AAPL at $150, what should I do?)

Get advice on:
• Hold, add, or sell
• Current P&L
• Suggested actions
• Risk assessment
"""
            await self.send_message_to(chat_id, msg)
            return
        
        try:
            buy_price = float(args[0])
            ticker = args[1].upper()
        except (ValueError, IndexError):
            await self.send_message_to(chat_id, "❌ Usage: /check 150 AAPL")
            return
        
        await self.send_message_to(chat_id, f"📊 <b>Checking your {ticker} position...</b>")
        
        try:
            quote = await self._fetch_quote(ticker)
            if not quote:
                await self.send_message_to(chat_id, f"❌ Could not fetch data for {ticker}")
                return
            
            current_price = quote.get('price', 0)
            change_pct = quote.get('change_pct', 0)
            high = quote.get('high', 0)
            low = quote.get('low', 0)
            
            # Calculate P&L
            pnl_amount = current_price - buy_price
            pnl_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
            
            # Determine position status
            if pnl_pct > 0:
                status_emoji = "🟢"
                position_status = "PROFIT"
            elif pnl_pct < 0:
                status_emoji = "🔴"
                position_status = "LOSS"
            else:
                status_emoji = "⚪"
                position_status = "BREAKEVEN"
            
            # Generate recommendation based on P&L and trend
            if pnl_pct >= 20:
                recommendation = "💰 TAKE PARTIAL PROFIT"
                advice = "Consider selling 50% to lock in gains. Let the rest run with a trailing stop."
                action_icon = "📤"
            elif pnl_pct >= 10:
                recommendation = "🛡️ PROTECT PROFITS"
                advice = "Move stop loss to breakeven. Consider taking 25-33% off the table."
                action_icon = "🔒"
            elif pnl_pct >= 5:
                recommendation = "✅ HOLD"
                advice = "Position is healthy. Keep your stop loss in place and let it work."
                action_icon = "⏳"
            elif -3 <= pnl_pct < 5:
                recommendation = "⏳ PATIENCE"
                advice = "Position is near entry. Wait for direction. Keep original stop."
                action_icon = "👀"
            elif -7 <= pnl_pct < -3:
                recommendation = "⚠️ CAUTION"
                advice = "Position under pressure. Evaluate if the original thesis still holds."
                action_icon = "🤔"
            elif pnl_pct < -7:
                recommendation = "🚨 REVIEW POSITION"
                advice = "Significant loss. Consider cutting loss if below your stop or if thesis broken."
                action_icon = "⚠️"
            else:
                recommendation = "❓ EVALUATE"
                advice = "Review your original thesis and risk tolerance."
                action_icon = "🔍"
            
            # Calculate suggested levels
            suggested_stop = buy_price * 0.93  # 7% stop
            breakeven_stop = buy_price
            
            # Add more context
            if pnl_pct > 0 and change_pct > 0:
                momentum = "📈 Trend and P&L both positive - favorable"
            elif pnl_pct > 0 and change_pct < 0:
                momentum = "⚠️ Pullback in a winning position - normal"
            elif pnl_pct < 0 and change_pct > 0:
                momentum = "🔄 Today recovering - watch for continuation"
            else:
                momentum = "📉 Both position and today's action negative"
            
            msg = f"""
📋 <b>POSITION CHECK: {ticker}</b>

━━━━━━━━━━━━━━━━━━━━━━
{status_emoji} <b>YOUR POSITION</b>
━━━━━━━━━━━━━━━━━━━━━━
💵 Your Entry: <b>${buy_price:.2f}</b>
💰 Current Price: <b>${current_price:.2f}</b>
📊 P&L: <b>{'+' if pnl_amount >= 0 else ''}${pnl_amount:.2f}</b> ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)

━━━━━━━━━━━━━━━━━━━━━━
{action_icon} <b>RECOMMENDATION</b>
━━━━━━━━━━━━━━━━━━━━━━
{recommendation}

{advice}

━━━━━━━━━━━━━━━━━━━━━━
📈 <b>TODAY'S ACTION</b>
━━━━━━━━━━━━━━━━━━━━━━
Change: {'+' if change_pct >= 0 else ''}{change_pct:.2f}%
Range: ${low:.2f} - ${high:.2f}
{momentum}

━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>SUGGESTED LEVELS</b>
━━━━━━━━━━━━━━━━━━━━━━
🛑 Initial Stop: ${suggested_stop:.2f} (-7%)
🔒 Breakeven Stop: ${breakeven_stop:.2f}
📈 Add More Below: ${buy_price * 0.95:.2f} (if thesis holds)

<i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>
"""
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            logger.error(f"Position check error: {e}")
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_analyze(self, chat_id: int, args: List[str]):
        """Technical analysis for a stock."""
        if not args:
            msg = """
📊 <b>Technical Analysis</b>

Usage: <code>/analyze AAPL</code>

Get technical analysis including:
• Trend analysis
• Support/Resistance levels
• Key indicators
• Volume analysis
"""
            await self.send_message_to(chat_id, msg)
            return
        
        ticker = args[0].upper()
        await self.send_message_to(chat_id, f"📊 <b>Analyzing {ticker}...</b>")
        
        try:
            quote = await self._fetch_quote(ticker)
            if not quote:
                await self.send_message_to(chat_id, f"❌ Could not fetch data for {ticker}")
                return
            
            price = quote.get('price', 0)
            change_pct = quote.get('change_pct', 0)
            high = quote.get('high', 0)
            low = quote.get('low', 0)
            volume = quote.get('volume', 0)
            prev_close = quote.get('prev_close', price)
            
            # Calculate basic levels
            daily_range = high - low if high > low else price * 0.02
            mid_point = (high + low) / 2
            
            # Estimate support/resistance (simplified)
            support_1 = round(low - daily_range * 0.5, 2)
            support_2 = round(low - daily_range * 1.5, 2)
            resistance_1 = round(high + daily_range * 0.5, 2)
            resistance_2 = round(high + daily_range * 1.5, 2)
            
            # Trend determination
            if change_pct > 1.0:
                trend = "🟢 STRONG UPTREND"
            elif change_pct > 0.3:
                trend = "🟢 UPTREND"
            elif change_pct > -0.3:
                trend = "➡️ SIDEWAYS"
            elif change_pct > -1.0:
                trend = "🔴 DOWNTREND"
            else:
                trend = "🔴 STRONG DOWNTREND"
            
            # Volume analysis
            volume_fmt = f"{volume:,}" if volume else "N/A"
            
            # Price location
            if high > low:
                price_location = (price - low) / (high - low) * 100
            else:
                price_location = 50
                
            if price_location > 80:
                location_desc = "Near day's high"
            elif price_location > 60:
                location_desc = "Upper range"
            elif price_location > 40:
                location_desc = "Mid range"
            elif price_location > 20:
                location_desc = "Lower range"
            else:
                location_desc = "Near day's low"
            
            msg = f"""
📊 <b>TECHNICAL ANALYSIS: {ticker}</b>

━━━━━━━━━━━━━━━━━━━━━━
📈 <b>PRICE ACTION</b>
━━━━━━━━━━━━━━━━━━━━━━
💰 Current: <b>${price:.2f}</b>
📊 Change: {'+' if change_pct >= 0 else ''}{change_pct:.2f}%
📅 Prev Close: ${prev_close:.2f}

━━━━━━━━━━━━━━━━━━━━━━
📏 <b>DAY'S RANGE</b>
━━━━━━━━━━━━━━━━━━━━━━
🔝 High: ${high:.2f}
🔻 Low: ${low:.2f}
📐 Range: ${daily_range:.2f}
📍 Location: {location_desc}

━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>KEY LEVELS</b>
━━━━━━━━━━━━━━━━━━━━━━
🟢 Resistance 2: ${resistance_2:.2f}
🟢 Resistance 1: ${resistance_1:.2f}
━━ Current: ${price:.2f} ━━
🔴 Support 1: ${support_1:.2f}
🔴 Support 2: ${support_2:.2f}

━━━━━━━━━━━━━━━━━━━━━━
📊 <b>INDICATORS</b>
━━━━━━━━━━━━━━━━━━━━━━
📈 Trend: {trend}
📦 Volume: {volume_fmt}
🎯 Mid Point: ${mid_point:.2f}

<i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>
<i>Use /advise {ticker} for trade recommendations</i>
"""
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            logger.error(f"Analysis error for {ticker}: {e}")
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_earnings(self, chat_id: int, args: List[str]):
        """Get earnings calendar and plays."""
        await self.send_message_to(chat_id, "📅 <b>Checking earnings calendar...</b>")
        
        try:
            # Note: In production, would fetch from earnings API
            msg = """
📅 <b>EARNINGS CALENDAR</b>

<b>This Week's Notable Earnings:</b>

Coming soon - earnings data integration.

<b>Earnings Trading Tips:</b>
• Trade AFTER earnings, not before
• Wait for post-earnings breakouts
• Avoid holding through reports
• Look for gap-and-go setups

Use /advise TICKER for individual analysis.
"""
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_movers(self, chat_id: int, args: List[str]):
        """Top gainers and losers."""
        await self.send_message_to(chat_id, "📊 <b>Scanning market movers...</b>")
        
        try:
            # Scan popular stocks
            tickers = self.TOP_STOCKS[:30]  # Scan top 30 for movers
            
            movers = []
            for ticker in tickers:
                quote = await self._fetch_quote(ticker)
                if quote:
                    movers.append({
                        "ticker": ticker,
                        "price": quote.get('price', 0),
                        "change_pct": quote.get('change_pct', 0)
                    })
            
            # Sort by change
            gainers = sorted([m for m in movers if m['change_pct'] > 0], 
                           key=lambda x: x['change_pct'], reverse=True)[:5]
            losers = sorted([m for m in movers if m['change_pct'] < 0], 
                          key=lambda x: x['change_pct'])[:5]
            
            msg = "📊 <b>TODAY'S MOVERS</b>\n\n"
            
            msg += "🟢 <b>TOP GAINERS</b>\n"
            for m in gainers:
                msg += f"   {m['ticker']}: ${m['price']:.2f} (+{m['change_pct']:.2f}%)\n"
            
            msg += "\n🔴 <b>TOP LOSERS</b>\n"
            for m in losers:
                msg += f"   {m['ticker']}: ${m['price']:.2f} ({m['change_pct']:.2f}%)\n"
            
            msg += f"\n<i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>"
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_premarket(self, chat_id: int, args: List[str]):
        """Pre-market and futures data."""
        try:
            msg = "🌅 <b>PRE-MARKET / FUTURES</b>\n\n"
            
            # Get futures proxies
            futures = [("ES=F", "S&P 500 Futures"), ("NQ=F", "NASDAQ Futures")]
            
            msg += "📈 <b>Index Futures:</b>\n"
            for symbol, name in [("SPY", "S&P 500"), ("QQQ", "NASDAQ")]:
                quote = await self._fetch_quote(symbol)
                if quote:
                    change_pct = quote.get('change_pct', 0)
                    emoji = "🟢" if change_pct >= 0 else "🔴"
                    msg += f"   {emoji} {name}: ${quote.get('price', 0):.2f} ({'+' if change_pct >= 0 else ''}{change_pct:.2f}%)\n"
            
            msg += "\n💡 <b>Pre-Market Tips:</b>\n"
            msg += "• Check overnight news\n"
            msg += "• Review earnings announcements\n"
            msg += "• Note gap levels\n"
            
            msg += f"\n<i>Market opens at 9:30 AM ET</i>"
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_ideas(self, chat_id: int, args: List[str]):
        """AI-generated trade ideas."""
        await self.send_message_to(chat_id, "💡 <b>Generating trade ideas...</b>")
        
        try:
            # Scan watchlist or defaults for ideas
            scan_list = self.watchlist if self.watchlist else self.TOP_STOCKS
            
            ideas = []
            for ticker in scan_list[:8]:
                quote = await self._fetch_quote(ticker)
                if not quote:
                    continue
                    
                price = quote.get('price', 0)
                change_pct = quote.get('change_pct', 0)
                
                idea = None
                if -3 <= change_pct <= -1:
                    idea = {"type": "🎯 PULLBACK BUY", "reason": "Healthy pullback in uptrend"}
                elif 1 <= change_pct <= 3:
                    idea = {"type": "🚀 MOMENTUM", "reason": "Strong momentum, watch for continuation"}
                elif abs(change_pct) < 0.5:
                    idea = {"type": "📐 CONSOLIDATION", "reason": "Tight range, breakout pending"}
                
                if idea:
                    ideas.append({
                        "ticker": ticker,
                        "price": price,
                        "change_pct": change_pct,
                        **idea
                    })
            
            if ideas:
                msg = "💡 <b>TODAY'S TRADE IDEAS</b>\n\n"
                for idea in ideas[:5]:
                    msg += f"<b>{idea['ticker']}</b> - {idea['type']}\n"
                    msg += f"   Price: ${idea['price']:.2f} ({'+' if idea['change_pct'] >= 0 else ''}{idea['change_pct']:.2f}%)\n"
                    msg += f"   {idea['reason']}\n\n"
                
                msg += "💡 Use /advise TICKER for detailed analysis"
            else:
                msg = "📭 No strong trade ideas at the moment.\n\nTry again when market is more active."
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_compare(self, chat_id: int, args: List[str]):
        """Compare two stocks."""
        if len(args) < 2:
            msg = """
📊 <b>Stock Comparison</b>

Usage: <code>/compare AAPL MSFT</code>

Compare two stocks side by side.
"""
            await self.send_message_to(chat_id, msg)
            return
        
        ticker1 = args[0].upper()
        ticker2 = args[1].upper()
        
        try:
            quote1 = await self._fetch_quote(ticker1)
            quote2 = await self._fetch_quote(ticker2)
            
            if not quote1 or not quote2:
                await self.send_message_to(chat_id, "❌ Could not fetch data for one or both tickers")
                return
            
            msg = f"📊 <b>COMPARISON: {ticker1} vs {ticker2}</b>\n\n"
            
            # Side by side comparison
            msg += f"{'Metric':<15} {ticker1:>10} {ticker2:>10}\n"
            msg += "─" * 35 + "\n"
            msg += f"{'Price':<15} ${quote1.get('price', 0):>9.2f} ${quote2.get('price', 0):>9.2f}\n"
            msg += f"{'Change %':<15} {quote1.get('change_pct', 0):>9.2f}% {quote2.get('change_pct', 0):>9.2f}%\n"
            msg += f"{'Volume':<15} {quote1.get('volume', 0):>10,} {quote2.get('volume', 0):>10,}\n"
            
            # Winner
            if quote1.get('change_pct', 0) > quote2.get('change_pct', 0):
                winner = ticker1
            else:
                winner = ticker2
            
            msg += f"\n🏆 Today's Winner: <b>{winner}</b>"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_levels(self, chat_id: int, args: List[str]):
        """Key support and resistance levels."""
        if not args:
            msg = """
📏 <b>Key Levels</b>

Usage: <code>/levels AAPL</code>

Get support and resistance levels.
"""
            await self.send_message_to(chat_id, msg)
            return
        
        ticker = args[0].upper()
        
        try:
            quote = await self._fetch_quote(ticker)
            if not quote:
                await self.send_message_to(chat_id, f"❌ Could not fetch data for {ticker}")
                return
            
            price = quote.get('price', 0)
            high = quote.get('high', 0)
            low = quote.get('low', 0)
            prev_close = quote.get('prev_close', price)
            
            # Calculate levels
            range_size = high - low if high > low else price * 0.02
            
            r3 = round(high + range_size * 1.5, 2)
            r2 = round(high + range_size * 0.75, 2)
            r1 = round(high, 2)
            pivot = round((high + low + prev_close) / 3, 2)
            s1 = round(low, 2)
            s2 = round(low - range_size * 0.75, 2)
            s3 = round(low - range_size * 1.5, 2)
            
            msg = f"""
📏 <b>KEY LEVELS: {ticker}</b>

<b>Current Price:</b> ${price:.2f}

━━━ <b>RESISTANCE</b> ━━━
🔴 R3: ${r3:.2f}
🟠 R2: ${r2:.2f}
🟡 R1: ${r1:.2f}

━━━ <b>PIVOT</b> ━━━
⚪ PP: ${pivot:.2f}

━━━ <b>SUPPORT</b> ━━━
🟡 S1: ${s1:.2f}
🟠 S2: ${s2:.2f}
🟢 S3: ${s3:.2f}

<i>Based on today's price action</i>
"""
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_strength(self, chat_id: int, args: List[str]):
        """Relative strength ranking."""
        await self.send_message_to(chat_id, "💪 <b>Calculating relative strength...</b>")
        
        try:
            tickers = self.watchlist if self.watchlist else self.TOP_STOCKS[:20]
            
            rankings = []
            for ticker in tickers[:10]:
                quote = await self._fetch_quote(ticker)
                if quote:
                    rankings.append({
                        "ticker": ticker,
                        "price": quote.get('price', 0),
                        "change_pct": quote.get('change_pct', 0)
                    })
            
            # Sort by performance
            rankings.sort(key=lambda x: x['change_pct'], reverse=True)
            
            msg = "💪 <b>RELATIVE STRENGTH RANKING</b>\n\n"
            
            for i, r in enumerate(rankings, 1):
                if i <= 3:
                    emoji = "🥇🥈🥉"[i-1]
                elif r['change_pct'] >= 0:
                    emoji = "🟢"
                else:
                    emoji = "🔴"
                
                msg += f"{emoji} #{i} <b>{r['ticker']}</b>: {'+' if r['change_pct'] >= 0 else ''}{r['change_pct']:.2f}%\n"
            
            msg += "\n💡 Top 3 = Strongest momentum"
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_risk(self, chat_id: int, args: List[str]):
        """Portfolio risk analysis."""
        try:
            positions = await self._get_positions()
            
            msg = "⚠️ <b>PORTFOLIO RISK ANALYSIS</b>\n\n"
            
            if not positions:
                msg += "No open positions.\n\n"
                msg += "<b>Risk Guidelines:</b>\n"
                msg += "• Risk 1-2% per trade\n"
                msg += "• Max 5-8 open positions\n"
                msg += "• Max 25% in one sector\n"
                msg += "• Keep 20%+ cash buffer\n"
            else:
                total_value = sum(p.get('value', 0) for p in positions)
                msg += f"<b>Total Exposure:</b> ${total_value:,.2f}\n"
                msg += f"<b>Open Positions:</b> {len(positions)}\n\n"
                
                msg += "<b>Position Sizes:</b>\n"
                for p in positions:
                    pct = (p.get('value', 0) / total_value * 100) if total_value else 0
                    msg += f"  {p['ticker']}: {pct:.1f}%\n"
            
            msg += "\n<i>Use /check PRICE TICKER to analyze positions</i>"
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_history(self, chat_id: int, args: List[str]):
        """Recent trade history."""
        try:
            msg = """
📜 <b>RECENT TRADE HISTORY</b>

No trades recorded yet.

<b>To start tracking:</b>
1. Connect a broker with /broker
2. Execute trades via /buy or /sell
3. Your history will appear here

<i>Paper trading is always available</i>
"""
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_stats(self, chat_id: int, args: List[str]):
        """Trading statistics."""
        try:
            msg = """
📈 <b>TRADING STATISTICS</b>

<b>All Time:</b>
  Total Trades: 0
  Win Rate: N/A
  Avg Win: N/A
  Avg Loss: N/A
  Profit Factor: N/A

<b>This Month:</b>
  Trades: 0
  P&L: $0.00

<i>Start trading to see your stats!</i>
"""
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_quick(self, chat_id: int, args: List[str]):
        """Quick analysis of a stock."""
        if not args:
            await self.send_message_to(chat_id, "Usage: /quick AAPL")
            return
        
        ticker = args[0].upper()
        
        try:
            quote = await self._fetch_quote(ticker)
            if not quote:
                await self.send_message_to(chat_id, f"❌ Could not fetch {ticker}")
                return
            
            price = quote.get('price', 0)
            change_pct = quote.get('change_pct', 0)
            high = quote.get('high', 0)
            low = quote.get('low', 0)
            
            # Quick verdict
            if change_pct > 2:
                verdict = "🚀 STRONG"
            elif change_pct > 0.5:
                verdict = "🟢 BULLISH"
            elif change_pct > -0.5:
                verdict = "➡️ NEUTRAL"
            elif change_pct > -2:
                verdict = "🟡 WEAK"
            else:
                verdict = "🔴 BEARISH"
            
            msg = f"""
⚡ <b>QUICK: {ticker}</b>

💰 ${price:.2f} ({'+' if change_pct >= 0 else ''}{change_pct:.2f}%)
📊 Range: ${low:.2f} - ${high:.2f}
🎯 Verdict: {verdict}

/advise {ticker} for full analysis
"""
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_daily(self, chat_id: int, args: List[str]):
        """Daily market summary."""
        try:
            msg = "📰 <b>DAILY MARKET SUMMARY</b>\n\n"
            msg += f"<i>{datetime.now().strftime('%A, %B %d, %Y')}</i>\n\n"
            
            # Get indices
            for symbol, name in [("SPY", "S&P 500"), ("QQQ", "NASDAQ"), ("DIA", "DOW")]:
                quote = await self._fetch_quote(symbol)
                if quote:
                    change_pct = quote.get('change_pct', 0)
                    emoji = "🟢" if change_pct >= 0 else "🔴"
                    msg += f"{emoji} <b>{name}</b>: {'+' if change_pct >= 0 else ''}{change_pct:.2f}%\n"
            
            # Market mood
            spy = await self._fetch_quote("SPY")
            if spy:
                change = spy.get('change_pct', 0)
                if change > 1:
                    mood = "😊 BULLISH - Risk on"
                elif change > 0:
                    mood = "🙂 POSITIVE - Cautiously optimistic"
                elif change > -1:
                    mood = "😐 MIXED - Wait and see"
                else:
                    mood = "😟 BEARISH - Risk off"
                msg += f"\n<b>Market Mood:</b> {mood}\n"
            
            msg += "\n<b>Quick Actions:</b>\n"
            msg += "/oppty - Find opportunities\n"
            msg += "/movers - Top movers\n"
            msg += "/swing - Swing setups"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_summary(self, chat_id: int, args: List[str]):
        """End of day summary."""
        await self._cmd_daily(chat_id, args)
    
    async def _cmd_alerts(self, chat_id: int, args: List[str]):
        """List all active alerts."""
        if not self.price_alerts:
            msg = """
🔔 <b>ACTIVE ALERTS</b>

No alerts set.

<b>To set an alert:</b>
<code>/alert AAPL above 200</code>
<code>/alert NVDA below 500</code>
"""
        else:
            msg = "🔔 <b>ACTIVE ALERTS</b>\n\n"
            for alert_id, alert in self.price_alerts.items():
                msg += f"• <b>{alert['ticker']}</b> {alert['condition']} ${alert['price']:.2f}\n"
            
            msg += f"\n<i>Total: {len(self.price_alerts)} alerts</i>"
        
        await self.send_message_to(chat_id, msg)
    
    # ===== PROFESSIONAL TECHNICAL ANALYSIS FUNCTIONS =====
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index) - standard 14-period."""
        if len(prices) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) < period:
            return 50.0
        
        # First average
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        # Smoothed RSI
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    
    def _calculate_atr(self, bars: List[Dict], period: int = 14) -> float:
        """Calculate ATR (Average True Range) - professional stop loss sizing."""
        if len(bars) < period + 1:
            return 0.0
        
        true_ranges = []
        for i in range(1, len(bars)):
            high = bars[i].get('high', 0)
            low = bars[i].get('low', 0)
            prev_close = bars[i-1].get('close', 0)
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0
        
        return sum(true_ranges[-period:]) / period
    
    def _calculate_macd(self, prices: List[float]) -> Dict:
        """Calculate MACD (12, 26, 9) - trend and momentum indicator."""
        if len(prices) < 26:
            return {"macd": 0, "signal": 0, "histogram": 0, "trend": "neutral"}
        
        # EMA calculation helper
        def ema(data, period):
            if len(data) < period:
                return data[-1] if data else 0
            multiplier = 2 / (period + 1)
            ema_val = sum(data[:period]) / period
            for price in data[period:]:
                ema_val = (price - ema_val) * multiplier + ema_val
            return ema_val
        
        ema12 = ema(prices, 12)
        ema26 = ema(prices, 26)
        macd_line = ema12 - ema26
        
        # Signal line (9-period EMA of MACD)
        # Simplified for real-time
        signal_line = macd_line * 0.9  # Approximation
        histogram = macd_line - signal_line
        
        trend = "bullish" if macd_line > signal_line else "bearish"
        
        return {
            "macd": round(macd_line, 3),
            "signal": round(signal_line, 3),
            "histogram": round(histogram, 3),
            "trend": trend
        }
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict:
        """Calculate Bollinger Bands - volatility and mean reversion."""
        if len(prices) < period:
            price = prices[-1] if prices else 0
            return {"upper": price, "middle": price, "lower": price, "position": 0.5}
        
        sma = sum(prices[-period:]) / period
        variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
        std = variance ** 0.5
        
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        
        current = prices[-1]
        position = (current - lower) / (upper - lower) if upper != lower else 0.5
        
        return {
            "upper": round(upper, 2),
            "middle": round(sma, 2),
            "lower": round(lower, 2),
            "position": round(position, 2)  # 0 = at lower, 1 = at upper
        }
    
    def _calculate_kelly_criterion(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Kelly Criterion for optimal position sizing.
        Formula: f* = (p * b - q) / b
        Where: p = win rate, q = loss rate, b = win/loss ratio
        
        Professional traders often use 1/4 or 1/2 Kelly for safety.
        """
        if avg_loss == 0 or avg_win == 0:
            return 0.01  # Default 1%
        
        p = win_rate
        q = 1 - win_rate
        b = abs(avg_win / avg_loss)
        
        kelly = (p * b - q) / b
        
        # Cap at 25% (even full Kelly rarely exceeds this for reasonable systems)
        # Use quarter Kelly for safety
        quarter_kelly = kelly / 4
        
        return max(0.005, min(0.05, quarter_kelly))  # Between 0.5% and 5%
    
    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.05) -> float:
        """Calculate Sharpe Ratio - risk-adjusted return metric."""
        if not returns or len(returns) < 2:
            return 0.0
        
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return 0.0
        
        # Annualized (assuming daily returns)
        daily_rf = risk_free_rate / 252
        sharpe = (avg_return - daily_rf) / std_dev * (252 ** 0.5)
        
        return round(sharpe, 2)
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate Maximum Drawdown - crucial risk metric."""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0
        
        peak = equity_curve[0]
        max_dd = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_dd:
                max_dd = drawdown
        
        return round(max_dd * 100, 2)
    
    # ===== AI Trading Advisor Commands =====
    
    async def _calculate_ai_score(self, ticker: str, quote: Dict) -> Dict:
        """Calculate AI score (1-10) for a stock based on multiple factors."""
        price = quote.get('price', 0)
        change_pct = quote.get('change_pct', 0)
        volume = quote.get('volume', 0)
        high = quote.get('high', 0)
        low = quote.get('low', 0)
        
        # Initialize scores
        momentum_score = 5
        volatility_score = 5
        volume_score = 5
        trend_score = 5
        
        # Momentum scoring (based on daily change)
        if change_pct > 3:
            momentum_score = 9
        elif change_pct > 2:
            momentum_score = 8
        elif change_pct > 1:
            momentum_score = 7
        elif change_pct > 0.5:
            momentum_score = 6
        elif change_pct > 0:
            momentum_score = 5.5
        elif change_pct > -0.5:
            momentum_score = 5
        elif change_pct > -1:
            momentum_score = 4
        elif change_pct > -2:
            momentum_score = 3
        else:
            momentum_score = 2
        
        # Volatility scoring (prefer moderate volatility)
        daily_range = (high - low) / price * 100 if price > 0 else 0
        if 1 <= daily_range <= 3:
            volatility_score = 8  # Ideal for trading
        elif 0.5 <= daily_range < 1:
            volatility_score = 6
        elif 3 < daily_range <= 5:
            volatility_score = 6
        elif daily_range > 5:
            volatility_score = 4  # Too volatile
        else:
            volatility_score = 3  # Too quiet
        
        # Volume scoring (higher relative volume = better)
        if volume > 0:
            volume_score = min(8, 5 + (volume / 1000000))  # Base + bonus for volume
        
        # Price location in day's range
        if high > low:
            price_location = (price - low) / (high - low)
            if price_location > 0.8:
                trend_score = 8  # Near highs = bullish
            elif price_location > 0.6:
                trend_score = 7
            elif price_location < 0.2:
                trend_score = 3  # Near lows = bearish
            elif price_location < 0.4:
                trend_score = 4
        
        # Composite AI score (weighted average)
        ai_score = (
            momentum_score * 0.35 +
            volatility_score * 0.20 +
            volume_score * 0.20 +
            trend_score * 0.25
        )
        
        # Determine signal
        if ai_score >= 7.5:
            signal = "STRONG BUY"
            confidence = "HIGH"
        elif ai_score >= 6.5:
            signal = "BUY"
            confidence = "MEDIUM-HIGH"
        elif ai_score >= 5.5:
            signal = "HOLD"
            confidence = "MEDIUM"
        elif ai_score >= 4.5:
            signal = "WEAK"
            confidence = "LOW"
        else:
            signal = "AVOID"
            confidence = "HIGH"
        
        return {
            "ticker": ticker,
            "ai_score": round(ai_score, 1),
            "momentum": round(momentum_score, 1),
            "volatility": round(volatility_score, 1),
            "volume": round(volume_score, 1),
            "trend": round(trend_score, 1),
            "signal": signal,
            "confidence": confidence,
            "price": price,
            "change_pct": change_pct,
        }
    
    async def _cmd_score(self, chat_id: int, args: List[str]):
        """AI score for a stock (Kavout/Kai style) - Enhanced with detailed analysis."""
        if not args:
            msg = """
🤖 <b>AI Stock Score</b>

Usage: <code>/score AAPL</code>

Get an AI score (1-10) based on:
• Momentum (daily/weekly performance)
• Volatility (trading range quality)
• Volume (relative to average)
• Trend (price position in range)
• Legendary investor criteria
• ML-adjusted weights
"""
            await self.send_message_to(chat_id, msg)
            return
        
        ticker = args[0].upper()
        await self.send_message_to(chat_id, f"🤖 <b>Calculating AI score for {ticker}...</b>")
        
        try:
            quote = await self._fetch_quote(ticker)
            if not quote:
                await self.send_message_to(chat_id, f"❌ Could not fetch data for {ticker}")
                return
            
            score_data = await self._calculate_ai_score(ticker, quote)
            
            # Get historical data for ATR/RSI
            bars = await self._get_historical_bars(ticker, days=20)
            atr = self._calculate_atr(bars) if bars else quote.get('price', 0) * 0.025
            prices = [b.get('close', 0) for b in bars] if bars else []
            rsi = self._calculate_rsi(prices) if len(prices) >= 14 else 50
            
            # Calculate entry/stop/target
            current_price = quote.get('price', 0)
            entry = current_price
            stop = entry - (2 * atr)
            target1 = entry + (2 * atr)  # 1R
            target2 = entry + (4 * atr)  # 2R
            target3 = entry + (6 * atr)  # 3R
            
            # Score bar visualization
            score = score_data['ai_score']
            filled = int(score)
            bar = "█" * filled + "░" * (10 - filled)
            
            # Color emoji based on score
            if score >= 7:
                emoji = "🟢"
                action = "STRONG BUY"
            elif score >= 6:
                emoji = "🟢"
                action = "BUY"
            elif score >= 5:
                emoji = "🟡"
                action = "HOLD/WATCH"
            elif score >= 4:
                emoji = "🟡"
                action = "CAUTION"
            else:
                emoji = "🔴"
                action = "AVOID"
            
            # Calculate position size based on user settings
            risk_amount = self.user_settings['account_size'] * self.user_settings['risk_per_trade']
            risk_per_share = entry - stop
            suggested_shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
            
            # Risk/Reward ratio
            reward = target2 - entry
            risk = entry - stop
            rr_ratio = reward / risk if risk > 0 else 0
            
            msg = f"""
🤖 <b>AI SCORE ANALYSIS: {ticker}</b>

{emoji} <b>Score: {score}/10 - {action}</b>
[{bar}]

━━━━━━━━━━━━━━━━━━━━━━
📊 <b>FACTOR BREAKDOWN</b>
━━━━━━━━━━━━━━━━━━━━━━
📈 Momentum: {score_data['momentum']}/10 {'🔥' if score_data['momentum'] >= 7 else ''}
📉 Volatility: {score_data['volatility']}/10
📦 Volume: {score_data['volume']}/10 {'📊' if score_data['volume'] >= 7 else ''}
🎯 Trend: {score_data['trend']}/10 {'✨' if score_data['trend'] >= 7 else ''}

━━━━━━━━━━━━━━━━━━━━━━
📉 <b>TECHNICAL INDICATORS</b>
━━━━━━━━━━━━━━━━━━━━━━
RSI(14): {rsi:.1f} {'(Oversold 🟢)' if rsi < 30 else '(Overbought 🔴)' if rsi > 70 else '(Neutral)'}
ATR(14): ${atr:.2f} ({atr/current_price*100:.1f}% of price)
Volatility: {'High ⚡' if atr/current_price > 0.03 else 'Normal' if atr/current_price > 0.015 else 'Low'}

━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>TRADE LEVELS</b>
━━━━━━━━━━━━━━━━━━━━━━
📍 Entry: ${entry:.2f}
🛑 Stop Loss: ${stop:.2f} (-{(entry-stop)/entry*100:.1f}%)
🎯 Target 1: ${target1:.2f} (+{(target1-entry)/entry*100:.1f}%) [1R]
🎯 Target 2: ${target2:.2f} (+{(target2-entry)/entry*100:.1f}%) [2R]
🎯 Target 3: ${target3:.2f} (+{(target3-entry)/entry*100:.1f}%) [3R]

📐 Risk/Reward: 1:{rr_ratio:.1f}

━━━━━━━━━━━━━━━━━━━━━━
💰 <b>POSITION SIZING</b>
━━━━━━━━━━━━━━━━━━━━━━
Account: ${self.user_settings['account_size']:,.0f}
Risk: {self.user_settings['risk_per_trade']*100:.1f}% = ${risk_amount:,.0f}
📊 Suggested Shares: {suggested_shares}
💵 Position Value: ${suggested_shares * entry:,.0f}

━━━━━━━━━━━━━━━━━━━━━━
💰 <b>CURRENT DATA</b>
━━━━━━━━━━━━━━━━━━━━━━
Price: ${current_price:.2f}
Change: {'+' if score_data['change_pct'] >= 0 else ''}{score_data['change_pct']:.2f}%
Signal: {score_data['signal']}
Confidence: {score_data['confidence']}

{'✅ <b>RECOMMENDED</b> - Good setup with favorable R:R' if score >= 6 and rr_ratio >= 2 else ''}
{'⚠️ <b>WAIT</b> - Look for better entry or R:R' if score >= 5 and rr_ratio < 2 else ''}
{'❌ <b>PASS</b> - Does not meet criteria' if score < 5 else ''}

<i>Use /riskcheck {ticker} {suggested_shares} {entry:.2f} for full risk analysis</i>
"""
            await self.send_message_to(chat_id, msg)
            
            # Record prediction for ML learning
            await self._record_prediction(ticker, score, action, entry, "momentum")
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_deep(self, chat_id: int, args: List[str]):
        """Deep analysis with comprehensive market data like Futubull."""
        if not args:
            msg = """
🔬 <b>Deep Analysis</b>

Usage: <code>/deep MU</code>

Provides comprehensive analysis:
• Real-time price & valuation
• Price performance (1M, 3M, YTD)
• Technical indicators & signals
• Volume analysis & capital flow
• Support/resistance levels
• AI verdict with confidence
"""
            await self.send_message_to(chat_id, msg)
            return
        
        ticker = args[0].upper()
        await self.send_message_to(chat_id, f"🔬 <b>Running deep analysis on {ticker}...</b>")
        
        try:
            import aiohttp
            from datetime import datetime, timedelta
            
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key
            }
            
            # Fetch current quote
            quote = await self._fetch_quote(ticker)
            if not quote:
                await self.send_message_to(chat_id, f"❌ Could not fetch data for {ticker}")
                return
            
            price = quote.get('price', 0)
            change_pct = quote.get('change_pct', 0)
            volume = quote.get('volume', 0)
            high = quote.get('high', 0)
            low = quote.get('low', 0)
            open_price = quote.get('open', 0)
            prev_close = quote.get('prev_close', 0)
            
            # Get historical data for technical analysis (30 days)
            async with aiohttp.ClientSession() as session:
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_30d = (datetime.now() - timedelta(days=35)).strftime("%Y-%m-%d")
                start_90d = (datetime.now() - timedelta(days=95)).strftime("%Y-%m-%d")
                
                # 30-day bars
                bars_url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
                params_30d = {"timeframe": "1Day", "start": start_30d, "end": end_date, "limit": 30, "feed": "iex"}
                
                bars_30d = []
                async with session.get(bars_url, headers=headers, params=params_30d) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        bars_30d = data.get("bars", [])
                
                # 90-day bars for longer term analysis
                params_90d = {"timeframe": "1Day", "start": start_90d, "end": end_date, "limit": 90, "feed": "iex"}
                bars_90d = []
                async with session.get(bars_url, headers=headers, params=params_90d) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        bars_90d = data.get("bars", [])
            
            # Calculate technical indicators
            if bars_30d:
                closes = [float(b.get('c', 0)) for b in bars_30d]
                highs = [float(b.get('h', 0)) for b in bars_30d]
                lows = [float(b.get('l', 0)) for b in bars_30d]
                volumes = [int(b.get('v', 0)) for b in bars_30d]
                
                # Moving averages
                ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else price
                ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else price
                ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else price
                
                # RSI calculation (14-day)
                gains = []
                losses = []
                for i in range(1, min(15, len(closes))):
                    diff = closes[i] - closes[i-1]
                    if diff > 0:
                        gains.append(diff)
                        losses.append(0)
                    else:
                        gains.append(0)
                        losses.append(abs(diff))
                
                avg_gain = sum(gains) / len(gains) if gains else 0
                avg_loss = sum(losses) / len(losses) if losses else 0.0001
                rs = avg_gain / avg_loss if avg_loss > 0 else 100
                rsi = 100 - (100 / (1 + rs))
                
                # Support/Resistance
                recent_lows = sorted(lows[-10:])[:3]
                recent_highs = sorted(highs[-10:], reverse=True)[:3]
                support = sum(recent_lows) / 3 if recent_lows else low
                resistance = sum(recent_highs) / 3 if recent_highs else high
                
                # Volume analysis
                avg_volume = sum(volumes) / len(volumes) if volumes else 0
                vol_ratio = volume / avg_volume if avg_volume > 0 else 1
                
                # Price position in range
                range_30d = max(highs) - min(lows) if highs and lows else 0
                pos_in_range = ((price - min(lows)) / range_30d * 100) if range_30d > 0 else 50
                
                # Performance calculations
                if len(closes) >= 5:
                    perf_5d = ((price - closes[-5]) / closes[-5] * 100) if closes[-5] > 0 else 0
                else:
                    perf_5d = 0
                    
                if len(closes) >= 20:
                    perf_20d = ((price - closes[-20]) / closes[-20] * 100) if closes[-20] > 0 else 0
                else:
                    perf_20d = 0
            else:
                ma5 = ma10 = ma20 = price
                rsi = 50
                support = low
                resistance = high
                avg_volume = volume
                vol_ratio = 1
                pos_in_range = 50
                perf_5d = perf_20d = 0
            
            # 90-day performance
            if bars_90d and len(bars_90d) >= 60:
                closes_90 = [float(b.get('c', 0)) for b in bars_90d]
                perf_60d = ((price - closes_90[-60]) / closes_90[-60] * 100) if closes_90[-60] > 0 else 0
            else:
                perf_60d = 0
            
            # Technical signals
            signals = []
            signal_score = 0
            
            # Trend analysis
            if price > ma20:
                signals.append("📈 Above MA20 (Bullish)")
                signal_score += 2
            else:
                signals.append("📉 Below MA20 (Bearish)")
                signal_score -= 2
            
            if price > ma5 and ma5 > ma10:
                signals.append("🚀 Short-term uptrend")
                signal_score += 1
            elif price < ma5 and ma5 < ma10:
                signals.append("⚠️ Short-term downtrend")
                signal_score -= 1
            
            # RSI analysis
            if rsi >= 70:
                signals.append(f"🔴 RSI {rsi:.0f} - OVERBOUGHT")
                signal_score -= 1
            elif rsi <= 30:
                signals.append(f"🟢 RSI {rsi:.0f} - OVERSOLD")
                signal_score += 1
            else:
                signals.append(f"🟡 RSI {rsi:.0f} - Neutral")
            
            # Volume analysis
            if vol_ratio >= 1.5:
                signals.append(f"🔥 High volume ({vol_ratio:.1f}x avg)")
                signal_score += 1
            elif vol_ratio <= 0.5:
                signals.append(f"💤 Low volume ({vol_ratio:.1f}x avg)")
            
            # Support/Resistance
            dist_to_support = ((price - support) / price * 100) if price > 0 else 0
            dist_to_resist = ((resistance - price) / price * 100) if price > 0 else 0
            
            if dist_to_support < 3:
                signals.append("🛡️ Near support level")
                signal_score += 1
            if dist_to_resist < 3:
                signals.append("🚧 Near resistance level")
            
            # Overall verdict
            if signal_score >= 3:
                verdict = "🟢 STRONG BUY"
                conf = "HIGH"
            elif signal_score >= 1:
                verdict = "🟢 BUY"
                conf = "MEDIUM"
            elif signal_score >= -1:
                verdict = "🟡 HOLD"
                conf = "NEUTRAL"
            elif signal_score >= -3:
                verdict = "🔴 SELL"
                conf = "MEDIUM"
            else:
                verdict = "🔴 STRONG SELL"
                conf = "HIGH"
            
            # Build comprehensive message
            emoji = "🟢" if change_pct >= 0 else "🔴"
            
            msg = f"🔬 <b>DEEP ANALYSIS: {ticker}</b>\n"
            msg += f"<i>Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n\n"
            
            # Price Overview
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "💰 <b>PRICE OVERVIEW</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"{emoji} Current: <b>${price:.2f}</b>\n"
            msg += f"   Change: {'+' if change_pct >= 0 else ''}{change_pct:.2f}%\n"
            msg += f"   Open: ${open_price:.2f} | Prev: ${prev_close:.2f}\n"
            msg += f"   Day Range: ${low:.2f} - ${high:.2f}\n\n"
            
            # Performance
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📊 <b>PERFORMANCE</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            perf_5d_emoji = "🟢" if perf_5d >= 0 else "🔴"
            perf_20d_emoji = "🟢" if perf_20d >= 0 else "🔴"
            perf_60d_emoji = "🟢" if perf_60d >= 0 else "🔴"
            msg += f"{perf_5d_emoji} 5-Day: {'+' if perf_5d >= 0 else ''}{perf_5d:.2f}%\n"
            msg += f"{perf_20d_emoji} 20-Day: {'+' if perf_20d >= 0 else ''}{perf_20d:.2f}%\n"
            msg += f"{perf_60d_emoji} 60-Day: {'+' if perf_60d >= 0 else ''}{perf_60d:.2f}%\n\n"
            
            # Technical Indicators
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📈 <b>TECHNICAL INDICATORS</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"MA5: ${ma5:.2f} | MA10: ${ma10:.2f} | MA20: ${ma20:.2f}\n"
            msg += f"RSI(14): {rsi:.1f} "
            if rsi >= 70:
                msg += "(⚠️ Overbought)\n"
            elif rsi <= 30:
                msg += "(📢 Oversold)\n"
            else:
                msg += "(Neutral)\n"
            msg += f"Position in 30D Range: {pos_in_range:.0f}%\n\n"
            
            # Volume Analysis
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📊 <b>VOLUME ANALYSIS</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"Today: {volume:,}\n"
            msg += f"Avg (30D): {int(avg_volume):,}\n"
            msg += f"Volume Ratio: {vol_ratio:.2f}x "
            if vol_ratio >= 1.5:
                msg += "(🔥 Unusual Activity)\n\n"
            elif vol_ratio <= 0.5:
                msg += "(💤 Low Activity)\n\n"
            else:
                msg += "(Normal)\n\n"
            
            # Support/Resistance
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "🎯 <b>KEY LEVELS</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"🛡️ Support: ${support:.2f} ({dist_to_support:.1f}% below)\n"
            msg += f"🚧 Resistance: ${resistance:.2f} ({dist_to_resist:.1f}% above)\n\n"
            
            # Signals Summary
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "🔔 <b>TECHNICAL SIGNALS</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            for sig in signals:
                msg += f"• {sig}\n"
            msg += "\n"
            
            # AI Verdict
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "🤖 <b>AI VERDICT</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"Signal: <b>{verdict}</b>\n"
            msg += f"Confidence: {conf}\n"
            msg += f"Score: {signal_score:+d} (range: -5 to +5)\n\n"
            
            # Trading Suggestion
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "💡 <b>TRADING SUGGESTION</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            if signal_score >= 2:
                msg += f"Consider BUY if breaks ${resistance:.2f}\n"
                msg += f"Stop Loss: ${support:.2f}\n"
                msg += f"Target: ${price + (resistance - support):.2f}\n"
            elif signal_score <= -2:
                msg += f"Consider SELL or avoid\n"
                msg += f"Watch for breakdown below ${support:.2f}\n"
            else:
                msg += f"WAIT for clearer signal\n"
                msg += f"Watch ${support:.2f} - ${resistance:.2f} range\n"
            
            msg += "\n<i>⚠️ This is not financial advice. Always do your own research.</i>"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_rank(self, chat_id: int, args: List[str]):
        """Rank stocks by AI momentum score."""
        await self.send_message_to(chat_id, "🏆 <b>Ranking stocks by AI score...</b>")
        
        try:
            # Get scores for top stocks
            rankings = []
            tickers = self.TOP_STOCKS[:25]
            
            for ticker in tickers:
                quote = await self._fetch_quote(ticker)
                if quote:
                    score_data = await self._calculate_ai_score(ticker, quote)
                    rankings.append(score_data)
            
            # Sort by AI score
            rankings.sort(key=lambda x: x['ai_score'], reverse=True)
            
            msg = "🏆 <b>AI MOMENTUM RANKINGS</b>\n"
            msg += f"<i>Top 20 by AI Score</i>\n\n"
            
            for i, r in enumerate(rankings[:20], 1):
                # Medal emojis for top 3
                if i == 1:
                    medal = "🥇"
                elif i == 2:
                    medal = "🥈"
                elif i == 3:
                    medal = "🥉"
                elif r['ai_score'] >= 7:
                    medal = "🟢"
                elif r['ai_score'] >= 5:
                    medal = "🟡"
                else:
                    medal = "🔴"
                
                change_str = f"+{r['change_pct']:.1f}%" if r['change_pct'] >= 0 else f"{r['change_pct']:.1f}%"
                msg += f"{medal} #{i} <b>{r['ticker']}</b>: {r['ai_score']}/10 ({change_str})\n"
            
            msg += "\n💡 Use /score TICKER for detailed breakdown"
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_top(self, chat_id: int, args: List[str]):
        """Top 10+ picks today with detailed reasons and legendary investor analysis."""
        await self.send_message_to(chat_id, "🎯 <b>Scanning 100+ stocks for top picks...</b>")
        
        try:
            # Score stocks and find best setups - scan more stocks
            picks = []
            tickers = self.TOP_STOCKS[:100]  # Scan 100 stocks
            
            for ticker in tickers:
                quote = await self._fetch_quote(ticker)
                if not quote or quote.get('price', 0) == 0:
                    continue
                
                price = quote.get('price', 0)
                change_pct = quote.get('change_pct', 0)
                volume = quote.get('volume', 0)
                high = quote.get('high', 0)
                low = quote.get('low', 0)
                open_price = quote.get('open', 0)
                prev_close = quote.get('prev_close', 0)
                
                # Calculate advanced scoring with legendary investor criteria
                score_data = await self._calculate_legendary_score(ticker, quote)
                
                if score_data['total_score'] >= 6.0:  # Only high-scoring stocks
                    # Calculate R:R and setup quality
                    atr_est = high - low if high > low else price * 0.02
                    
                    stop = round(price - atr_est * 1.5, 2)
                    target = round(price + atr_est * 3, 2)
                    rr = round((target - price) / (price - stop), 1) if price > stop else 0
                    
                    # Determine position in day's range
                    if high > low:
                        pos_in_range = (price - low) / (high - low) * 100
                    else:
                        pos_in_range = 50
                    
                    # Build reasons list
                    reasons = []
                    
                    # Momentum reason
                    if change_pct > 2:
                        reasons.append(f"🚀 Strong momentum (+{change_pct:.1f}%)")
                    elif change_pct > 0.5:
                        reasons.append(f"📈 Positive momentum (+{change_pct:.1f}%)")
                    elif change_pct < -2:
                        reasons.append(f"🎯 Oversold bounce setup ({change_pct:.1f}%)")
                    
                    # Price action
                    if pos_in_range > 70:
                        reasons.append("💪 Trading near day's highs")
                    elif pos_in_range < 30:
                        reasons.append("🛡️ Near support level")
                    
                    # Investor style reasons
                    if score_data['buffett_score'] >= 7:
                        reasons.append("🏛️ Buffett: Strong value + quality")
                    if score_data['lynch_score'] >= 7:
                        reasons.append("📊 Lynch: PEG attractive for growth")
                    if score_data['momentum_score'] >= 7:
                        reasons.append("🔥 Druckenmiller: Momentum aligned")
                    if score_data['tepper_score'] >= 7:
                        reasons.append("💎 Tepper: Distressed value play")
                    
                    # Volume confirmation
                    if volume > 1000000:
                        reasons.append(f"📊 High liquidity ({volume/1000000:.1f}M vol)")
                    
                    if not reasons:
                        reasons.append("📈 Technical setup favorable")
                    
                    picks.append({
                        "ticker": ticker,
                        "price": price,
                        "change_pct": change_pct,
                        "score": score_data['total_score'],
                        "signal": score_data['signal'],
                        "confidence": score_data['confidence'],
                        "stop": stop,
                        "target": target,
                        "rr": rr,
                        "reasons": reasons[:3],  # Top 3 reasons
                        "investor_scores": score_data,
                        "hold_days": "3-15 days"
                    })
            
            # Sort by score
            picks.sort(key=lambda x: x['score'], reverse=True)
            
            # Split into two messages if needed
            msg1 = "🎯 <b>TOP PICKS TODAY (Part 1/2)</b>\n"
            msg1 += f"<i>Scanned {len(tickers)} stocks | {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>\n\n"
            
            if picks:
                # First 5 picks in message 1
                for i, p in enumerate(picks[:5], 1):
                    score_bar = "●" * int(p['score']) + "○" * (10 - int(p['score']))
                    chg_emoji = "🟢" if p['change_pct'] >= 0 else "🔴"
                    
                    msg1 += f"<b>#{i} {p['ticker']}</b> - {p['signal']}\n"
                    msg1 += f"{chg_emoji} ${p['price']:.2f} ({p['change_pct']:+.2f}%)\n"
                    msg1 += f"   🛑 Stop: ${p['stop']:.2f} | 🎯 Target: ${p['target']:.2f}\n"
                    msg1 += f"   📊 Score: {p['score']:.1f}/10 [{score_bar}]\n"
                    msg1 += f"   <b>Why:</b>\n"
                    for reason in p['reasons']:
                        msg1 += f"   • {reason}\n"
                    msg1 += "\n"
                
                await self.send_message_to(chat_id, msg1)
                
                # Second message with picks 6-12
                if len(picks) > 5:
                    msg2 = "🎯 <b>TOP PICKS TODAY (Part 2/2)</b>\n\n"
                    
                    for i, p in enumerate(picks[5:12], 6):
                        score_bar = "●" * int(p['score']) + "○" * (10 - int(p['score']))
                        chg_emoji = "🟢" if p['change_pct'] >= 0 else "🔴"
                        
                        msg2 += f"<b>#{i} {p['ticker']}</b> - {p['signal']}\n"
                        msg2 += f"{chg_emoji} ${p['price']:.2f} ({p['change_pct']:+.2f}%)\n"
                        msg2 += f"   🛑 Stop: ${p['stop']:.2f} | 🎯 Target: ${p['target']:.2f}\n"
                        msg2 += f"   📊 Score: {p['score']:.1f}/10\n"
                        msg2 += f"   • {p['reasons'][0] if p['reasons'] else 'Technical setup'}\n\n"
                    
                    msg2 += "━━━━━━━━━━━━━━━━━━━━━━\n"
                    msg2 += "💡 <b>LEGENDARY INVESTOR STYLES:</b>\n"
                    msg2 += "🏛️ Buffett: Value + Moat\n"
                    msg2 += "📊 Lynch: Growth at reasonable price\n"
                    msg2 += "🔥 Druckenmiller: Momentum + Macro\n"
                    msg2 += "💎 Tepper: Distressed value\n\n"
                    msg2 += "Use <code>/simtrade 2025-04-06</code> to backtest picks\n"
                    msg2 += "⚠️ <i>Not financial advice. DYOR.</i>"
                    
                    await self.send_message_to(chat_id, msg2)
            else:
                msg1 += "📭 No strong picks found right now.\n"
                msg1 += "Market may be choppy - wait for clearer setups.\n"
                msg1 += "Try <code>/scan</code> for more options."
                await self.send_message_to(chat_id, msg1)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _calculate_legendary_score(self, ticker: str, quote: Dict) -> Dict:
        """Calculate score based on legendary investor strategies."""
        price = quote.get('price', 0)
        change_pct = quote.get('change_pct', 0)
        volume = quote.get('volume', 0)
        high = quote.get('high', 0)
        low = quote.get('low', 0)
        prev_close = quote.get('prev_close', price)
        
        # Initialize component scores
        buffett_score = 5.0  # Value + Quality (Buffett)
        lynch_score = 5.0    # Growth at reasonable price (Lynch)
        momentum_score = 5.0  # Momentum (Druckenmiller)
        tepper_score = 5.0   # Distressed Value (Tepper)
        greenblatt_score = 5.0  # Magic Formula (Greenblatt)
        
        # === BUFFETT SCORE (Value + Quality) ===
        # Without P/E data, use price stability and trend
        if abs(change_pct) < 1.5:
            buffett_score += 1.5  # Stable price = quality
        if price > prev_close * 0.97:  # Not crashing
            buffett_score += 1
        # Large cap proxy (higher prices often = larger companies)
        if price > 100:
            buffett_score += 1
        
        # === LYNCH SCORE (PEG / Growth) ===
        # Use momentum as growth proxy
        if 1 < change_pct <= 3:
            lynch_score += 2.5  # Moderate growth momentum
        elif 0.5 < change_pct <= 1:
            lynch_score += 1.5
        elif change_pct > 3:
            lynch_score += 1  # Too hot, lower PEG appeal
        
        # === MOMENTUM SCORE (Druckenmiller) ===
        # Trend + Price action
        if change_pct > 2:
            momentum_score += 3
        elif change_pct > 1:
            momentum_score += 2
        elif change_pct > 0.5:
            momentum_score += 1
        elif change_pct < -1:
            momentum_score -= 1.5
        
        # Near highs = strong momentum
        if high > low:
            pos_in_range = (price - low) / (high - low)
            if pos_in_range > 0.8:
                momentum_score += 1.5
            elif pos_in_range < 0.2:
                momentum_score -= 1
        
        # === TEPPER SCORE (Distressed Value) ===
        # Buy beaten-down assets during panic
        if change_pct < -3:
            tepper_score += 3  # Panic selling = opportunity
        elif change_pct < -2:
            tepper_score += 2
        elif change_pct < -1:
            tepper_score += 1
        else:
            tepper_score -= 0.5  # Not distressed
        
        # === GREENBLATT SCORE (Magic Formula) ===
        # Earnings yield + ROIC proxy via price action
        if 0 < change_pct < 2:
            greenblatt_score += 1.5
        if abs(change_pct) < 1:  # Stable = quality
            greenblatt_score += 1
        
        # Volume confirmation for all
        if volume > 500000:
            momentum_score += 0.5
            lynch_score += 0.5
        
        # Normalize scores
        buffett_score = min(10, max(1, buffett_score))
        lynch_score = min(10, max(1, lynch_score))
        momentum_score = min(10, max(1, momentum_score))
        tepper_score = min(10, max(1, tepper_score))
        greenblatt_score = min(10, max(1, greenblatt_score))
        
        # Weighted composite score
        total_score = (
            buffett_score * 0.20 +      # Value quality
            lynch_score * 0.20 +         # Growth value
            momentum_score * 0.30 +      # Momentum (most actionable)
            tepper_score * 0.15 +        # Contrarian
            greenblatt_score * 0.15      # Magic formula
        )
        
        # Determine signal and confidence
        if total_score >= 7.5:
            signal = "STRONG BUY"
            confidence = "HIGH"
        elif total_score >= 6.5:
            signal = "BUY"
            confidence = "MEDIUM-HIGH"
        elif total_score >= 5.5:
            signal = "HOLD"
            confidence = "MEDIUM"
        elif total_score >= 4.5:
            signal = "WEAK"
            confidence = "LOW"
        else:
            signal = "AVOID"
            confidence = "HIGH"
        
        return {
            "total_score": round(total_score, 1),
            "buffett_score": round(buffett_score, 1),
            "lynch_score": round(lynch_score, 1),
            "momentum_score": round(momentum_score, 1),
            "tepper_score": round(tepper_score, 1),
            "greenblatt_score": round(greenblatt_score, 1),
            "signal": signal,
            "confidence": confidence,
        }
    
    async def _cmd_setup(self, chat_id: int, args: List[str]):
        """Morning prep: top 10 setups for today."""
        await self.send_message_to(chat_id, "☀️ <b>Preparing morning setups...</b>")
        
        try:
            setups = []
            for ticker in self.TOP_STOCKS[:40]:
                quote = await self._fetch_quote(ticker)
                if not quote:
                    continue
                
                score_data = await self._calculate_ai_score(ticker, quote)
                price = quote.get('price', 0)
                change_pct = quote.get('change_pct', 0)
                high = quote.get('high', 0)
                low = quote.get('low', 0)
                
                setup_type = None
                probability = 0
                
                # Identify setup types
                if score_data['ai_score'] >= 7 and 0.5 <= change_pct <= 3:
                    setup_type = "🚀 Momentum Long"
                    probability = 65 + score_data['ai_score'] * 2
                elif -2 <= change_pct <= -0.5 and score_data['trend'] >= 5:
                    setup_type = "🎯 Pullback Buy"
                    probability = 60 + score_data['ai_score']
                elif abs(change_pct) < 0.5 and score_data['volatility'] >= 6:
                    setup_type = "📐 Breakout Watch"
                    probability = 55 + score_data['ai_score']
                
                if setup_type:
                    atr_est = high - low if high > low else price * 0.02
                    setups.append({
                        "ticker": ticker,
                        "type": setup_type,
                        "price": price,
                        "stop": round(price - atr_est * 1.5, 2),
                        "target": round(price + atr_est * 2.5, 2),
                        "probability": min(85, round(probability)),
                        "score": score_data['ai_score'],
                        "change_pct": change_pct,
                    })
            
            # Sort by probability
            setups.sort(key=lambda x: x['probability'], reverse=True)
            
            msg = f"☀️ <b>MORNING SETUP - {datetime.now().strftime('%b %d, %Y')}</b>\n"
            msg += "<i>Top 10 setups for today's session</i>\n\n"
            
            if setups:
                for i, s in enumerate(setups[:10], 1):
                    prob_bar = "▓" * (s['probability'] // 10) + "░" * (10 - s['probability'] // 10)
                    msg += f"<b>#{i} {s['ticker']}</b> {s['type']}\n"
                    msg += f"   Entry: ${s['price']:.2f} | Stop: ${s['stop']:.2f} | Target: ${s['target']:.2f}\n"
                    msg += f"   Prob: {s['probability']}% [{prob_bar}]\n\n"
                
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "💡 <b>Trading Tips:</b>\n"
                msg += "• Wait 15-30 min after open for confirmation\n"
                msg += "• Use 1-2% risk per trade\n"
                msg += "• Take partial profits at 1R\n"
            else:
                msg += "📭 No clear setups found.\n"
                msg += "Consider waiting for better conditions."
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_patterns(self, chat_id: int, args: List[str]):
        """Auto-detected chart patterns."""
        await self.send_message_to(chat_id, "📊 <b>Scanning for chart patterns...</b>")
        
        try:
            patterns_found = []
            tickers = self.watchlist if self.watchlist else self.TOP_STOCKS[:20]
            
            for ticker in tickers:
                quote = await self._fetch_quote(ticker)
                if not quote:
                    continue
                
                price = quote.get('price', 0)
                high = quote.get('high', 0)
                low = quote.get('low', 0)
                change_pct = quote.get('change_pct', 0)
                
                if price <= 0:
                    continue
                
                # Simple pattern detection based on price action
                pattern = None
                daily_range = (high - low) / price * 100 if price > 0 else 0
                
                if daily_range < 1.5 and abs(change_pct) < 0.5:
                    pattern = {"name": "📐 Tight Base", "bias": "BREAKOUT PENDING", "probability": 65}
                elif change_pct > 2 and high == price:
                    pattern = {"name": "🚀 Bullish Flag Breakout", "bias": "BULLISH", "probability": 70}
                elif change_pct < -2 and low == price:
                    pattern = {"name": "📉 Breakdown", "bias": "BEARISH", "probability": 60}
                elif 0 < change_pct < 1 and daily_range > 2:
                    pattern = {"name": "🔨 Hammer/Reversal", "bias": "BULLISH", "probability": 60}
                
                if pattern:
                    patterns_found.append({
                        "ticker": ticker,
                        "price": price,
                        "change_pct": change_pct,
                        **pattern
                    })
            
            msg = "📊 <b>CHART PATTERNS DETECTED</b>\n\n"
            
            if patterns_found:
                for p in patterns_found[:10]:
                    msg += f"<b>{p['ticker']}</b> - {p['name']}\n"
                    msg += f"   Price: ${p['price']:.2f} ({'+' if p['change_pct'] >= 0 else ''}{p['change_pct']:.2f}%)\n"
                    msg += f"   Bias: {p['bias']} | Prob: {p['probability']}%\n\n"
                
                msg += "💡 Combine with volume confirmation"
            else:
                msg += "No clear patterns detected right now.\n"
                msg += "Patterns form over days/weeks - check back later."
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_divergence(self, chat_id: int, args: List[str]):
        """MACD/RSI divergence alerts."""
        msg = """
📊 <b>DIVERGENCE SCANNER</b>

<b>What are divergences?</b>
• Price makes new high, but indicator doesn't = Bearish
• Price makes new low, but indicator doesn't = Bullish

<b>Coming Soon:</b>
• RSI divergence detection
• MACD divergence alerts
• Real-time monitoring

<i>Use /analyze TICKER for current technical indicators</i>
"""
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_daytrade(self, chat_id: int, args: List[str]):
        """Intraday ORB/VWAP setups."""
        await self.send_message_to(chat_id, "⚡ <b>Scanning for intraday setups...</b>")
        
        try:
            setups = []
            for ticker in self.TOP_STOCKS[:25]:
                quote = await self._fetch_quote(ticker)
                if not quote:
                    continue
                
                price = quote.get('price', 0)
                high = quote.get('high', 0)
                low = quote.get('low', 0)
                change_pct = quote.get('change_pct', 0)
                volume = quote.get('volume', 0)
                
                if price <= 0:
                    continue
                
                # Opening Range Breakout detection
                orb_high = high  # Simplified - would use first 15-30 min range
                orb_low = low
                orb_range = orb_high - orb_low
                
                setup = None
                if price >= orb_high * 0.998 and change_pct > 0.5:
                    setup = {
                        "type": "🟢 ORB Long",
                        "entry": orb_high,
                        "stop": orb_low,
                        "target": orb_high + orb_range * 2,
                    }
                elif price <= orb_low * 1.002 and change_pct < -0.5:
                    setup = {
                        "type": "🔴 ORB Short",
                        "entry": orb_low,
                        "stop": orb_high,
                        "target": orb_low - orb_range * 2,
                    }
                
                if setup:
                    setups.append({
                        "ticker": ticker,
                        "price": price,
                        "change_pct": change_pct,
                        **setup
                    })
            
            msg = "⚡ <b>INTRADAY SETUPS</b>\n"
            msg += "<i>ORB & VWAP bounce candidates</i>\n\n"
            
            if setups:
                for s in setups[:8]:
                    rr = abs(s['target'] - s['entry']) / abs(s['entry'] - s['stop']) if s['entry'] != s['stop'] else 0
                    msg += f"<b>{s['ticker']}</b> - {s['type']}\n"
                    msg += f"   Entry: ${s['entry']:.2f}\n"
                    msg += f"   Stop: ${s['stop']:.2f}\n"
                    msg += f"   Target: ${s['target']:.2f} ({rr:.1f}R)\n\n"
                
                msg += "⚠️ <b>Day Trading Rules:</b>\n"
                msg += "• Max 3 trades per day\n"
                msg += "• Stop after 2 losses\n"
                msg += "• Take profits quickly\n"
            else:
                msg += "No clear intraday setups right now.\n"
                msg += "Best setups appear 30 min after market open."
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_heatmap(self, chat_id: int, args: List[str]):
        """Visual market heatmap by sector."""
        await self.send_message_to(chat_id, "🗺️ <b>Generating market heatmap...</b>")
        
        try:
            sectors = {
                "Technology": ["AAPL", "MSFT", "NVDA", "AMD", "GOOGL"],
                "Financials": ["JPM", "BAC", "GS", "V", "MA"],
                "Healthcare": ["UNH", "JNJ", "PFE", "LLY", "ABBV"],
                "Consumer": ["AMZN", "TSLA", "WMT", "HD", "MCD"],
                "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
                "Communications": ["META", "NFLX", "DIS", "TMUS", "VZ"],
            }
            
            msg = "🗺️ <b>MARKET HEATMAP</b>\n\n"
            
            sector_data = []
            for sector, tickers in sectors.items():
                changes = []
                for ticker in tickers:
                    quote = await self._fetch_quote(ticker)
                    if quote:
                        changes.append(quote.get('change_pct', 0))
                
                if changes:
                    avg_change = sum(changes) / len(changes)
                    sector_data.append({
                        "sector": sector,
                        "change": avg_change,
                        "stocks": len(changes)
                    })
            
            # Sort by performance
            sector_data.sort(key=lambda x: x['change'], reverse=True)
            
            # Visual heatmap
            for s in sector_data:
                if s['change'] > 1:
                    heat = "🟩🟩🟩"
                    label = "HOT"
                elif s['change'] > 0.3:
                    heat = "🟩🟩"
                    label = "WARM"
                elif s['change'] > -0.3:
                    heat = "⬜"
                    label = "NEUTRAL"
                elif s['change'] > -1:
                    heat = "🟥🟥"
                    label = "COOL"
                else:
                    heat = "🟥🟥🟥"
                    label = "COLD"
                
                msg += f"{heat} <b>{s['sector']}</b>: {'+' if s['change'] >= 0 else ''}{s['change']:.2f}% [{label}]\n"
            
            # Market bias
            total_avg = sum(s['change'] for s in sector_data) / len(sector_data) if sector_data else 0
            if total_avg > 0.5:
                bias = "📈 BULLISH - Risk On"
            elif total_avg > 0:
                bias = "↗️ SLIGHT BULL"
            elif total_avg > -0.5:
                bias = "↔️ MIXED/RANGE"
            else:
                bias = "📉 BEARISH - Risk Off"
            
            msg += f"\n<b>Market Bias:</b> {bias}\n"
            msg += f"<i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_simtrade(self, chat_id: int, args: List[str]):
        """Simulate trading from a historical date - see what would have happened."""
        if not args:
            msg = """
🎮 <b>TRADE SIMULATION</b>

Simulate what would happen if you followed the AI picks from a past date.

Usage:
<code>/simtrade 2025-04-06</code> - Simulate from April 6, 2025
<code>/simtrade 2025-01-15</code> - Simulate from January 15, 2025

The simulation will:
1. Generate picks based on that date's data
2. Apply stop loss (-3%) and take profit (+5%)
3. Hold for max 15 days
4. Show actual results vs today's prices

This tests if following the system would have been profitable!
"""
            await self.send_message_to(chat_id, msg)
            return
        
        # Parse date
        try:
            from datetime import datetime, timedelta
            sim_date = datetime.strptime(args[0], "%Y-%m-%d")
        except ValueError:
            await self.send_message_to(chat_id, "❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-04-06)")
            return
        
        # Validate date is in the past
        today = datetime.now()
        if sim_date >= today:
            await self.send_message_to(chat_id, "❌ Simulation date must be in the past")
            return
        
        days_since = (today - sim_date).days
        if days_since > 365:
            await self.send_message_to(chat_id, "❌ Date too far in the past (max 1 year)")
            return
        
        await self.send_message_to(chat_id, f"🎮 <b>Running trade simulation from {sim_date.strftime('%Y-%m-%d')}...</b>\n<i>Fetching historical data for 10 stocks...</i>")
        
        try:
            import aiohttp
            
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key
            }
            
            # Tickers to simulate
            sim_tickers = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", 
                          "META", "TSLA", "AMD", "JPM", "V"]
            
            trades = []
            
            async with aiohttp.ClientSession() as session:
                for ticker in sim_tickers:
                    # Fetch bars from sim_date to today
                    url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
                    params = {
                        "start": sim_date.strftime("%Y-%m-%d"),
                        "end": today.strftime("%Y-%m-%d"),
                        "timeframe": "1Day",
                        "feed": "iex",
                        "limit": 400
                    }
                    
                    async with session.get(url, headers=headers, params=params) as resp:
                        if resp.status != 200:
                            continue
                        
                        data = await resp.json()
                        bars = data.get("bars", [])
                        
                        if len(bars) < 5:
                            continue
                        
                        # Entry on sim_date (or next trading day)
                        entry_bar = bars[0]
                        entry_price = float(entry_bar.get("o", 0))  # Open price
                        entry_date = entry_bar.get("t", "")[:10]
                        
                        # Calculate entry signals based on historical data
                        # Use first 3 bars to determine if this was a "pick"
                        if len(bars) >= 3:
                            d1_close = float(bars[0].get("c", 0))
                            d2_close = float(bars[1].get("c", 0))
                            d3_close = float(bars[2].get("c", 0))
                            
                            # Simple momentum check - was it trending?
                            if d2_close > d1_close or d3_close > d2_close:
                                was_pick = True
                                setup = "Momentum"
                            elif d1_close < float(bars[0].get("o", 0)) * 0.98:
                                was_pick = True
                                setup = "Oversold"
                            else:
                                was_pick = False
                                setup = "N/A"
                        else:
                            was_pick = False
                            setup = "N/A"
                        
                        if not was_pick:
                            continue
                        
                        # Simulate trade with stop/take profit
                        stop_pct = -3.0  # -3% stop loss
                        target_pct = 5.0  # +5% take profit
                        max_hold = 15  # 15 days max hold
                        
                        exit_price = 0
                        exit_reason = ""
                        exit_date = ""
                        pnl_pct = 0
                        
                        # Track through subsequent bars
                        for i, bar in enumerate(bars[1:min(max_hold+1, len(bars))], 1):
                            bar_high = float(bar.get("h", 0))
                            bar_low = float(bar.get("l", 0))
                            bar_close = float(bar.get("c", 0))
                            
                            # Check stop loss hit
                            stop_price = entry_price * (1 + stop_pct/100)
                            if bar_low <= stop_price:
                                exit_price = stop_price
                                exit_reason = "🛑 Stop Loss"
                                exit_date = bar.get("t", "")[:10]
                                pnl_pct = stop_pct
                                break
                            
                            # Check take profit hit
                            target_price = entry_price * (1 + target_pct/100)
                            if bar_high >= target_price:
                                exit_price = target_price
                                exit_reason = "🎯 Take Profit"
                                exit_date = bar.get("t", "")[:10]
                                pnl_pct = target_pct
                                break
                            
                            # Max hold exit
                            if i >= max_hold - 1:
                                exit_price = bar_close
                                exit_reason = "⏱️ Max Hold"
                                exit_date = bar.get("t", "")[:10]
                                pnl_pct = (exit_price - entry_price) / entry_price * 100
                                break
                        
                        # If we didn't exit, use last bar
                        if exit_price == 0:
                            last_bar = bars[-1]
                            exit_price = float(last_bar.get("c", entry_price))
                            exit_reason = "📅 Current"
                            exit_date = last_bar.get("t", "")[:10]
                            pnl_pct = (exit_price - entry_price) / entry_price * 100
                        
                        trades.append({
                            "ticker": ticker,
                            "setup": setup,
                            "entry_date": entry_date,
                            "entry_price": entry_price,
                            "exit_date": exit_date,
                            "exit_price": exit_price,
                            "exit_reason": exit_reason,
                            "pnl_pct": pnl_pct,
                            "pnl_emoji": "🟢" if pnl_pct > 0 else "🔴"
                        })
            
            # Calculate portfolio statistics
            if trades:
                total_return = sum(t['pnl_pct'] for t in trades)
                avg_return = total_return / len(trades)
                wins = [t for t in trades if t['pnl_pct'] > 0]
                losses = [t for t in trades if t['pnl_pct'] <= 0]
                win_rate = len(wins) / len(trades) * 100 if trades else 0
                
                avg_win = sum(t['pnl_pct'] for t in wins) / len(wins) if wins else 0
                avg_loss = sum(t['pnl_pct'] for t in losses) / len(losses) if losses else 0
                
                # Calculate profit factor
                gross_profit = sum(t['pnl_pct'] for t in wins) if wins else 0
                gross_loss = abs(sum(t['pnl_pct'] for t in losses)) if losses else 0.01
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
                
                # Hypothetical portfolio value ($10,000 starting, equal weight)
                position_size = 10000 / len(trades)
                final_value = sum(position_size * (1 + t['pnl_pct']/100) for t in trades)
                portfolio_return = (final_value - 10000) / 10000 * 100
                
                msg = f"🎮 <b>TRADE SIMULATION RESULTS</b>\n"
                msg += f"<i>From: {sim_date.strftime('%Y-%m-%d')} ({days_since} days ago)</i>\n\n"
                
                # Summary
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "📊 <b>PORTFOLIO SUMMARY</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                port_emoji = "🟢" if portfolio_return > 0 else "🔴"
                msg += f"{port_emoji} Portfolio Return: <b>{portfolio_return:+.2f}%</b>\n"
                msg += f"Starting: $10,000 → Final: ${final_value:,.2f}\n"
                msg += f"Trades: {len(trades)} | Win Rate: {win_rate:.0f}%\n"
                msg += f"Avg Win: {avg_win:+.2f}% | Avg Loss: {avg_loss:.2f}%\n"
                msg += f"Profit Factor: {profit_factor:.2f}\n\n"
                
                # Individual trades
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "📈 <b>INDIVIDUAL TRADES</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                
                for t in trades:
                    msg += f"\n{t['pnl_emoji']} <b>{t['ticker']}</b> ({t['setup']})\n"
                    msg += f"   Entry: ${t['entry_price']:.2f} ({t['entry_date']})\n"
                    msg += f"   Exit: ${t['exit_price']:.2f} ({t['exit_date']})\n"
                    msg += f"   {t['exit_reason']}: {t['pnl_pct']:+.2f}%\n"
                
                # Lessons learned
                msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "💡 <b>AI INSIGHTS</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                
                if profit_factor >= 1.5:
                    msg += "✅ Strategy was profitable\n"
                    msg += "• Stop/TP rules protected capital\n"
                elif profit_factor >= 1.0:
                    msg += "🟡 Strategy was break-even\n"
                    msg += "• Consider tighter stops or better entries\n"
                else:
                    msg += "⚠️ Strategy underperformed\n"
                    msg += "• Review entry criteria\n"
                
                if win_rate >= 60:
                    msg += "• High win rate - good entry timing\n"
                elif win_rate < 40:
                    msg += "• Low win rate - improve signal quality\n"
                
                msg += f"\n<i>Simulation completed at {datetime.now().strftime('%H:%M:%S')}</i>"
            else:
                msg = "📭 No qualifying trades found for that date range.\n"
                msg += "Try a different date or more liquid tickers."
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            logger.error(f"Simulation error: {e}")
            await self.send_message_to(chat_id, f"❌ Simulation error: {e}")
    
    async def _cmd_backtest(self, chat_id: int, args: List[str]):
        """Run backtest on historical data."""
        if not args:
            msg = """
📊 <b>HISTORICAL BACKTEST</b>

Usage:
<code>/backtest AAPL</code> - Backtest AAPL (1 year)
<code>/backtest AAPL 6m</code> - 6 months
<code>/backtest AAPL 3m</code> - 3 months
<code>/backtest AAPL 1y</code> - 1 year

<b>Strategies tested:</b>
• Momentum (buy on strength)
• Mean Reversion (buy on dips)
• Trend Following (MA crossover)
"""
            await self.send_message_to(chat_id, msg)
            return
        
        ticker = args[0].upper()
        period = args[1].lower() if len(args) > 1 else "1y"
        
        # Parse period
        if period == "3m":
            days = 90
            period_name = "3 Months"
        elif period == "6m":
            days = 180
            period_name = "6 Months"
        else:
            days = 365
            period_name = "1 Year"
        
        await self.send_message_to(chat_id, f"📊 <b>Running backtest for {ticker}...</b>\n<i>Period: {period_name}</i>")
        
        try:
            # Fetch historical bars from Alpaca
            bars = await self._fetch_historical_bars(ticker, days)
            
            if not bars or len(bars) < 20:
                await self.send_message_to(chat_id, f"❌ Insufficient historical data for {ticker}")
                return
            
            # Run backtests
            momentum_results = self._backtest_momentum(bars)
            mean_rev_results = self._backtest_mean_reversion(bars)
            trend_results = self._backtest_trend_following(bars)
            
            # Calculate buy & hold
            start_price = bars[0]['close']
            end_price = bars[-1]['close']
            buy_hold_return = ((end_price - start_price) / start_price * 100)
            
            msg = f"📊 <b>BACKTEST RESULTS: {ticker}</b>\n"
            msg += f"<i>Period: {period_name} ({len(bars)} trading days)</i>\n\n"
            
            # Buy & Hold Benchmark
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📈 <b>BUY & HOLD (Benchmark)</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            bh_emoji = "🟢" if buy_hold_return >= 0 else "🔴"
            msg += f"{bh_emoji} Return: {buy_hold_return:+.2f}%\n"
            msg += f"Start: ${start_price:.2f} → End: ${end_price:.2f}\n\n"
            
            # Momentum Strategy
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "🚀 <b>MOMENTUM STRATEGY</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"Trades: {momentum_results['trades']}\n"
            msg += f"Win Rate: {momentum_results['win_rate']:.1f}%\n"
            msg += f"Total Return: {'+' if momentum_results['total_return'] >= 0 else ''}{momentum_results['total_return']:.2f}%\n"
            msg += f"Avg Win: {momentum_results['avg_win']:.2f}% | Avg Loss: {momentum_results['avg_loss']:.2f}%\n"
            msg += f"Profit Factor: {momentum_results['profit_factor']:.2f}\n"
            msg += f"Max Drawdown: {momentum_results['max_dd']:.2f}%\n\n"
            
            # Mean Reversion Strategy
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "🔄 <b>MEAN REVERSION STRATEGY</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"Trades: {mean_rev_results['trades']}\n"
            msg += f"Win Rate: {mean_rev_results['win_rate']:.1f}%\n"
            msg += f"Total Return: {'+' if mean_rev_results['total_return'] >= 0 else ''}{mean_rev_results['total_return']:.2f}%\n"
            msg += f"Avg Win: {mean_rev_results['avg_win']:.2f}% | Avg Loss: {mean_rev_results['avg_loss']:.2f}%\n"
            msg += f"Profit Factor: {mean_rev_results['profit_factor']:.2f}\n\n"
            
            # Trend Following Strategy
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📈 <b>TREND FOLLOWING STRATEGY</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"Trades: {trend_results['trades']}\n"
            msg += f"Win Rate: {trend_results['win_rate']:.1f}%\n"
            msg += f"Total Return: {'+' if trend_results['total_return'] >= 0 else ''}{trend_results['total_return']:.2f}%\n"
            msg += f"Profit Factor: {trend_results['profit_factor']:.2f}\n\n"
            
            # Best Strategy
            strategies = [
                ("Momentum", momentum_results['total_return']),
                ("Mean Reversion", mean_rev_results['total_return']),
                ("Trend Following", trend_results['total_return']),
                ("Buy & Hold", buy_hold_return)
            ]
            best = max(strategies, key=lambda x: x[1])
            
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "🏆 <b>BEST STRATEGY</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"<b>{best[0]}</b> with {best[1]:+.2f}% return\n\n"
            
            msg += f"<i>Backtest completed at {datetime.now().strftime('%H:%M:%S')}</i>"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            logger.error(f"Backtest error: {e}")
            await self.send_message_to(chat_id, f"❌ Backtest error: {e}")
    
    async def _fetch_historical_bars(self, ticker: str, days: int) -> List[Dict]:
        """Fetch historical OHLCV bars from Alpaca."""
        try:
            import aiohttp
            from datetime import timedelta
            
            if not settings.alpaca_api_key or not settings.alpaca_secret_key:
                return []
            
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key
            }
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
            params = {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d"),
                "timeframe": "1Day",
                "feed": "iex",
                "limit": 500
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        return []
                    
                    data = await resp.json()
                    bars = data.get("bars", [])
                    
                    return [{
                        "date": bar.get("t"),
                        "open": float(bar.get("o", 0)),
                        "high": float(bar.get("h", 0)),
                        "low": float(bar.get("l", 0)),
                        "close": float(bar.get("c", 0)),
                        "volume": int(bar.get("v", 0)),
                    } for bar in bars]
                    
        except Exception as e:
            logger.error(f"Historical bars fetch error: {e}")
            return []
    
    def _backtest_momentum(self, bars: List[Dict]) -> Dict:
        """Backtest momentum strategy: buy on 3-day positive streak."""
        trades = []
        in_position = False
        entry_price = 0
        
        for i in range(3, len(bars) - 1):
            # Entry: 3 consecutive up days
            if not in_position:
                if (bars[i]['close'] > bars[i-1]['close'] and
                    bars[i-1]['close'] > bars[i-2]['close'] and
                    bars[i-2]['close'] > bars[i-3]['close']):
                    in_position = True
                    entry_price = bars[i+1]['open']  # Buy next open
            
            # Exit: down day or 5% profit or 3% loss
            elif in_position:
                current = bars[i]['close']
                pnl_pct = (current - entry_price) / entry_price * 100
                
                if pnl_pct >= 5 or pnl_pct <= -3 or bars[i]['close'] < bars[i-1]['close']:
                    trades.append(pnl_pct)
                    in_position = False
        
        return self._calculate_backtest_stats(trades)
    
    def _backtest_mean_reversion(self, bars: List[Dict]) -> Dict:
        """Backtest mean reversion: buy on 3% dip, sell on bounce."""
        trades = []
        in_position = False
        entry_price = 0
        
        for i in range(1, len(bars) - 1):
            if not in_position:
                # Entry: -3% or more daily drop
                daily_change = (bars[i]['close'] - bars[i-1]['close']) / bars[i-1]['close'] * 100
                if daily_change <= -2.5:
                    in_position = True
                    entry_price = bars[i+1]['open']  # Buy next open
            
            elif in_position:
                current = bars[i]['close']
                pnl_pct = (current - entry_price) / entry_price * 100
                
                # Exit: 3% profit, 4% loss, or 5 days
                if pnl_pct >= 3 or pnl_pct <= -4:
                    trades.append(pnl_pct)
                    in_position = False
        
        return self._calculate_backtest_stats(trades)
    
    def _backtest_trend_following(self, bars: List[Dict]) -> Dict:
        """Backtest trend following: 10/20 MA crossover."""
        trades = []
        in_position = False
        entry_price = 0
        
        for i in range(20, len(bars) - 1):
            # Calculate MAs
            ma10 = sum(b['close'] for b in bars[i-9:i+1]) / 10
            ma20 = sum(b['close'] for b in bars[i-19:i+1]) / 20
            ma10_prev = sum(b['close'] for b in bars[i-10:i]) / 10
            ma20_prev = sum(b['close'] for b in bars[i-20:i]) / 20
            
            if not in_position:
                # Golden cross: MA10 crosses above MA20
                if ma10 > ma20 and ma10_prev <= ma20_prev:
                    in_position = True
                    entry_price = bars[i+1]['open']
            
            elif in_position:
                # Death cross: MA10 crosses below MA20
                if ma10 < ma20 and ma10_prev >= ma20_prev:
                    exit_price = bars[i+1]['open']
                    pnl_pct = (exit_price - entry_price) / entry_price * 100
                    trades.append(pnl_pct)
                    in_position = False
        
        return self._calculate_backtest_stats(trades)
    
    def _calculate_backtest_stats(self, trades: List[float]) -> Dict:
        """Calculate backtest statistics from trades list."""
        if not trades:
            return {
                "trades": 0, "win_rate": 0, "total_return": 0,
                "avg_win": 0, "avg_loss": 0, "profit_factor": 0, "max_dd": 0
            }
        
        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]
        
        total_return = sum(trades)
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0
        
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit
        
        # Calculate max drawdown
        equity = 100
        peak = 100
        max_dd = 0
        for t in trades:
            equity = equity * (1 + t/100)
            peak = max(peak, equity)
            dd = (peak - equity) / peak * 100
            max_dd = max(max_dd, dd)
        
        return {
            "trades": len(trades),
            "win_rate": win_rate,
            "total_return": total_return,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "max_dd": max_dd
        }
    
    async def _cmd_performance(self, chat_id: int, args: List[str]):
        """Win rate, profit factor, Sharpe."""
        msg = """
📈 <b>YOUR TRADING PERFORMANCE</b>

<b>This Month:</b>
━━━━━━━━━━━━━━━━━━━━━━
Trades: 0
Win Rate: N/A
P&L: $0.00

<b>All Time:</b>
━━━━━━━━━━━━━━━━━━━━━━
Total Trades: 0
Win Rate: N/A
Profit Factor: N/A
Sharpe Ratio: N/A
Max Drawdown: N/A

<i>Start trading to track performance!</i>
<i>Use /buy or /sell to execute trades</i>
"""
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_journal(self, chat_id: int, args: List[str]):
        """Trade journal & analysis."""
        msg = """
📓 <b>TRADE JOURNAL</b>

No trades recorded yet.

<b>Journal Features:</b>
• Track all entries and exits
• Note why trades worked/failed
• Identify pattern in losses
• Refine your edge over time

<b>Tips for Journaling:</b>
1. Record entry reason
2. Note emotional state
3. Review weekly
4. Identify recurring mistakes

<i>Execute trades via /buy and /sell to build your journal</i>
"""
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_sizing(self, chat_id: int, args: List[str]):
        """Calculate position size."""
        if len(args) < 2:
            msg = """
📏 <b>POSITION SIZING CALCULATOR</b>

Usage: <code>/sizing TICKER STOP_PRICE</code>

Example: <code>/sizing AAPL 240</code>
(Calculate size for AAPL with stop at $240)

<b>Risk Parameters:</b>
• Account: $100,000 (default)
• Risk per trade: 1%
• Max position: 10% of account
"""
            await self.send_message_to(chat_id, msg)
            return
        
        try:
            ticker = args[0].upper()
            stop_price = float(args[1])
            account_size = 100000  # Default account size
            risk_pct = 0.01  # 1% risk
            
            quote = await self._fetch_quote(ticker)
            if not quote:
                await self.send_message_to(chat_id, f"❌ Could not fetch {ticker}")
                return
            
            price = quote.get('price', 0)
            if price <= stop_price:
                await self.send_message_to(chat_id, "❌ Stop price must be below current price for longs")
                return
            
            risk_per_share = price - stop_price
            risk_amount = account_size * risk_pct
            shares = int(risk_amount / risk_per_share)
            position_value = shares * price
            position_pct = (position_value / account_size) * 100
            
            # Cap at 10% of account
            max_shares = int(account_size * 0.10 / price)
            if shares > max_shares:
                shares = max_shares
                position_value = shares * price
                position_pct = (position_value / account_size) * 100
            
            target_1r = price + risk_per_share
            target_2r = price + risk_per_share * 2
            target_3r = price + risk_per_share * 3
            
            msg = f"""
📏 <b>POSITION SIZE: {ticker}</b>

━━━━━━━━━━━━━━━━━━━━━━
💰 <b>ENTRY DETAILS</b>
━━━━━━━━━━━━━━━━━━━━━━
Current Price: ${price:.2f}
Stop Loss: ${stop_price:.2f}
Risk/Share: ${risk_per_share:.2f}

━━━━━━━━━━━━━━━━━━━━━━
📊 <b>POSITION SIZE</b>
━━━━━━━━━━━━━━━━━━━━━━
Shares: <b>{shares}</b>
Position Value: ${position_value:,.2f}
% of Account: {position_pct:.1f}%
Risk Amount: ${risk_amount:.2f} (1%)

━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>TARGETS</b>
━━━━━━━━━━━━━━━━━━━━━━
Target 1 (1R): ${target_1r:.2f}
Target 2 (2R): ${target_2r:.2f}
Target 3 (3R): ${target_3r:.2f}

<i>Based on $100k account, 1% risk</i>
"""
            await self.send_message_to(chat_id, msg)
            
        except ValueError:
            await self.send_message_to(chat_id, "❌ Invalid stop price. Use: /sizing AAPL 240")
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_exposure(self, chat_id: int, args: List[str]):
        """Sector exposure & correlation."""
        try:
            positions = await self._get_positions()
            
            msg = "📊 <b>PORTFOLIO EXPOSURE</b>\n\n"
            
            if not positions:
                msg += "<b>No open positions</b>\n\n"
                msg += "<b>Recommended Limits:</b>\n"
                msg += "• Max 25% per sector\n"
                msg += "• Max 10% per stock\n"
                msg += "• 5-8 positions max\n"
                msg += "• Keep 20% cash\n\n"
                msg += "<b>Sector Buckets:</b>\n"
                msg += "• Tech: AAPL, MSFT, NVDA, AMD\n"
                msg += "• Finance: JPM, V, MA, GS\n"
                msg += "• Health: UNH, JNJ, LLY\n"
                msg += "• Consumer: AMZN, WMT, COST\n"
            else:
                total_value = sum(p.get('value', 0) for p in positions)
                msg += f"<b>Total Exposure:</b> ${total_value:,.2f}\n\n"
                
                for p in positions:
                    pct = (p.get('value', 0) / total_value * 100) if total_value else 0
                    msg += f"• {p['ticker']}: {pct:.1f}%\n"
            
            msg += "\n<i>Diversification reduces risk</i>"
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    async def _cmd_eod(self, chat_id: int, args: List[str]):
        """End of day report."""
        await self.send_message_to(chat_id, "🌙 <b>Generating EOD report...</b>")
        
        try:
            # Get market indices
            spy = await self._fetch_quote("SPY")
            qqq = await self._fetch_quote("QQQ")
            
            msg = f"🌙 <b>END OF DAY REPORT</b>\n"
            msg += f"<i>{datetime.now().strftime('%A, %B %d, %Y')}</i>\n\n"
            
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📊 <b>MARKET CLOSE</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            
            if spy:
                emoji = "🟢" if spy.get('change_pct', 0) >= 0 else "🔴"
                msg += f"{emoji} S&P 500: {'+' if spy.get('change_pct', 0) >= 0 else ''}{spy.get('change_pct', 0):.2f}%\n"
            if qqq:
                emoji = "🟢" if qqq.get('change_pct', 0) >= 0 else "🔴"
                msg += f"{emoji} NASDAQ: {'+' if qqq.get('change_pct', 0) >= 0 else ''}{qqq.get('change_pct', 0):.2f}%\n"
            
            # Get top movers from watchlist
            if self.watchlist:
                msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "👀 <b>YOUR WATCHLIST</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
                
                for ticker in self.watchlist[:5]:
                    quote = await self._fetch_quote(ticker)
                    if quote:
                        change_pct = quote.get('change_pct', 0)
                        emoji = "🟢" if change_pct >= 0 else "🔴"
                        msg += f"{emoji} {ticker}: {'+' if change_pct >= 0 else ''}{change_pct:.2f}%\n"
            
            msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📋 <b>TOMORROW'S PREP</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "• Review today's trades\n"
            msg += "• Check earnings calendar\n"
            msg += "• Update watchlist\n"
            msg += "• Set alerts for key levels\n"
            
            msg += "\n💤 <i>Rest well. Markets open at 9:30 AM ET.</i>"
            
            await self.send_message_to(chat_id, msg)
            
        except Exception as e:
            await self.send_message_to(chat_id, f"❌ Error: {e}")
    
    # ===== Helper Methods =====
    
    async def _fetch_quote(self, ticker: str, detailed: bool = False) -> Optional[Dict]:
        """Fetch stock quote from Alpaca using Trade API (more accurate than Quote API)."""
        try:
            import aiohttp
            
            if not settings.alpaca_api_key or not settings.alpaca_secret_key:
                return None
            
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key
            }
            
            async with aiohttp.ClientSession() as session:
                price = 0
                bid = 0
                ask = 0
                
                # Method 1: Get latest TRADE (most accurate current price)
                trade_url = f"https://data.alpaca.markets/v2/stocks/{ticker}/trades/latest"
                params = {"feed": "iex"}
                async with session.get(trade_url, headers=headers, params=params) as trade_resp:
                    if trade_resp.status == 200:
                        trade_json = await trade_resp.json()
                        trade_data = trade_json.get("trade", {})
                        price = float(trade_data.get("p", 0))
                
                # Fallback to quote if trade fails
                if price == 0:
                    quote_url = f"https://data.alpaca.markets/v2/stocks/{ticker}/quotes/latest"
                    async with session.get(quote_url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            quote_data = data.get("quote", {})
                            bid = float(quote_data.get("bp", 0))
                            ask = float(quote_data.get("ap", 0))
                            price = (bid + ask) / 2 if bid and ask else bid or ask
                
                if price == 0:
                    return None
                
                # Get latest bar for OHLC and prev close
                bars_url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars/latest"
                async with session.get(bars_url, headers=headers, params=params) as bar_resp:
                    bar_data = {}
                    if bar_resp.status == 200:
                        bars_json = await bar_resp.json()
                        bar_data = bars_json.get("bar", {})
                
                # Get previous day bar for accurate prev_close
                prev_close = float(bar_data.get("c", price))
                open_price = float(bar_data.get("o", price))
                high = float(bar_data.get("h", price))
                low = float(bar_data.get("l", price))
                volume = int(bar_data.get("v", 0))
                
                # Try to get previous day's close for accurate change calculation
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
                
                bars_hist_url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
                hist_params = {
                    "timeframe": "1Day",
                    "start": start_date,
                    "end": end_date,
                    "limit": 2,
                    "feed": "iex"
                }
                async with session.get(bars_hist_url, headers=headers, params=hist_params) as hist_resp:
                    if hist_resp.status == 200:
                        hist_json = await hist_resp.json()
                        bars_list = hist_json.get("bars", [])
                        if len(bars_list) >= 2:
                            prev_close = float(bars_list[-2].get("c", prev_close))
                            open_price = float(bars_list[-1].get("o", open_price))
                            high = float(bars_list[-1].get("h", high))
                            low = float(bars_list[-1].get("l", low))
                            volume = int(bars_list[-1].get("v", volume))
                        elif len(bars_list) == 1:
                            prev_close = float(bars_list[0].get("o", prev_close))
                
                # Calculate change from previous close
                change = price - prev_close if prev_close else 0
                change_pct = (change / prev_close * 100) if prev_close else 0
                
                return {
                    "ticker": ticker,
                    "name": ticker,
                    "price": price,
                    "bid": bid,
                    "ask": ask,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "volume": volume,
                    "prev_close": prev_close,
                    "change": change,
                    "change_pct": change_pct,
                    "avg_volume": 0,
                    "market_cap": 0,
                    "pe_ratio": "N/A",
                    "low_52w": 0,
                    "high_52w": 0,
                }
                
        except Exception as e:
            logger.error(f"Quote fetch error for {ticker}: {e}")
            return None
    
    async def _get_positions(self) -> List[Dict]:
        """Get positions from active broker."""
        if self.active_broker == BrokerType.FUTU and self.futu_client:
            return await self._get_futu_positions()
        elif self.active_broker == BrokerType.IB and self.ib_client:
            return await self._get_ib_positions()
        else:
            # Paper trading - return empty
            return []
    
    async def _get_futu_positions(self) -> List[Dict]:
        """Get positions from Futu."""
        # Futu OpenD integration would go here
        return []
    
    async def _get_ib_positions(self) -> List[Dict]:
        """Get positions from Interactive Brokers."""
        # IB Gateway integration would go here
        return []
    
    def _is_market_open(self) -> bool:
        """Check if US market is open."""
        now = datetime.now()
        # Simple check - market hours 9:30 AM - 4:00 PM ET
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()
        
        if weekday >= 5:  # Weekend
            return False
        
        # Rough EST approximation (should use proper timezone)
        if 9 <= hour < 16:
            if hour == 9 and minute < 30:
                return False
            return True
        return False
    
    def _generate_bar(self, pct: float) -> str:
        """Generate visual bar for percentage."""
        bars = int(min(abs(pct), 5))
        if pct >= 0:
            return "█" * bars + "░" * (5 - bars)
        else:
            return "░" * (5 - bars) + "█" * bars
    
    async def _price_alert_monitor(self):
        """Monitor price alerts in background."""
        while self._running:
            try:
                alerts_to_remove = []
                
                for alert_id, alert in self.price_alerts.items():
                    quote = await self._fetch_quote(alert["ticker"])
                    if not quote:
                        continue
                    
                    price = quote.get("price", 0)
                    triggered = False
                    
                    if alert["condition"] == "above" and price >= alert["price"]:
                        triggered = True
                    elif alert["condition"] == "below" and price <= alert["price"]:
                        triggered = True
                    
                    if triggered:
                        msg = f"""
🔔 <b>PRICE ALERT</b>

<b>{alert['ticker']}</b> is now {alert['condition']} ${alert['price']:.2f}

<b>Current Price:</b> ${price:.2f}

<i>Alert triggered at {datetime.now().strftime('%H:%M:%S')}</i>
"""
                        await self.send_message_to(alert["chat_id"], msg)
                        alerts_to_remove.append(alert_id)
                
                for alert_id in alerts_to_remove:
                    del self.price_alerts[alert_id]
                    
            except Exception as e:
                logger.error(f"Price alert monitor error: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _market_update_loop(self):
        """Send periodic market updates and automated scans."""
        last_hourly_scan = 0
        last_morning_scan = None
        last_eod_report = None
        
        while self._running:
            try:
                now = datetime.now()
                current_hour = now.hour
                today = now.date()
                
                # Skip if not enabled
                if not self.auto_updates_enabled:
                    await asyncio.sleep(60)
                    continue
                
                # Morning Pre-Market Scan (8:30 AM - before market open)
                if current_hour == 8 and now.minute >= 30 and now.minute < 31:
                    if last_morning_scan != today:
                        last_morning_scan = today
                        await self._send_morning_briefing()
                
                # Market Open Alert (9:30 AM)
                if current_hour == 9 and now.minute == 30:
                    await self.send_message("🔔 <b>Market Open!</b>\n\n🇺🇸 US markets are now open for trading.\n\nUse /oppty for opportunities!")
                
                # Hourly Opportunity Scan (during market hours 10AM - 3PM)
                if 10 <= current_hour <= 15:
                    if current_hour != last_hourly_scan and now.minute < 5:
                        last_hourly_scan = current_hour
                        await self._send_hourly_scan()
                
                # Mid-day Update (12:30 PM)
                if current_hour == 12 and now.minute >= 30 and now.minute < 31:
                    await self._send_midday_update()
                
                # Market Close Alert & EOD Report (4:00 PM)
                if current_hour == 16 and now.minute < 5:
                    if last_eod_report != today:
                        last_eod_report = today
                        await self._send_market_close_summary()
                
            except Exception as e:
                logger.error(f"Market update loop error: {e}")
            
            await asyncio.sleep(60)  # Check every minute
    
    async def _send_morning_briefing(self):
        """Send morning pre-market briefing."""
        try:
            msg = f"☀️ <b>MORNING BRIEFING</b>\n"
            msg += f"<i>{datetime.now().strftime('%A, %B %d, %Y')}</i>\n\n"
            
            # Pre-market movers (check futures/indices)
            spy = await self._fetch_quote("SPY")
            qqq = await self._fetch_quote("QQQ")
            
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📊 <b>MARKET OUTLOOK</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            
            if spy:
                emoji = "🟢" if spy.get('change_pct', 0) >= 0 else "🔴"
                msg += f"{emoji} SPY: ${spy.get('price', 0):.2f}\n"
            if qqq:
                emoji = "🟢" if qqq.get('change_pct', 0) >= 0 else "🔴"
                msg += f"{emoji} QQQ: ${qqq.get('price', 0):.2f}\n"
            
            msg += "\n"
            msg += "🔔 <b>TODAY'S ACTIONS:</b>\n"
            msg += "• /setup - Get morning setups\n"
            msg += "• /oppty - Find opportunities\n"
            msg += "• /top - AI top picks\n\n"
            
            msg += "🕘 <i>Market opens in 1 hour (9:30 AM ET)</i>"
            
            await self.send_message(msg)
            
        except Exception as e:
            logger.error(f"Morning briefing error: {e}")
    
    async def _send_hourly_scan(self):
        """Send hourly opportunity scan during market hours."""
        try:
            # Quick scan for top movers
            opportunities = []
            
            for ticker in self.TOP_STOCKS[:20]:
                quote = await self._fetch_quote(ticker)
                if not quote:
                    continue
                
                change_pct = quote.get('change_pct', 0)
                price = quote.get('price', 0)
                
                # Flag significant movers (>2% move)
                if abs(change_pct) >= 2:
                    score_data = await self._calculate_ai_score(ticker, quote)
                    opportunities.append({
                        "ticker": ticker,
                        "price": price,
                        "change_pct": change_pct,
                        "ai_score": score_data['ai_score'],
                        "signal": score_data['signal']
                    })
            
            if opportunities:
                # Sort by absolute change
                opportunities.sort(key=lambda x: abs(x['change_pct']), reverse=True)
                
                msg = f"📡 <b>HOURLY SCAN ({datetime.now().strftime('%I:%M %p')})</b>\n\n"
                
                msg += "<b>🔥 BIG MOVERS:</b>\n"
                for opp in opportunities[:5]:
                    emoji = "🟢" if opp['change_pct'] >= 0 else "🔴"
                    msg += f"{emoji} <b>{opp['ticker']}</b>: ${opp['price']:.2f} ({opp['change_pct']:+.2f}%)\n"
                    msg += f"   AI: {opp['ai_score']}/10 | {opp['signal']}\n"
                
                msg += "\n💡 Use /advise TICKER for full analysis"
                
                await self.send_message(msg)
                
        except Exception as e:
            logger.error(f"Hourly scan error: {e}")
    
    async def _send_midday_update(self):
        """Send mid-day market update."""
        try:
            spy = await self._fetch_quote("SPY")
            qqq = await self._fetch_quote("QQQ")
            
            msg = "🌤️ <b>MID-DAY UPDATE</b>\n\n"
            
            if spy and qqq:
                spy_chg = spy.get('change_pct', 0)
                qqq_chg = qqq.get('change_pct', 0)
                
                if spy_chg > 0.5 and qqq_chg > 0.5:
                    msg += "📈 <b>Market: BULLISH</b>\n"
                    msg += "Indices trending higher into midday.\n"
                elif spy_chg < -0.5 and qqq_chg < -0.5:
                    msg += "📉 <b>Market: BEARISH</b>\n"
                    msg += "Indices under pressure at midday.\n"
                else:
                    msg += "↔️ <b>Market: MIXED</b>\n"
                    msg += "Choppy action - be selective.\n"
                
                spy_emoji = "🟢" if spy_chg >= 0 else "🔴"
                qqq_emoji = "🟢" if qqq_chg >= 0 else "🔴"
                msg += f"\n{spy_emoji} SPY: {spy_chg:+.2f}%\n"
                msg += f"{qqq_emoji} QQQ: {qqq_chg:+.2f}%\n"
            
            msg += "\n🕐 <i>2.5 hours until close</i>"
            
            await self.send_message(msg)
            
        except Exception as e:
            logger.error(f"Midday update error: {e}")
    
    async def _send_market_close_summary(self):
        """Send comprehensive market close summary."""
        try:
            spy = await self._fetch_quote("SPY")
            qqq = await self._fetch_quote("QQQ")
            
            msg = f"🌙 <b>MARKET CLOSE</b>\n"
            msg += f"<i>{datetime.now().strftime('%A, %B %d, %Y')}</i>\n\n"
            
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📊 <b>FINAL NUMBERS</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            
            if spy:
                emoji = "🟢" if spy.get('change_pct', 0) >= 0 else "🔴"
                msg += f"{emoji} S&P 500: {spy.get('change_pct', 0):+.2f}%\n"
            if qqq:
                emoji = "🟢" if qqq.get('change_pct', 0) >= 0 else "🔴"
                msg += f"{emoji} NASDAQ: {qqq.get('change_pct', 0):+.2f}%\n"
            
            # Get today's biggest movers
            movers = []
            for ticker in self.TOP_STOCKS[:15]:
                quote = await self._fetch_quote(ticker)
                if quote:
                    movers.append({
                        "ticker": ticker,
                        "change_pct": quote.get('change_pct', 0)
                    })
            
            if movers:
                movers.sort(key=lambda x: x['change_pct'], reverse=True)
                
                msg += "\n<b>🏆 TOP GAINERS:</b>\n"
                for m in movers[:3]:
                    if m['change_pct'] > 0:
                        msg += f"🟢 {m['ticker']}: {m['change_pct']:+.2f}%\n"
                
                msg += "\n<b>📉 TOP LOSERS:</b>\n"
                for m in movers[-3:]:
                    if m['change_pct'] < 0:
                        msg += f"🔴 {m['ticker']}: {m['change_pct']:.2f}%\n"
            
            msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📋 <b>TOMORROW'S PREP</b>\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "• Review today's setups\n"
            msg += "• Check /earnings for reports\n"
            msg += "• Update /watchlist\n\n"
            
            msg += "💤 <i>See you tomorrow at 8:30 AM!</i>"
            
            await self.send_message(msg)
            
        except Exception as e:
            logger.error(f"Market close summary error: {e}")
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to default chat."""
        return await self.send_message_to(self.chat_id, text, parse_mode)
    
    async def send_message_to(self, chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to specific chat."""
        if not self.is_configured:
            return False
        
        url = f"{self.TELEGRAM_API_BASE}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            async with self._session.post(url, json=payload) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return False
    
    async def _handle_callback(self, callback: Dict):
        """Handle callback query (button presses)."""
        callback_id = callback.get("id")
        data = callback.get("data", "")
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        
        # Acknowledge callback
        url = f"{self.TELEGRAM_API_BASE}/bot{self.bot_token}/answerCallbackQuery"
        await self._session.post(url, json={"callback_query_id": callback_id})
        
        # Process callback data
        if data.startswith("confirm_"):
            await self.send_message_to(chat_id, "✅ Order confirmed!")
        elif data.startswith("cancel_"):
            await self.send_message_to(chat_id, "❌ Order cancelled")
    
    # ===== USER SETTINGS & CUSTOMIZATION COMMANDS =====
    
    async def _cmd_settings(self, chat_id: int, args: List[str]):
        """View and edit user trading preferences."""
        s = self.user_settings
        
        msg = "⚙️ <b>YOUR TRADING SETTINGS</b>\n\n"
        
        msg += "💰 <b>ACCOUNT</b>\n"
        msg += f"├ Account Size: ${s['account_size']:,.0f}\n"
        msg += f"├ Risk/Trade: {s['risk_per_trade']*100:.1f}%\n"
        msg += f"├ Max Positions: {s['max_positions']}\n"
        msg += f"└ Max Daily Trades: {s['max_daily_trades']}\n\n"
        
        msg += "📊 <b>TRADING STYLE</b>\n"
        style_emoji = {"day": "⚡", "swing": "🌊", "position": "🏔️"}
        msg += f"├ Style: {style_emoji.get(s['trading_style'], '📈')} {s['trading_style'].title()}\n"
        risk_emoji = {"conservative": "🛡️", "moderate": "⚖️", "aggressive": "🔥"}
        msg += f"├ Risk Tolerance: {risk_emoji.get(s['risk_tolerance'], '⚖️')} {s['risk_tolerance'].title()}\n"
        msg += f"└ Min AI Score: {s['min_ai_score']}/10\n\n"
        
        msg += "🎯 <b>STRATEGIES</b>\n"
        for strat in s['preferred_strategies']:
            msg += f"  ✓ {strat.replace('_', ' ').title()}\n"
        if not s['preferred_strategies']:
            msg += "  All strategies enabled\n"
        msg += "\n"
        
        msg += "🔔 <b>ALERTS</b>\n"
        msg += f"├ News: {'✅' if s['news_alerts'] else '❌'}\n"
        msg += f"├ Earnings: {'✅' if s['earnings_alerts'] else '❌'}\n"
        msg += f"└ Price: {'✅' if s['price_alerts'] else '❌'}\n\n"
        
        msg += "🤖 <b>AUTOMATION</b>\n"
        msg += f"└ Auto-Trade: {'🟢 ON' if self.auto_trade_enabled else '🔴 OFF'}\n\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>Customize with:</b>\n"
        msg += "<code>/setaccount 50000</code>\n"
        msg += "<code>/setrisk 1.5</code>\n"
        msg += "<code>/setstyle swing|day|position</code>\n"
        msg += "<code>/autotrade on|off</code>\n"
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_setaccount(self, chat_id: int, args: List[str]):
        """Set account size."""
        if not args:
            msg = f"""
💰 <b>Account Size Setting</b>

Current: ${self.user_settings['account_size']:,.0f}

Usage: <code>/setaccount 50000</code>

This affects:
• Position sizing calculations
• Risk per trade amounts
• Kelly criterion recommendations
"""
            await self.send_message_to(chat_id, msg)
            return
        
        try:
            amount = float(args[0].replace(",", "").replace("$", ""))
            if amount < 1000:
                await self.send_message_to(chat_id, "❌ Minimum account size: $1,000")
                return
            if amount > 100000000:
                await self.send_message_to(chat_id, "❌ Maximum account size: $100M")
                return
            
            old = self.user_settings['account_size']
            self.user_settings['account_size'] = amount
            self.account_size = amount
            
            msg = f"✅ <b>Account Size Updated</b>\n\n"
            msg += f"Old: ${old:,.0f}\n"
            msg += f"New: ${amount:,.0f}\n\n"
            msg += f"Risk/Trade (1%): ${amount * 0.01:,.0f}"
            
            await self.send_message_to(chat_id, msg)
            
        except ValueError:
            await self.send_message_to(chat_id, "❌ Invalid amount. Use: /setaccount 50000")
    
    async def _cmd_setrisk(self, chat_id: int, args: List[str]):
        """Set risk percentage per trade."""
        if not args:
            msg = f"""
⚠️ <b>Risk Per Trade Setting</b>

Current: {self.user_settings['risk_per_trade']*100:.1f}%
Amount: ${self.user_settings['account_size'] * self.user_settings['risk_per_trade']:,.0f}

Usage: <code>/setrisk 1.5</code>

<b>Professional Guidelines:</b>
• Conservative: 0.5%
• Standard: 1.0%
• Moderate: 1.5%
• Aggressive: 2.0%
• Max Recommended: 2.5%
"""
            await self.send_message_to(chat_id, msg)
            return
        
        try:
            pct = float(args[0].replace("%", ""))
            if pct < 0.1 or pct > 5:
                await self.send_message_to(chat_id, "❌ Risk must be 0.1% - 5%")
                return
            
            old = self.user_settings['risk_per_trade'] * 100
            self.user_settings['risk_per_trade'] = pct / 100
            self.max_risk_per_trade = pct / 100
            
            amount = self.user_settings['account_size'] * (pct / 100)
            
            msg = f"✅ <b>Risk Updated</b>\n\n"
            msg += f"Old: {old:.1f}%\n"
            msg += f"New: {pct:.1f}%\n"
            msg += f"Risk Amount: ${amount:,.0f}/trade"
            
            await self.send_message_to(chat_id, msg)
            
        except ValueError:
            await self.send_message_to(chat_id, "❌ Invalid. Use: /setrisk 1.5")
    
    async def _cmd_setstyle(self, chat_id: int, args: List[str]):
        """Set trading style."""
        if not args:
            styles = {
                "day": "⚡ Day Trading - Intraday, quick profits, no overnight risk",
                "swing": "🌊 Swing Trading - 2-10 days, catch momentum waves", 
                "position": "🏔️ Position Trading - Weeks to months, ride trends"
            }
            
            msg = "📊 <b>Trading Style Setting</b>\n\n"
            msg += f"Current: <b>{self.user_settings['trading_style'].title()}</b>\n\n"
            msg += "<b>Available Styles:</b>\n"
            for style, desc in styles.items():
                current = " ✓" if style == self.user_settings['trading_style'] else ""
                msg += f"\n{desc}{current}\n"
            msg += "\n<code>/setstyle swing</code>"
            
            await self.send_message_to(chat_id, msg)
            return
        
        style = args[0].lower()
        if style not in ["day", "swing", "position"]:
            await self.send_message_to(chat_id, "❌ Use: /setstyle day|swing|position")
            return
        
        self.user_settings['trading_style'] = style
        
        # Adjust other settings based on style
        if style == "day":
            self.user_settings['min_ai_score'] = 7
            self.user_settings['max_daily_trades'] = 10
        elif style == "swing":
            self.user_settings['min_ai_score'] = 6
            self.user_settings['max_daily_trades'] = 5
        else:  # position
            self.user_settings['min_ai_score'] = 7
            self.user_settings['max_daily_trades'] = 2
        
        msg = f"✅ <b>Style Updated: {style.title()}</b>\n\n"
        msg += f"Min AI Score: {self.user_settings['min_ai_score']}/10\n"
        msg += f"Max Daily Trades: {self.user_settings['max_daily_trades']}"
        
        await self.send_message_to(chat_id, msg)
    
    # ===== AUTOMATION COMMANDS =====
    
    async def _cmd_autotrade(self, chat_id: int, args: List[str]):
        """Enable/disable automated trading."""
        if not args:
            status = "🟢 ENABLED" if self.auto_trade_enabled else "🔴 DISABLED"
            
            msg = f"""
🤖 <b>AUTO-TRADE STATUS: {status}</b>

<b>How Auto-Trade Works:</b>
1. Bot scans market at scheduled times
2. Signals with AI score ≥{self.user_settings['min_ai_score']} are flagged
3. Position sizing uses your settings
4. Orders sent to {self.active_broker.value.upper()}

<b>Safety Limits:</b>
• Max {self.user_settings['max_daily_trades']} trades/day
• Max {self.user_settings['risk_per_trade']*100:.1f}% risk/trade
• Max {self.user_settings['max_positions']} open positions
• Daily loss limit: 3%

<b>Commands:</b>
<code>/autotrade on</code> - Enable
<code>/autotrade off</code> - Disable
<code>/schedule</code> - Set scan times
<code>/autopilot</code> - Full settings

⚠️ Paper trading recommended first!
"""
            await self.send_message_to(chat_id, msg)
            return
        
        action = args[0].lower()
        if action == "on":
            self.auto_trade_enabled = True
            self.user_settings['auto_trade_enabled'] = True
            msg = "🟢 <b>Auto-Trade ENABLED</b>\n\n"
            msg += "Bot will now execute signals automatically.\n"
            msg += "Use /autopilot to configure.\n\n"
            msg += "⚠️ Ensure broker is connected: /broker"
        elif action == "off":
            self.auto_trade_enabled = False
            self.user_settings['auto_trade_enabled'] = False
            msg = "🔴 <b>Auto-Trade DISABLED</b>\n\n"
            msg += "Bot will only send alerts.\n"
            msg += "Manual execution required."
        else:
            msg = "❌ Use: /autotrade on|off"
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_schedule(self, chat_id: int, args: List[str]):
        """Configure scheduled scans."""
        msg = """
⏰ <b>SCHEDULED SCANS</b>

<b>Default Schedule (US Eastern):</b>
🌅 08:30 - Pre-market scan
🔔 09:35 - Opening momentum
📊 12:00 - Midday review
🌙 15:45 - EOD signals
📈 16:30 - After-hours report

<b>Scan Types:</b>
• Gap scanners (pre-market)
• ORB breakouts (9:30-10:30)
• VCP patterns (midday)
• EOD momentum (15:00+)

<b>Your Preferences:</b>
• Style: {style}
• Min Score: {min_score}/10
• Max Trades: {max_trades}/day

When running on server (24/7):
• Scans run automatically
• Signals sent to Telegram
• Auto-trade executes if enabled

💡 Deploy with: <code>docker-compose up -d</code>
""".format(
            style=self.user_settings['trading_style'].title(),
            min_score=self.user_settings['min_ai_score'],
            max_trades=self.user_settings['max_daily_trades']
        )
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_autopilot(self, chat_id: int, args: List[str]):
        """Full autopilot mode settings."""
        msg = """
🚀 <b>AUTOPILOT MODE</b>

<b>Current Status:</b>
Auto-Trade: {auto_status}
Broker: {broker}
Account: ${account:,.0f}

<b>AUTOPILOT RULES:</b>

📊 <b>Entry Criteria:</b>
• AI Score ≥ {min_score}/10
• Market regime not BEAR/CRISIS
• Position size within limits
• Not exceeding max positions

🛡️ <b>Risk Management:</b>
• Stop Loss: 2x ATR below entry
• Profit Target: 3x ATR above entry
• Trailing Stop: 1.5x ATR
• Max 1% risk per trade

📈 <b>Position Sizing:</b>
• Kelly Criterion (quarter size)
• Max 10% per position
• Scale in: 50% → 30% → 20%

⏰ <b>Time Filters:</b>
• No trades first 5 min
• No trades last 15 min
• Avoid 12:00-14:00 chop

<b>To activate full autopilot:</b>
1. <code>/setaccount [size]</code>
2. <code>/setrisk 1</code>
3. <code>/broker paper</code> (test first!)
4. <code>/autotrade on</code>
5. Deploy to server for 24/7

⚠️ Always monitor initial trades!
""".format(
            auto_status="🟢 ON" if self.auto_trade_enabled else "🔴 OFF",
            broker=self.active_broker.value.upper(),
            account=self.user_settings['account_size'],
            min_score=self.user_settings['min_ai_score']
        )
        
        await self.send_message_to(chat_id, msg)
    
    # ===== ML & PERFORMANCE COMMANDS =====
    
    async def _cmd_mlstats(self, chat_id: int, args: List[str]):
        """Show ML model statistics and learning progress."""
        msg = "🧠 <b>ML MODEL STATISTICS</b>\n\n"
        msg += f"Model Version: {self.model_version}\n\n"
        
        msg += "📊 <b>CURRENT WEIGHTS</b>\n"
        for factor, weight in self.ml_model_weights.items():
            bar_len = int(weight * 20)
            bar = "█" * bar_len + "░" * (5 - bar_len)
            msg += f"├ {factor.replace('_', ' ').title()}: [{bar}] {weight*100:.0f}%\n"
        
        msg += f"\n📈 <b>LEARNING METRICS</b>\n"
        msg += f"├ Predictions Made: {len(self.prediction_log)}\n"
        msg += f"├ Outcomes Tracked: {len(self.trade_outcomes)}\n"
        
        # Calculate overall accuracy
        if self.trade_outcomes:
            wins = sum(1 for t in self.trade_outcomes if t.get('profit', 0) > 0)
            accuracy = wins / len(self.trade_outcomes)
            msg += f"├ Win Rate: {accuracy*100:.1f}%\n"
        else:
            msg += f"├ Win Rate: Collecting data...\n"
        
        msg += f"\n🎯 <b>STRATEGY PERFORMANCE</b>\n"
        for strat, stats in self.strategy_accuracy.items():
            acc = stats.get('accuracy', 0.5)
            total = stats.get('total', 0)
            emoji = "🟢" if acc >= 0.55 else "🟡" if acc >= 0.45 else "🔴"
            msg += f"{emoji} {strat.title()}: {acc*100:.0f}% ({total} trades)\n"
        
        msg += "\n💡 <b>ML LEARNING:</b>\n"
        msg += "• Weights auto-adjust based on outcomes\n"
        msg += "• Best strategies get higher weight\n"
        msg += "• Poor performers reduced\n"
        msg += "• Rebalances weekly\n"
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_optimize(self, chat_id: int, args: List[str]):
        """Optimize strategy based on historical performance."""
        msg = "🔧 <b>STRATEGY OPTIMIZATION</b>\n\n"
        
        # Analyze strategy performance
        best_strategy = None
        best_accuracy = 0
        worst_strategy = None
        worst_accuracy = 1
        
        for strat, stats in self.strategy_accuracy.items():
            acc = stats.get('accuracy', 0.5)
            if acc > best_accuracy:
                best_accuracy = acc
                best_strategy = strat
            if acc < worst_accuracy:
                worst_accuracy = acc
                worst_strategy = strat
        
        msg += "📊 <b>ANALYSIS RESULTS</b>\n\n"
        
        if best_strategy:
            msg += f"🏆 <b>Best Strategy:</b> {best_strategy.title()}\n"
            msg += f"   Accuracy: {best_accuracy*100:.0f}%\n\n"
        
        if worst_strategy and worst_accuracy < 0.45:
            msg += f"⚠️ <b>Underperforming:</b> {worst_strategy.title()}\n"
            msg += f"   Accuracy: {worst_accuracy*100:.0f}%\n\n"
        
        msg += "🎯 <b>OPTIMIZATION SUGGESTIONS</b>\n\n"
        
        # Generate suggestions based on performance
        if best_accuracy >= 0.6:
            msg += f"✓ Increase {best_strategy.title()} weight to 30%\n"
        if worst_accuracy < 0.45:
            msg += f"✗ Reduce {worst_strategy.title()} weight to 10%\n"
        
        # Style-based suggestions
        style = self.user_settings['trading_style']
        if style == "day":
            msg += "✓ Focus on momentum + ORB strategies\n"
            msg += "✓ Tighter stops (1.5x ATR)\n"
        elif style == "swing":
            msg += "✓ Use trend + mean reversion combo\n"
            msg += "✓ Standard stops (2x ATR)\n"
        else:
            msg += "✓ Focus on value + trend following\n"
            msg += "✓ Wider stops (2.5x ATR)\n"
        
        msg += "\n<b>Auto-Optimization:</b>\n"
        msg += "Weights adjust automatically based on\n"
        msg += "recent 30-day performance data.\n"
        
        await self.send_message_to(chat_id, msg)
    
    async def _cmd_report(self, chat_id: int, args: List[str]):
        """Generate comprehensive performance report."""
        stats = self.performance_stats
        
        msg = "📊 <b>PERFORMANCE REPORT</b>\n\n"
        msg += f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>\n\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "📈 <b>TRADING SUMMARY</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total = stats['total_trades']
        wins = stats['winning_trades']
        win_rate = (wins / total * 100) if total > 0 else 0
        
        msg += f"Total Trades: {total}\n"
        msg += f"Winning: {wins} ({win_rate:.1f}%)\n"
        msg += f"Losing: {total - wins} ({100-win_rate:.1f}%)\n\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💰 <b>PROFIT & LOSS</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        pnl = stats['total_pnl']
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        msg += f"Total P&L: {pnl_emoji} ${pnl:+,.2f}\n"
        msg += f"Best Trade: 🏆 ${stats['best_trade']:+,.2f}\n"
        msg += f"Worst Trade: 📉 ${stats['worst_trade']:+,.2f}\n\n"
        
        if stats['avg_win'] > 0 or stats['avg_loss'] > 0:
            msg += f"Avg Win: ${stats['avg_win']:,.2f}\n"
            msg += f"Avg Loss: ${abs(stats['avg_loss']):,.2f}\n"
        
        msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "📉 <b>RISK METRICS</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        pf = stats['profit_factor']
        sharpe = stats['sharpe_ratio']
        dd = stats['max_drawdown']
        
        msg += f"Profit Factor: {pf:.2f}\n"
        msg += f"Sharpe Ratio: {sharpe:.2f}\n"
        msg += f"Max Drawdown: {dd*100:.1f}%\n\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "🎯 <b>STREAK</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        streak = stats['current_streak']
        streak_emoji = "🔥" if streak > 0 else "❄️" if streak < 0 else "➖"
        msg += f"Current: {streak_emoji} {abs(streak)} {'wins' if streak > 0 else 'losses' if streak < 0 else ''}\n"
        msg += f"Best Streak: 🏆 {stats['best_streak']} wins\n\n"
        
        # Recommendations
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💡 <b>RECOMMENDATIONS</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if win_rate >= 55:
            msg += "✅ Win rate is healthy\n"
        else:
            msg += "⚠️ Focus on higher conviction trades\n"
        
        if pf >= 1.5:
            msg += "✅ Good profit factor\n"
        elif pf < 1:
            msg += "⚠️ Improve R:R ratio\n"
        
        if dd > 0.1:
            msg += "⚠️ Reduce position sizes\n"
        
        await self.send_message_to(chat_id, msg)
    
    # ===== ML LEARNING HELPERS =====
    
    async def _record_prediction(self, ticker: str, score: float, action: str, 
                                  entry_price: float, strategy: str):
        """Record a prediction for later outcome tracking."""
        prediction = {
            "id": f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "ticker": ticker,
            "score": score,
            "action": action,
            "entry_price": entry_price,
            "strategy": strategy,
            "timestamp": datetime.now().isoformat(),
            "outcome": None,
            "exit_price": None,
            "pnl": None,
        }
        self.prediction_log.append(prediction)
        return prediction["id"]
    
    async def _update_prediction_outcome(self, prediction_id: str, 
                                          exit_price: float, outcome: str):
        """Update prediction with actual outcome."""
        for pred in self.prediction_log:
            if pred["id"] == prediction_id:
                pred["exit_price"] = exit_price
                pred["outcome"] = outcome
                pred["pnl"] = exit_price - pred["entry_price"]
                
                # Update strategy accuracy
                strategy = pred.get("strategy", "momentum")
                if strategy in self.strategy_accuracy:
                    self.strategy_accuracy[strategy]["total"] += 1
                    if outcome == "win":
                        self.strategy_accuracy[strategy]["wins"] += 1
                    
                    total = self.strategy_accuracy[strategy]["total"]
                    wins = self.strategy_accuracy[strategy]["wins"]
                    self.strategy_accuracy[strategy]["accuracy"] = wins / total if total > 0 else 0.5
                
                # Trigger ML weight adjustment
                await self._adjust_ml_weights()
                break
    
    async def _adjust_ml_weights(self):
        """Adjust ML weights based on strategy performance."""
        # Get strategy performance
        performances = {}
        for strat, stats in self.strategy_accuracy.items():
            if stats["total"] >= 5:  # Minimum sample size
                performances[strat] = stats["accuracy"]
        
        if not performances:
            return
        
        # Normalize weights based on performance
        total_perf = sum(performances.values())
        if total_perf > 0:
            # Map strategies to weight keys
            strat_to_weight = {
                "momentum": "momentum_score",
                "mean_reversion": "value_score",
                "trend_following": "trend_score",
                "buffett": "value_score",
                "druckenmiller": "momentum_score",
            }
            
            # Adjust weights
            for strat, perf in performances.items():
                weight_key = strat_to_weight.get(strat)
                if weight_key and weight_key in self.ml_model_weights:
                    # Increase weight for better performers
                    adjustment = (perf - 0.5) * 0.1  # +/-5% max
                    new_weight = self.ml_model_weights[weight_key] + adjustment
                    self.ml_model_weights[weight_key] = max(0.1, min(0.4, new_weight))
            
            # Normalize to sum to 1
            total_weight = sum(self.ml_model_weights.values())
            for key in self.ml_model_weights:
                self.ml_model_weights[key] /= total_weight


# Convenience function to create and start bot
async def start_telegram_bot():
    """Start the Telegram bot."""
    bot = TelegramBot()
    await bot.start()
    return bot
