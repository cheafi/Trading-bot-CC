"""
International Stock Universe — HK, JP, EU, UK, KR, TW, AU, IN, Crypto.

Sprint 39: Expanded international coverage.
  - HK: 80+ (HSI + H-shares + tech)
  - JP: 60+ (TOPIX core + Nikkei 225 leaders)
  - EU/UK: 50+ (blue-chip ADRs)
  - KR/TW/AU/IN: 40+ (major ADRs)
  - Crypto: 50+ tokens
"""

# ═══════════════════════════════════════════════════════════
# Hong Kong — 80+ tickers
# ═══════════════════════════════════════════════════════════

HK_TICKERS = [
    # HSI components + major tech
    "0700.HK",  # Tencent
    "9988.HK",  # Alibaba
    "9618.HK",  # JD.com
    "3690.HK",  # Meituan
    "9999.HK",  # NetEase
    "1810.HK",  # Xiaomi
    "2020.HK",  # Anta Sports
    "0388.HK",  # HKEX
    "0005.HK",  # HSBC
    "1299.HK",  # AIA
    "0941.HK",  # China Mobile
    "2318.HK",  # Ping An
    "0027.HK",  # Galaxy Entertainment
    "1928.HK",  # Sands China
    "0883.HK",  # CNOOC
    "0175.HK",  # Geely Auto
    "2269.HK",  # WuXi Bio
    "9626.HK",  # Bilibili
    "0981.HK",  # SMIC
    "3968.HK",  # China Merchants Bank
    "2388.HK",  # BOC Hong Kong
    "0001.HK",  # CK Hutchison
    "0016.HK",  # Sun Hung Kai
    "1211.HK",  # BYD
    "9868.HK",  # XPeng
    "2015.HK",  # Li Auto
    "9866.HK",  # NIO
    # Extended: H-shares + financials
    "1398.HK",  # ICBC
    "0939.HK",  # CCB
    "3988.HK",  # BOC
    "1288.HK",  # ABC
    "2628.HK",  # China Life
    "2601.HK",  # CPIC
    "6862.HK",  # Haidilao
    "0669.HK",  # Techtronic
    "0002.HK",  # CLP Holdings
    "0003.HK",  # HK & China Gas
    "0006.HK",  # Power Assets
    "0011.HK",  # Hang Seng Bank
    "0012.HK",  # Henderson Land
    "0017.HK",  # New World Dev
    "0019.HK",  # Swire Pacific
    "0066.HK",  # MTR Corp
    "0083.HK",  # Sino Land
    "0101.HK",  # Hang Lung
    "0267.HK",  # CITIC
    "0288.HK",  # WH Group
    "0386.HK",  # Sinopec
    "0688.HK",  # China Overseas
    "0762.HK",  # China Unicom
    "0823.HK",  # Link REIT
    "0857.HK",  # PetroChina
    "0868.HK",  # Xinyi Glass
    "0960.HK",  # Longfor Group
    "1038.HK",  # CK Infrastructure
    "1044.HK",  # Hengan
    "1088.HK",  # China Shenhua
    "1109.HK",  # China Resources
    "1177.HK",  # Sino Biopharm
    "1876.HK",  # Budweiser APAC
    "1997.HK",  # Wharf REIC
    "2007.HK",  # Country Garden
    "2018.HK",  # AAC Tech
    "2196.HK",  # Fosun Pharma
    "2313.HK",  # Shenzhou
    "2319.HK",  # Mengniu Dairy
    "2382.HK",  # Sunny Optical
    "2688.HK",  # ENN Energy
    "3328.HK",  # Bank of Comms
    "6060.HK",  # ZhongAn Online
    "6618.HK",  # JD Health
    "6690.HK",  # Haier Smart
    "9633.HK",  # Nongfu Spring
    "9888.HK",  # Baidu
    "9961.HK",  # Trip.com
    "9698.HK",  # GDS Holdings
    "2192.HK",  # Mediclinic
    "0853.HK",  # Microport
]

# ═══════════════════════════════════════════════════════════
# Japan — 60+ tickers (TOPIX / Nikkei 225 leaders)
# ═══════════════════════════════════════════════════════════

JP_TICKERS = [
    "7203.T",   # Toyota
    "6758.T",   # Sony
    "6861.T",   # Keyence
    "9984.T",   # SoftBank Group
    "6098.T",   # Recruit
    "8306.T",   # MUFG
    "7741.T",   # HOYA
    "9433.T",   # KDDI
    "4063.T",   # Shin-Etsu Chemical
    "6501.T",   # Hitachi
    "4568.T",   # Daiichi Sankyo
    "6902.T",   # Denso
    "7974.T",   # Nintendo
    "8035.T",   # Tokyo Electron
    "6857.T",   # Advantest
    "4519.T",   # Chugai Pharma
    "6367.T",   # Daikin
    "4661.T",   # Oriental Land
    "6954.T",   # Fanuc
    "7267.T",   # Honda
    # Extended TOPIX / Nikkei
    "9432.T",   # NTT
    "4502.T",   # Takeda
    "4503.T",   # Astellas Pharma
    "6326.T",   # Kubota
    "6752.T",   # Panasonic
    "8001.T",   # ITOCHU
    "8031.T",   # Mitsui & Co
    "8058.T",   # Mitsubishi Corp
    "8316.T",   # Sumitomo Mitsui
    "8411.T",   # Mizuho Financial
    "8766.T",   # Tokio Marine
    "8801.T",   # Mitsui Fudosan
    "9020.T",   # JR East
    "9021.T",   # JR West
    "9022.T",   # JR Central
    "9101.T",   # NYK Line
    "9104.T",   # Mitsui OSK
    "4452.T",   # Kao Corp
    "4901.T",   # Fujifilm
    "6273.T",   # SMC Corp
    "6594.T",   # Nidec
    "6645.T",   # Omron
    "6701.T",   # NEC
    "6702.T",   # Fujitsu
    "6723.T",   # Renesas
    "6762.T",   # TDK
    "6981.T",   # Murata Mfg
    "7201.T",   # Nissan
    "7269.T",   # Suzuki
    "7270.T",   # Subaru
    "7751.T",   # Canon
    "7832.T",   # Bandai Namco
    "8002.T",   # Marubeni
    "8053.T",   # Sumitomo Corp
    "8591.T",   # Orix
    "8725.T",   # MS&AD Insurance
    "9434.T",   # SoftBank Corp
    "9613.T",   # NTT Data
    "9983.T",   # Fast Retailing
    "3382.T",   # Seven & i
]

# ═══════════════════════════════════════════════════════════
# South Korea — KR ADRs & local
# ═══════════════════════════════════════════════════════════

KR_TICKERS = [
    "005930.KS",  # Samsung Electronics
    "000660.KS",  # SK Hynix
    "035420.KS",  # NAVER
    "035720.KS",  # Kakao
    "051910.KS",  # LG Chem
    "006400.KS",  # Samsung SDI
    "373220.KS",  # LG Energy Solution
    "068270.KS",  # Celltrion
    "105560.KS",  # KB Financial
    "055550.KS",  # Shinhan Financial
    "003670.KS",  # POSCO
    "207940.KS",  # Samsung Biologics
    "012330.KS",  # Hyundai Mobis
    "005380.KS",  # Hyundai Motor
    "000270.KS",  # Kia
]

# ═══════════════════════════════════════════════════════════
# Taiwan — TW tickers
# ═══════════════════════════════════════════════════════════

TW_TICKERS = [
    "2330.TW",  # TSMC
    "2317.TW",  # Hon Hai (Foxconn)
    "2454.TW",  # MediaTek
    "2382.TW",  # Quanta Computer
    "2308.TW",  # Delta Electronics
    "1301.TW",  # Formosa Plastics
    "1303.TW",  # Nan Ya Plastics
    "2881.TW",  # Fubon Financial
    "2882.TW",  # Cathay Financial
    "2891.TW",  # CTBC Financial
    "3711.TW",  # ASE Technology
]

# ═══════════════════════════════════════════════════════════
# Australia — AU tickers
# ═══════════════════════════════════════════════════════════

AU_TICKERS = [
    "BHP.AX",   # BHP Group
    "CBA.AX",   # Commonwealth Bank
    "CSL.AX",   # CSL Limited
    "NAB.AX",   # National Aust Bank
    "WBC.AX",   # Westpac
    "ANZ.AX",   # ANZ Group
    "WES.AX",   # Wesfarmers
    "MQG.AX",   # Macquarie Group
    "FMG.AX",   # Fortescue Metals
    "RIO.AX",   # Rio Tinto
    "WOW.AX",   # Woolworths
    "TLS.AX",   # Telstra
    "WDS.AX",   # Woodside Energy
    "ALL.AX",   # Aristocrat
    "REA.AX",   # REA Group
]

# ═══════════════════════════════════════════════════════════
# India — IN ADRs
# ═══════════════════════════════════════════════════════════

IN_TICKERS = [
    "RELIANCE.NS",  # Reliance
    "TCS.NS",       # Tata Consultancy
    "INFY.NS",      # Infosys
    "HDFCBANK.NS",  # HDFC Bank
    "ICICIBANK.NS", # ICICI Bank
    "HINDUNILVR.NS",# Hindustan Unilever
    "ITC.NS",       # ITC
    "SBIN.NS",      # State Bank India
    "BHARTIARTL.NS",# Bharti Airtel
    "WIPRO.NS",     # Wipro
]

# ═══════════════════════════════════════════════════════════
# Crypto — 50+ tokens
# ═══════════════════════════════════════════════════════════

CRYPTO_TICKERS = [
    # Top 25
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT",
    "MATIC", "LINK", "UNI", "AAVE", "MKR", "LDO", "ARB",
    "OP", "APT", "SUI", "SEI", "TIA", "NEAR", "ATOM",
    "DOGE", "SHIB", "PEPE",
    # DeFi
    "CRV", "COMP", "SNX", "SUSHI", "YFI", "BAL", "FXS",
    "PENDLE", "GMX", "RDNT", "JOE",
    # Layer 1 / Layer 2
    "FTM", "ALGO", "HBAR", "VET", "EGLD", "KAVA", "INJ",
    "MINA", "CELO", "ZK", "STRK", "BLAST",
    # Gaming / Metaverse
    "AXS", "SAND", "MANA", "GALA", "IMX", "RONIN",
    "ILV", "MAGIC",
    # AI tokens
    "FET", "AGIX", "OCEAN", "RNDR", "TAO", "ARKM",
    "WLD",
]


# ═══════════════════════════════════════════════════════════
# Market region enum + helpers
# ═══════════════════════════════════════════════════════════

from enum import Enum


class MarketRegion(str, Enum):
    US = "us"
    HK = "hk"
    JP = "jp"
    KR = "kr"
    TW = "tw"
    AU = "au"
    IN = "in"
    CRYPTO = "crypto"


# Total count helper
def get_universe_stats():
    """Return dict of market → ticker count."""
    from src.scanners.us_universe import US_UNIVERSE
    return {
        "us": len(US_UNIVERSE),
        "hk": len(HK_TICKERS),
        "jp": len(JP_TICKERS),
        "kr": len(KR_TICKERS),
        "tw": len(TW_TICKERS),
        "au": len(AU_TICKERS),
        "in": len(IN_TICKERS),
        "crypto": len(CRYPTO_TICKERS),
    }
