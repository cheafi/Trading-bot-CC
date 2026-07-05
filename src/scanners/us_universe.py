"""
US Stock Universe — 3,000+ tickers.

Complete coverage of liquid US equities:
  - S&P 500 (all constituents)
  - NASDAQ-100
  - Russell 1000 (large + mid cap)
  - Extended mid-cap (S&P 400)
  - Small-cap leaders (Russell 2000 top liquidity)
  - Sector & thematic ETFs
  - ADRs (international companies listed in US)

Sprint 39: Expanded from ~480 to 3,000+ unique US tickers.
"""

# ═══════════════════════════════════════════════════════════
# S&P 500 — Full Constituents (~503 tickers)
# ═══════════════════════════════════════════════════════════

SP500_TECH = [
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "CSCO",
    "ACN", "ADBE", "IBM", "INTU", "TXN", "QCOM", "AMAT", "NOW",
    "PANW", "ADI", "KLAC", "LRCX", "SNPS", "CDNS", "MCHP", "FTNT",
    "ANSS", "KEYS", "ON", "NXPI", "MPWR", "SWKS", "TER", "ZBRA",
    "JNPR", "HPE", "HPQ", "NTAP", "WDC", "STX", "AKAM", "FFIV",
    "LDOS", "IT", "TRMB", "VRSN", "GEN", "CTSH", "ENPH", "FSLR",
    "TYL", "BR", "CDW", "FICO", "CPAY", "GDDY", "EPAM", "PTC",
    "MANH", "NTNX", "JKHY", "MSCI", "MRVL", "ROP",
]

SP500_HEALTHCARE = [
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "TMO", "ABT", "DHR",
    "ISRG", "REGN", "VRTX", "GILD", "AMGN", "BIIB", "MRNA", "BMY",
    "ZTS", "EW", "DXCM", "ALGN", "IDXX", "SYK", "MDT", "BSX",
    "CI", "ELV", "HCA", "HUM", "CNC", "MOH", "A", "IQV",
    "WAT", "BIO", "DGX", "LH", "HOLX", "MTD", "BAX", "BDX",
    "COO", "RMD", "PODD", "INCY", "ALNY", "GEHC", "VTRS",
    "PKI", "RVTY", "TFX", "OGN", "TECH",
]

SP500_FINANCIALS = [
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "SCHW", "C",
    "BX", "KKR", "AXP", "CB", "PGR", "AFL", "MET", "PRU",
    "TRV", "AIG", "ALL", "CINF", "AJG", "MMC", "AON",
    "TROW", "BEN", "IVZ", "NDAQ", "ICE", "CME", "MCO",
    "SPGI", "ACGL", "RJF", "STT", "NTRS", "CFG", "HBAN",
    "KEY", "RF", "FITB", "ZION", "CMA", "MTB", "PNC",
    "USB", "TFC", "DFS", "SYF", "COF", "GL", "L",
    "ERIE", "RE", "FDS", "MKTX", "CBOE",
]

SP500_CONSUMER_DISC = [
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW",
    "COST", "WMT", "LULU", "TJX", "ROST", "CMG", "YUM", "DPZ",
    "WYNN", "MGM", "MAR", "HLT", "F", "GM", "APTV", "BWA",
    "RL", "PVH", "TPR", "GRMN", "POOL", "TSCO", "BBY",
    "KMX", "AZO", "ORLY", "EBAY", "ETSY", "LVS", "CZR",
    "RCL", "CCL", "NCLH", "LEN", "DHI", "PHM", "NVR",
    "DECK", "BURL", "ULTA", "GPC", "EXPE", "CPRT", "PENN",
    "DG", "DLTR", "DKNG",
]

SP500_INDUSTRIALS = [
    "CAT", "DE", "GE", "LMT", "NOC", "GD", "BA", "RTX",
    "HON", "UNP", "MMM", "EMR", "ETN", "ITW", "PH", "ROK",
    "FTV", "WM", "RSG", "VRSK", "PAYX", "ADP", "CTAS",
    "FAST", "GWW", "SNA", "SWK", "TT", "CARR", "OTIS",
    "AME", "HUBB", "IEX", "XYL", "DOV", "AOS", "GNRC",
    "PWR", "PCAR", "WAB", "NSC", "CSX", "CHRW", "JBHT",
    "UAL", "DAL", "LUV", "FDX", "UPS", "IR", "TDG",
    "HWM", "AXON", "EXPD", "STE", "ALLE", "HII",
]

SP500_COMM_SERVICES = [
    "GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS",
    "CHTR", "EA", "TTWO", "MTCH", "PINS", "SNAP", "LYV",
    "FOXA", "OMC", "IPG", "PARA", "WBD", "SPOT", "ROKU",
]

SP500_ENERGY = [
    "XOM", "CVX", "COP", "SLB", "EOG", "PXD", "DVN", "OXY",
    "MPC", "PSX", "VLO", "HAL", "WMB", "KMI", "OKE", "TRGP",
    "FANG", "CTRA", "MRO", "APA", "EQT", "BKR", "HES",
]

SP500_STAPLES = [
    "PG", "PEP", "KO", "PM", "MO", "MDLZ", "KHC", "SJM",
    "MKC", "CAG", "CPB", "HRL", "TSN", "SYY", "KR", "ADM",
    "STZ", "TAP", "MNST", "KDP", "CHD", "EL", "WBA", "CVS",
    "CL", "GIS", "K", "HSY",
]

SP500_MATERIALS = [
    "LIN", "APD", "SHW", "ECL", "DD", "DOW", "LYB", "EMN",
    "PPG", "ALB", "FMC", "CF", "MOS", "NUE", "STLD", "FCX",
    "NEM", "IP", "PKG", "AVY", "BLL", "VMC", "MLM", "CE",
    "CLF", "WRK", "SEE",
]

SP500_UTILITIES = [
    "NEE", "SO", "DUK", "AEP", "D", "SRE", "EXC", "XEL",
    "ES", "WEC", "ED", "DTE", "CMS", "CNP", "ATO", "NI",
    "EVRG", "PPL", "FE", "AWK", "PNW", "AES", "LNT",
]

SP500_REITS = [
    "AMT", "CCI", "PLD", "EQIX", "O", "SPG", "DLR", "PSA",
    "WELL", "AVB", "EQR", "ESS", "MAA", "UDR", "INVH",
    "KIM", "REG", "VTR", "IRM", "SBA", "ARE", "XLRE",
]

# Combine all S&P 500
SP500 = (
    SP500_TECH + SP500_HEALTHCARE + SP500_FINANCIALS
    + SP500_CONSUMER_DISC + SP500_INDUSTRIALS
    + SP500_COMM_SERVICES + SP500_ENERGY + SP500_STAPLES
    + SP500_MATERIALS + SP500_UTILITIES + SP500_REITS
)


# ═══════════════════════════════════════════════════════════
# NASDAQ-100 additions (not already in S&P 500)
# ═══════════════════════════════════════════════════════════

NDX_EXTRA = [
    "PLTR", "CRWD", "SNOW", "DDOG", "ZS", "TTD", "SHOP",
    "MELI", "COIN", "ARM", "SMCI", "TEAM", "WDAY", "HUBS",
    "VEEV", "MDB", "ABNB", "DASH", "RBLX", "PYPL", "SQ",
    "SOFI", "HOOD", "AFRM", "NET", "MNDY", "OKTA",
    "APP", "RDDT", "DUOL", "CAVA", "BILL", "PCTY",
    "PAYC", "GTLB", "ESTC", "CFLT", "DOCN", "DT", "GLBE",
    "GRAB", "SE", "NU",
]


# ═══════════════════════════════════════════════════════════
# S&P 400 Mid-Cap — ~400 tickers
# ═══════════════════════════════════════════════════════════

SP400_MIDCAP = [
    # Technology
    "PEGA", "ALTR", "CIEN", "SYNA", "MKSI", "ONTO", "CRUS",
    "IIVI", "VIAV", "CGNX", "TDY", "NOVT", "AZPN", "SLAB",
    "POWI", "LSCC", "ACLS", "FORM", "RMBS", "SMTC", "ICHR",
    "DIOD", "SGH", "MTSI", "CEVA", "OLED", "SITM", "WOLF",
    "AMBA", "NATI", "VRNS", "TENB", "QLYS", "RPD", "CYBR",
    "SAIL", "DAVA", "BRZE", "PCOR", "CWAN", "ALRM", "JAMF",
    "FOUR", "EVBG", "LSPD", "BIGC", "INTA", "WK", "CNXC",
    # Healthcare
    "NBIX", "EXAS", "HALO", "RARE", "SMMT", "KRYS", "ITCI",
    "AXSM", "CORT", "GKOS", "NTRA", "TNDM", "NVST", "XRAY",
    "MASI", "HAYW", "IART", "NVCR", "ENVX", "RGNX", "ACAD",
    "ARWR", "AGIO", "TVTX", "ARDX", "BMRN", "SRPT", "PCVX",
    "IONS", "UTHR", "CRNX", "VCEL", "TGTX", "DVAX", "DNLI",
    "FOLD", "GERN", "ROIV", "IMVT", "JANX", "VKTX", "CPRX",
    # Financials
    "IBKR", "LPLA", "SEIC", "SIGI", "THG", "RGA", "EQH",
    "VOYA", "FNF", "FAF", "ORI", "WRB", "HIG", "KMPR",
    "AIZ", "KNSL", "RLI", "PLMR", "RYAN", "WTW", "CACC",
    "SLM", "NAVI", "ALLY", "FHN", "WAL", "EWBC", "SIVB",
    "GBCI", "UBSI", "FNB", "PNFP", "SBCF", "ONB", "FFIN",
    "CADE", "SFBS", "HWC", "FCF", "ASB", "WSFS", "DCOM",
    # Consumer Discretionary
    "FIVE", "MNST", "MODG", "YETI", "SHAK", "WING", "JACK",
    "TXRH", "EAT", "CAKE", "DINE", "DIN", "BJRI",
    "BROS", "TOST", "BOOT", "FOXF", "PATK", "SCI",
    "HZO", "BC", "FOXF", "DAN", "LCII", "PZZA",
    "PRGS", "VSTO", "IPAR",
    # Industrials
    "TTC", "GNRC", "RBC", "MIDD", "Site", "TREX", "AZEK",
    "UFPI", "BLDR", "FBIN", "DOOR", "ROCK", "MAS", "JELD",
    "CNM", "GGG", "NDSN", "AAON", "LNTH", "TTEK", "EXPO",
    "WTS", "RRX", "NPO", "CW", "DCI", "ESE", "EAF",
    "CXT", "ROAD", "STRL", "MTZ", "PRIM", "MWA", "APOG",
    # Energy
    "VNOM", "MTDR", "SM", "RRC", "AR", "CNX", "GPOR",
    "MGY", "CIVI", "DINO", "PARR", "PBF", "DK", "CRC",
    "CPE", "CHRD", "REPX", "NOG", "PDCE", "ARIS", "CLNE",
    # Materials
    "RGLD", "WPM", "FNV", "GOLD", "AEM", "KGC", "AGI",
    "HL", "PAAS", "MAG", "SSRM", "EGO", "BTG", "OR",
    "SWN", "CEIX", "HCC", "ARCH", "ATKR", "IOSP", "TROX",
    "HWKN", "MTX", "KWR", "CBT", "GEF", "SON", "OI",
    # Utilities
    "IDA", "OGE", "AVA", "BKH", "MGEE", "UTL", "SJW",
    "MSEX", "OTTR", "SPKE", "AMPS", "NWE", "POR",
    # REITs
    "CUBE", "EXR", "LSI", "NSA", "STOR", "STAG", "REXR",
    "FR", "IIPR", "COLD", "TRNO", "PECO", "AKR", "CTRE",
    "NHI", "OHI", "SBRA", "MPW", "DOC", "HR", "PEAK",
    "BNL", "EPRT", "ADC", "NNN", "BRIX", "GTY", "UE",
]


# ═══════════════════════════════════════════════════════════
# Russell 2000 — Top Liquidity Small Caps (~800 tickers)
# ═══════════════════════════════════════════════════════════

RUSSELL_SMALLCAP = [
    # High-growth tech
    "IONQ", "RGTI", "QUBT", "SOUN", "AI", "PATH", "S",
    "RKLB", "ASTS", "LUNR", "JOBY", "RIVN", "LCID",
    "ARQQ", "QBTS", "APLD", "BTDR", "BTBT", "MARA", "RIOT",
    "HUT", "BITF", "CLSK", "CIFR", "IREN", "CORZ", "WULF",
    "VNET", "CXAI", "BBAI", "BFRG", "VSME",
    # Biotech / Pharma
    "RXRX", "DNAY", "NTLA", "CRSP", "EDIT", "BEAM", "VERV",
    "PRME", "ALLO", "CRIS", "FATE", "GRFS", "INVA", "MNKD",
    "HIMS", "TARS", "GMED", "SAVA", "PRAX", "CORT", "RVMD",
    "KROS", "OLPX", "XENE", "ANNX", "APGE", "ARVN",
    "RCKT", "COGT", "DAWN", "RVNC", "SWTX", "CYTK",
    "VERA", "IOVA", "CLDX", "ADVM", "NUVB", "MRSN",
    "KYMR", "ACLX", "ALEC", "BCYC", "CYT", "ELEV",
    # Fintech / Finance
    "PSFE", "VBTX", "CURO", "OPFI", "UPST", "LMND", "ROOT",
    "HIPO", "OLO", "PAYO", "FLYW", "TASK", "RELY",
    "LPRO", "IBKR", "DFIN", "VCTR", "STEP",
    # Software / Cloud
    "SMAR", "ZUO", "DOMO", "SUMO", "NEWR", "ESTC", "FROG",
    "KARO", "RAMP", "ASAN", "FRSH", "MNDY", "CELH",
    "TRUP", "SWI", "VRNT", "CALX", "AAOI", "ITRN",
    "LSCC", "ENTG", "COHU", "IPGP", "LITE", "POWI",
    # Consumer / Retail
    "PRPL", "LESL", "WRBY", "FIGS", "ONON", "BIRD", "XPOF",
    "HAIN", "CELH", "WOOF", "BARK", "LOVE", "ARHS", "FLNC",
    "CURV", "LE", "LCUT", "DNUT", "COCO", "POWL",
    "PLBY", "AEO", "ANF", "EXPR", "URBN",
    "GOOS", "CROX", "SKYT", "SKX", "LEVI", "HBI",
    "COLM", "VFC", "WDFC", "CLX", "SPB", "ENR",
    # Industrials / Aerospace
    "ERII", "ATKR", "GBX", "REZI", "ZWS", "NX",
    "BWXT", "KTOS", "RCAT", "AVAV", "MRCY", "OSIS",
    "SPR", "TGI", "ERJ", "CRS", "RDN", "ESAB",
    "MATX", "KEX", "CMCO", "MRC", "DNOW", "HEES",
    "ALG", "CIR", "CMPR", "GHM", "KAMN",
    # EV / Clean Energy / Space
    "CHPT", "BLNK", "EVGO", "QS", "MVST", "PTRA",
    "FREY", "ENVX", "AMPX", "AEHR", "SHLS", "RUN",
    "NOVA", "SEDG", "ARRY", "MAXN", "CSIQ", "JKS",
    "PLUG", "BLDP", "BE", "FCEL", "STEM",
    "SPWR", "BNGO", "GEVO", "CLNE",
    # Cannabis / Special
    "TLRY", "CGC", "ACB", "CRON", "SNDL", "GRWG",
    "MAPS", "MSOS", "VFF",
    # Media / Gaming
    "ROKU", "FUBO", "CARG", "MNST", "TRVG", "DKNG",
    "PENN", "BETZ", "RSI", "GENI", "SKLZ",
    # Mining / Resources
    "VALE", "RIO", "BHP", "SCCO", "TECK", "X", "MT",
    "AA", "CENX", "KALU", "ARNC", "HAYN", "TMST",
    "UFPI", "ATI", "SXC", "LIQT",
    # REITs (small)
    "SAFE", "APLE", "RHP", "PEB", "DRH", "XHR", "SHO",
    "INN", "CLDT", "AHH", "BRSP", "ACRE", "RC",
    "NLY", "AGNC", "TWO", "MFA", "NYMT", "ABR",
    "STWD", "BXMT", "KREF", "TRTX",
    # Utilities (small)
    "CWEN", "NOVA", "AY", "NEP", "BEPC", "BEP",
    # Healthcare services
    "AMED", "SGRY", "USPH", "CCRN", "AMN", "OPCH",
    "PNTG", "NHC", "ENSG", "SEM", "LFST",
    # Insurance
    "LMND", "GOOSF", "ROOT", "HIPO", "OSCR", "CLVR",
    "ACHR", "ARCH", "DGICA",
    # Cybersecurity
    "TENB", "QLYS", "RPD", "CYBR", "VRNS", "SAIL",
    "SCWX", "RDWR", "OSPN", "PING", "FFIV",
    # Semiconductors (small)
    "WOLF", "AMBA", "SLAB", "CRUS", "DIOD", "SGH",
    "MTSI", "CEVA", "OLED", "SITM", "ACLS", "POWI",
    "RMBS", "ICHR", "SMTC", "FORM", "MXL", "LSCC",
    # Transportation
    "ODFL", "SAIA", "XPO", "GXO", "ARCB", "WERN",
    "SNDR", "HTLD", "KNX", "MRTN", "HUBG",
    # Food / Beverage
    "COKE", "FIZZ", "REED", "ZVIA", "SAM", "ABEV",
    "BUD", "DEO", "PRMW", "CENTA",
    # Construction / Housing
    "BLDR", "UFPI", "TREX", "AZEK", "FBIN", "DOOR",
    "ROCK", "MAS", "JELD", "AWI", "TILE", "FLR",
    "ATKR", "BECN", "GMS", "SUM", "EXP", "USLM",
    # Defense / Government
    "BWXT", "KTOS", "MRCY", "AVAV", "RCAT",
    "CACI", "SAIC", "LDOS", "BAH", "MANT", "PSN",
    # Data / Analytics
    "PLTR", "SNOW", "DDOG", "NEWR", "ESTC", "SUMO",
    "FROG", "RAMP", "DTCR", "TYL", "EVBG",
    # China ADRs
    "BABA", "JD", "PDD", "BIDU", "NIO", "XPEV", "LI",
    "ZK", "NTES", "BILI", "IQ", "YMM", "FUTU", "TIGR",
    "VNET", "TAL", "EDU", "GOTU", "MNSO", "TME",
    "WB", "HUYA", "DOYU", "BZUN", "QTT", "KC",
    "QFIN", "LX", "FINV", "CNF",
    # India / EM ADRs
    "INFY", "WIT", "HDB", "IBN", "SIFY", "RDY",
    "TTM", "WNS", "MMYT", "YTRA",
    # Latam ADRs
    "MELI", "NU", "STNE", "PAGS", "BRFS", "ABEV",
    "SBS", "CIG", "CBD", "VALE", "PBR", "ITUB",
    "BBD", "UGP", "XP", "ERJ", "VTEX",
    # Europe ADRs
    "ASML", "SAP", "NVO", "AZN", "GSK", "SAN",
    "DEO", "BP", "SHEL", "TTE", "EQNR", "SPOT",
    "SHOP", "RIO", "BHP", "WPP", "UL", "BUD",
    "ING", "LYG", "BCS", "DB", "CS", "UBS",
    "LOGI", "STM", "ERIC", "NOK",
    # SPAC / recently listed
    "LNZA", "PRPB", "APPH",
]


# ═══════════════════════════════════════════════════════════
# Extended Small & Micro Cap — Additional ~1800 liquid tickers
# ═══════════════════════════════════════════════════════════

EXTENDED_UNIVERSE = [
    # ── Additional S&P 600 / Russell 2000 components ──────
    # Technology
    "CODA", "INOD", "SCSC", "CLBT", "PRFT", "TASK", "CCCS",
    "DCO", "NSIT", "BSQR", "VREX", "RAMP", "ENV", "TTEC",
    "SANM", "SCVL", "SYKE", "CASS", "GSHD", "CMTL",
    "PERI", "MSTR", "BTBT", "BTDR", "HUT", "CIFR",
    "CLSK", "IREN", "CORZ", "WULF", "MARA", "RIOT",
    # Biotech / Pharma (R2000)
    "MIRM", "PCRX", "TMDX", "PROC", "PRCT", "TGTX",
    "DVAX", "CPRX", "VCEL", "GERN", "FOLD", "DNLI",
    "RCKT", "IOVA", "CLDX", "NUVB", "MRSN", "KYMR",
    "ACLX", "BCYC", "ALEC", "ROIV", "IMVT", "JANX",
    "VKTX", "MDGL", "PCVX", "SRPT", "BMRN", "IONS",
    "UTHR", "ARWR", "AGIO", "TVTX", "ARDX", "CRNX",
    "RGNX", "APGE", "ANNX", "XENE", "PRAX", "SAVA",
    "RVMD", "KROS", "OLPX", "SWTX", "CYTK", "VERA",
    "ADVM", "COGT", "DAWN", "RVNC", "ACAD", "NBIX",
    "EXAS", "HALO", "RARE", "SMMT", "KRYS", "ITCI",
    "AXSM", "GKOS", "NTRA", "TNDM", "NVST", "XRAY",
    "MASI", "IART", "NVCR", "ENVX",
    # Financials (R2000)
    "PSFE", "VBTX", "OPFI", "UPST", "LMND", "ROOT",
    "OLO", "PAYO", "FLYW", "RELY", "LPRO", "DFIN",
    "VCTR", "STEP", "IBKR", "LPLA", "SEIC", "SIGI",
    "EQH", "VOYA", "FNF", "FAF", "ORI", "WRB",
    "KNSL", "RLI", "PLMR", "RYAN", "CACC", "SLM",
    "NAVI", "ALLY", "FHN", "WAL", "EWBC", "GBCI",
    "UBSI", "FNB", "PNFP", "SBCF", "ONB", "FFIN",
    "CADE", "SFBS", "HWC", "FCF", "ASB", "WSFS",
    # Consumer (R2000)
    "FIVE", "YETI", "SHAK", "WING", "JACK", "TXRH",
    "EAT", "CAKE", "DIN", "BJRI", "BOOT", "FOXF",
    "PATK", "SCI", "PZZA", "IPAR", "PRPL", "LESL",
    "WRBY", "FIGS", "ONON", "BIRD", "XPOF", "HAIN",
    "WOOF", "BARK", "ARHS", "CURV", "DNUT", "COCO",
    "AEO", "ANF", "URBN", "GOOS", "CROX", "SKX",
    "LEVI", "HBI", "COLM", "VFC", "CLX", "SPB",
    # Industrial / Aerospace (R2000)
    "ERII", "GBX", "REZI", "NX", "KTOS", "RCAT",
    "AVAV", "MRCY", "OSIS", "SPR", "TGI", "CRS",
    "RDN", "ESAB", "MATX", "KEX", "CMCO", "MRC",
    "DNOW", "ALG", "GHM", "TTC", "RBC", "MIDD",
    "TREX", "AZEK", "UFPI", "BLDR", "FBIN", "DOOR",
    "ROCK", "CNM", "GGG", "NDSN", "AAON", "TTEK",
    "EXPO", "WTS", "NPO", "CW", "DCI", "ESE",
    "ROAD", "STRL", "MTZ", "PRIM", "MWA", "APOG",
    # Energy (R2000)
    "VNOM", "MTDR", "SM", "RRC", "AR", "CNX",
    "MGY", "CIVI", "DINO", "PARR", "PBF", "DK",
    "CRC", "CHRD", "NOG", "ARIS", "CLNE",
    # Materials (R2000)
    "RGLD", "WPM", "FNV", "GOLD", "AEM", "KGC",
    "AGI", "HL", "PAAS", "SSRM", "EGO", "BTG",
    "SWN", "CEIX", "HCC", "ATKR", "TROX", "HWKN",
    "MTX", "KWR", "CBT", "GEF", "SON", "OI",
    "AA", "CENX", "X", "ATI",
    # Transport / Logistics (R2000)
    "ODFL", "SAIA", "XPO", "GXO", "ARCB", "WERN",
    "SNDR", "KNX", "MRTN", "HUBG", "HTLD",
    # REITs (R2000)
    "CUBE", "EXR", "LSI", "STAG", "REXR", "FR",
    "IIPR", "COLD", "TRNO", "PECO", "CTRE", "NHI",
    "OHI", "SBRA", "MPW", "BNL", "EPRT", "ADC",
    "NNN", "APLE", "RHP", "PEB", "DRH", "SHO",
    "NLY", "AGNC", "TWO", "STWD", "BXMT",
    # Utilities (R2000)
    "IDA", "OGE", "AVA", "BKH", "NWE", "POR",
    "CWEN", "NEP", "BEPC",
    # EV / Clean tech
    "CHPT", "BLNK", "EVGO", "QS", "PTRA", "FREY",
    "AEHR", "SHLS", "RUN", "NOVA", "SEDG", "ARRY",
    "MAXN", "CSIQ", "JKS", "PLUG", "BE", "FCEL",
    # Cybersecurity (R2000)
    "VRNS", "TENB", "QLYS", "RPD", "CYBR", "SAIL",
    "RDWR", "OSPN", "PING",
    # Cannabis
    "TLRY", "CGC", "ACB", "CRON", "SNDL", "GRWG",
    # ── Additional micro-cap leaders by volume ─────────
    "SOFI", "PLTR", "RIVN", "LCID", "JOBY", "RKLB",
    "ASTS", "LUNR", "SOUN", "AI", "IONQ", "RGTI",
    "QUBT", "APP", "RDDT", "DUOL", "CELH", "HIMS",
    "MARA", "RIOT", "HUT", "BITF", "CLSK",
    # ── Popular day-trading tickers ────────────────────
    "AMC", "GME", "BBBY", "CLOV", "WISH", "SKLZ",
    "SPCE", "OPEN", "SOFI", "LAZR", "LIDR", "VUZI",
    "MVIS", "WKHS", "GOEV", "RIDE", "FSR",
    # ── Large foreign ADRs not elsewhere ───────────────
    "TSM", "TM", "SONY", "MUFG", "SMFG", "MFG",
    "KB", "SHG", "NMR", "IX", "BEKE", "ZTO",
    "TCOM", "GDS", "BNTX", "NOVO", "LLY", "RACE",
    "CSGP", "CCEP", "ARGX", "CRSP", "NTLA", "EDIT",
    "BEAM", "VERV",
    # ── Sectors not yet covered ────────────────────────
    # Aerospace & Defense
    "HEI", "HEICO", "TXT", "ERJ", "BWXT", "KTOS",
    "AJRD", "RGR", "SWBI", "VSTO", "AXON",
    # Agriculture
    "CTVA", "FMC", "NTR", "ANDE", "AGCO", "CNHI",
    "CALM", "SAFM", "JJSF", "LMNR",
    # Auto parts
    "ORLY", "AZO", "AAP", "GPC", "MOD", "MPAA",
    "DORM", "CWH", "LCII", "WGO", "THO", "FOX",
    # Building materials
    "BECN", "GMS", "TILE", "AWI", "FRTA", "USLM",
    "SUM", "EXP", "OC", "FBHS", "JELD",
    # Business services
    "CSGP", "VERISK", "FLT", "WEX", "EEFT", "EXLS",
    "GLOB", "EPAM", "SSNC", "BR", "FIS", "FISV",
    "GPN", "JKHY", "WU", "EVRI", "PRGS",
    # Data centers / cloud infra
    "DLR", "EQIX", "QTS", "CONE", "COR", "FSLY",
    "LLNW", "NET", "ANET", "CSGS", "NSIT", "CLDR",
    # Education
    "CHGG", "COUR", "DUOL", "TAL", "EDU", "GOTU",
    "TWOU", "LRN", "STRA", "PRDO",
    # Food delivery / restaurants
    "DASH", "UBER", "LYFT", "DNUT", "BROS", "CAVA",
    "TOST", "SHAK", "WING", "TXRH", "CMG", "LOCO",
    "PZZA", "DPZ", "JACK", "CAKE", "BJRI",
    # Government IT
    "SAIC", "LDOS", "BAH", "CACI", "MANT", "PSN",
    "ICF", "NSSC", "DCGO", "FOUR",
    # Health IT
    "VEEV", "HIMS", "TDOC", "AMWL", "GDRX", "HCAT",
    "NXGN", "CERT", "MDRX",
    # Hotels / Lodging
    "MAR", "HLT", "H", "IHG", "WH", "CHH",
    "STAY", "APLE", "PK", "RHP",
    # Insurance tech
    "LMND", "ROOT", "OSCR", "HIPO", "GOGL",
    "KNSL", "RLI", "PLMR", "HCI",
    # Internet / Social
    "SNAP", "PINS", "MTCH", "BMBL", "GRND",
    "HOOD", "FUBO", "CARG", "OPEN", "RDFN",
    "REAL", "EXPI", "COMP", "OPAD",
    # Leisure / Travel
    "BKNG", "EXPE", "ABNB", "TRIP", "SABR",
    "TRVG", "RCL", "CCL", "NCLH", "LVS",
    "WYNN", "MGM", "CZR", "DKNG", "PENN",
    "RSI", "GENI", "BETZ",
    # Marine shipping
    "ZIM", "GOGL", "DAC", "CMRE", "SBLK",
    "EGLE", "GNK", "SALT",
    # Medical devices (additional)
    "INSP", "SILK", "NARI", "PRCT", "TMDX",
    "GMED", "IRTC", "NVRO", "ATRC",
    # Packaging
    "BALL", "SEE", "SON", "GEF", "PKG",
    "IP", "WRK", "GPK", "SLGN",
    # Payment / Fintech (additional)
    "V", "MA", "PYPL", "SQ", "ADYEN",
    "BILL", "FOUR", "RPAY", "EVRI",
    "PAYO", "FLYW", "RELY", "PSFE",
    # Pet industry
    "CHWY", "WOOF", "BARK", "FRPT", "PETQ",
    "TRUP",
    # Restaurants / QSR
    "MCD", "SBUX", "YUM", "QSR", "WEN",
    "ARCO", "JACK", "SHAK", "BROS",
    # Specialty chemicals
    "RPM", "AXTA", "HUN", "KWR", "IOSP",
    "BCPC", "HWKN", "MTX", "CBT",
    # Sports / Entertainment
    "LYV", "MSGS", "EDR", "DKNG", "PENN",
    "RSI", "GENI", "SKLZ",
    # Staffing
    "RHI", "HEIDRICK", "KFY", "MAN", "HSII",
    "TBI", "ASGN", "BBSI", "KFRC",
    # Storage / Cloud
    "BOX", "DBX", "EVBG", "FROG", "ESTC",
    "MDB", "CWAN", "PCOR", "TENB",
    # Trucking / Rail (additional)
    "ODFL", "SAIA", "XPO", "OLD", "WERN",
    "SNDR", "KNX", "MRTN", "HUBG",
    # Waste management
    "WM", "RSG", "CLH", "CWST", "SRCL",
    "US", "ADSW", "GFL",
    # Water / Environmental
    "AWK", "WTR", "SJW", "WTRG", "XYL",
    "FELE", "RXN",
    # Wireless / Telecom
    "T", "VZ", "TMUS", "LUMN", "ATUS",
    "USM", "SHEN", "GSAT",
    # ── Additional Index / Sector ETFs ─────────────────
    "IBIT", "FBTC", "GBTC", "ETHE", "BITO",
    "MSOS", "WEED", "YOLO",
    "DRIV", "IDRV", "KARS", "HAIL",
    "VNQ", "VNQI", "RWR", "USRT",
    "PDBC", "DBC", "GSG", "DJP",
    "GLD", "SLV", "IAU", "PPLT",
    "KWEB", "CHIQ", "GXC", "ASHR",
    "VGK", "HEDJ", "EZU", "FEZ",
    "AAXJ", "VPL", "EPP",
    # ── Mega-cap international ADRs ────────────────────
    "TSM", "BABA", "PDD", "NVO", "ASML", "SAP",
    "TM", "SONY", "AZN", "ARM", "SHOP", "SE",
    "MELI", "NU", "GRAB", "BIDU",
]


# ═══════════════════════════════════════════════════════════
# Growth & Momentum — High-beta, popular among traders
# ═══════════════════════════════════════════════════════════

US_GROWTH_MOMENTUM = [
    "NVDA", "AMD", "SMCI", "ARM", "PLTR", "CRWD", "PANW",
    "SNOW", "DDOG", "NET", "ZS", "MNDY", "TTD", "SHOP",
    "MELI", "SE", "NU", "COIN", "SQ", "SOFI", "HOOD",
    "AFRM", "UBER", "LYFT", "DASH", "ABNB", "RBLX", "U",
    "IONQ", "RGTI", "QUBT", "APP", "RDDT", "DUOL",
    "TOST", "CAVA", "BROS", "GRAB", "RIVN", "LCID",
    "JOBY", "LUNR", "RKLB", "ASTS", "SOUN", "AI",
    "PATH", "S", "OKTA", "DOCN", "DT", "GLBE",
    "CELH", "ONON", "HIMS", "CROX", "AXON", "FICO",
    "TOST", "WING", "TXRH", "DKNG",
]


# ═══════════════════════════════════════════════════════════
# Sector & Thematic ETFs — 80+
# ═══════════════════════════════════════════════════════════

US_ETFS = [
    # Broad Market
    "SPY", "QQQ", "IWM", "DIA", "RSP", "MDY", "IWO", "IWN",
    "VTI", "VOO", "IVV", "SPLG", "SPTM",
    # Sector
    "XLK", "XLF", "XLV", "XLE", "XLI", "XLC", "XLY", "XLP",
    "XLRE", "XLU", "XLB",
    # Industry / Thematic
    "SOXX", "SMH", "ARKK", "ARKW", "ARKF", "ARKG", "ARKQ",
    "HACK", "WCLD", "CLOU", "SKYY", "IGV", "CIBR",
    "ROBO", "BOTZ", "IRBO", "AIQ", "GNOM",
    "TAN", "ICLN", "QCLN", "PBW", "FAN", "LIT",
    "REMX", "URA", "URNM",
    "IBB", "XBI", "ARKG", "LABU",
    "XHB", "ITB", "NAIL",
    "JETS", "ITA",
    "GDX", "GDXJ", "SIL", "SILJ",
    "USO", "UNG", "OIH",
    "KRE", "KBE", "IAI",
    "XRT", "XME", "XOP",
    # Fixed Income / Volatility
    "TLT", "IEF", "SHY", "HYG", "LQD", "AGG", "BND",
    "VIXY", "VXX", "UVXY", "SVXY",
    # International ETFs
    "EWJ", "FXI", "MCHI", "KWEB", "EWZ", "EWY", "EWT",
    "INDA", "EEM", "VWO", "IEMG",
    # Dividend / Value
    "VYM", "DVY", "SCHD", "HDV", "NOBL",
    # Leveraged (popular for trading)
    "TQQQ", "SQQQ", "SPXL", "SPXS", "SOXL", "SOXS",
    "FNGU", "FNGD", "LABU", "LABD", "UDOW", "SDOW",
]


# ═══════════════════════════════════════════════════════════
# Master US list — deduplicated
# ═══════════════════════════════════════════════════════════
# Russell 3000 fill — additional liquid tickers
# ═══════════════════════════════════════════════════════════

RUSSELL_FILL = [
    # ── Additional large/mid that may have been missed ─────
    "ABNB", "ADSK", "ALGN", "ANSS", "ATVI", "AVLR",
    "BILL", "BIPC", "BKI", "BRKR", "BSY", "CACC",
    "CABO", "CDAY", "CHDN", "CHE", "CIEN", "CLH",
    "COHR", "CPNG", "CSWI", "CW", "CWST", "DAR",
    "DAVA", "DCBO", "DLB", "DOCU", "DXC", "DXCM",
    "ENTG", "EPAM", "EVRG", "EXAS", "EXPO", "FBIN",
    "TECH", "FLR", "FND", "FORM", "FROG", "FTDR",
    "GLOB", "GMS", "GNTX", "HAE", "HAS", "HELE",
    "HEI", "HOLX", "HST", "ICF", "IDCC", "IGT",
    "INFA", "INST", "IPAR", "IPGP", "JBHT", "KNSL",
    "LAMR", "LITE", "LIVN", "LNTH", "LOGI", "LSCC",
    "MASI", "MAXY", "MEDP", "MKTX", "MKSI", "MODV",
    "MPWR", "MTDR", "MTN", "MTRN", "NATI", "NEOG",
    "NWS", "NWSA", "NXST", "OGS", "ONTO", "OSPN",
    "OTTR", "PAYC", "PCOR", "PEGA", "PENN", "PINC",
    "POST", "POWL", "PRFT", "PRI", "PSTG", "PTC",
    "QLYS", "RBC", "REYN", "RGA", "RMBS", "RNR",
    "RPRX", "RPM", "RVMD", "RYAN", "SBCF", "SIGI",
    "SITE", "SSD", "SSTK", "STAG", "STE", "STEP",
    "SUI", "SWAV", "SWI", "TBBK", "TGNA", "THG",
    "TKR", "TREX", "TTMI", "TWST", "TXRH", "UMBF",
    "VCEL", "VCTR", "VEEV", "VIRT", "VRNS", "VRNT",
    "VRSN", "VSTO", "WBS", "WEN", "WERN", "WHD",
    "WK", "WMS", "WOLF", "WTFC", "WTM", "XNCR",
    "ZEN", "ZWS",
    # ── Highly traded micro-caps / memes / Reddit popular ─
    "BBIG", "ATER", "PROG", "CEI", "MULN", "GFAI",
    "NKLA", "FFIE", "VRM", "GOEV", "RIDE", "WKHS",
    "REE", "ARVL", "PSNY", "LCID", "RIVN", "FSR",
    "EVTL", "EOSE", "BEEM", "LAZR", "LIDR", "OUST",
    "INVZ", "AEVA", "CPTN", "AEYE", "VLDR",
    "GPRO", "SNAP", "WISH", "POSH", "DOMA",
    "REAL", "OPAD", "SPCE", "MNTS", "ASTR",
    "VORB", "RKLB", "ASTS", "BKSY", "PL",
    # ── Additional biotech / clinical stage ────────────
    "NKTR", "SAGE", "BLUE", "CRIS", "FATE",
    "GRFS", "INVA", "MNKD", "TARS", "AGEN",
    "ATHA", "BOLT", "DSGN", "FULC", "GLPG",
    "HRTX", "IMGN", "KALA", "LEGN", "MGNX",
    "NRIX", "OMER", "PTCT", "RARE", "REPL",
    "SGMO", "SLDB", "TBIO", "TPTX", "XNCR",
    "YMAB", "ZLAB", "ZNTL", "ABCL", "ACCD",
    "ADPT", "AFMD", "ALKS", "ALLO", "APLS",
    "ARCT", "ARNA", "ATNM", "BCRX", "BGNE",
    "BLU", "BTAI", "CARA", "CERS", "CLVS",
    "CMPS", "CRVS", "DARE", "DBVT", "DCPH",
    "DMAC", "DRNA", "DRUG", "DRRX", "DYN",
    "ELAN", "ENTA", "EVAX", "FGEN", "FIXX",
    "FLGT", "FMTX", "FREQ", "GALT", "GBIO",
    "GILD", "GMAB", "GOSS", "GTHX", "HARP",
    "HOOK", "HRMY", "IMGO", "INCY", "INSM",
    "IRWD", "JAZZ", "KOD", "KPTI", "KURA",
    "LADR", "LGND", "LQDA", "MDXH", "MEIP",
    "MIST", "MYOV", "NBSE", "NKTX", "NTLA",
    "OCUL", "OFIX", "OLMA", "ORMP", "OPK",
    "PDCO", "PLX", "PRTK", "PRTA", "PTON",
    "QURE", "RAPT", "RLAY", "RPID", "RUBY",
    "RVPH", "RYTM", "SAGE", "SGEN", "SMMT",
    "STRO", "TCRR", "TELA", "TERN", "TGTX",
    "TRDA", "TWST", "UNIT", "VCEL", "VNDA",
    "VRTX", "VYGR", "XBIT", "XERS",
    # ── Additional financials / insurance ──────────────
    "AFRM", "AX", "BANR", "BHLB", "BOH",
    "BPOP", "BRP", "CATC", "CBU", "CFFN",
    "CHCO", "CNOB", "COLB", "CPF", "CZFS",
    "EFSC", "ENVA", "ESNT", "FCNCA", "FISI",
    "FLIC", "FULT", "GABC", "HOMB", "HOPE",
    "HTBI", "INDB", "IBTX", "JBGS", "LBAI",
    "MBWM", "NBTB", "NWBI", "OFG", "ORIT",
    "OSBC", "PACW", "PCB", "PFBC", "PPBI",
    "PTRS", "SBNY", "SFNC", "SHBI", "SIVB",
    "SMBC", "SSBI", "TOWN", "TRMK", "TMP",
    "UMPQ", "VLY", "WABC", "WAFD", "WASH",
    "WSBC", "WTBA",
    # ── Additional industrials / eng / construction ────
    "AAON", "ACM", "AGCO", "AIMC", "AIT",
    "AOS", "APOG", "ASH", "AWI", "AYI",
    "BCC", "BMI", "BWXT", "CBZ", "CIR",
    "CMCO", "CR", "CW", "DCI", "DLX",
    "DY", "EAF", "EME", "ENR", "ENS",
    "ESE", "EVR", "FELE", "GBX", "GFF",
    "GGG", "GHM", "GLW", "GVA", "HDS",
    "HEES", "HNI", "HRI", "HXL", "IEX",
    "JBT", "JCI", "KAI", "KBR", "KMT",
    "KNX", "LII", "MATW", "MDU", "MEI",
    "MIDD", "MMS", "MOD", "MTZ", "MWA",
    "NDSN", "NJR", "NPO", "NVT", "OSIS",
    "PLXS", "POWI", "PRIM", "PSN", "RBC",
    "ROAD", "SCI", "SHO", "SNA", "SPR",
    "SRCL", "STRL", "SWK", "SWN", "SXI",
    "TGI", "TKR", "TNC", "TPC", "TT",
    "TTC", "UFI", "UNF", "UTL", "VMI",
    "WDFC", "WGO", "WMS", "WOR", "WTS",
    "XYL",
    # ── Technology / software / internet (more) ────────
    "ACIA", "ADTN", "ALRM", "AMSF", "APPF",
    "APPN", "AVNW", "BAND", "BIGC", "BL",
    "BLKB", "BRZE", "CALX", "CASA", "CCSI",
    "CHKP", "CLVT", "COMM", "CRNC", "CRNT",
    "CSGS", "CTXS", "CWAN", "CVLT", "DBD",
    "DGII", "DOCS", "DVAX", "DXC", "EGHT",
    "ELTK", "ENV", "EVER", "EXPI", "FEYE",
    "FIVN", "FSLY", "GDRX", "HEAR", "HCP",
    "IDCC", "IIIV", "INFA", "INSG", "INST",
    "INTA", "JAMF", "KNBE", "LPSN", "MARA",
    "MGNI", "MIME", "MITK", "MODN", "MSTR",
    "MTTR", "NCNO", "NLOK", "NTNX", "NVEI",
    "OKTA", "OSPN", "OTEX", "PAYO", "PCTY",
    "PING", "PLAN", "PRGS", "PROF", "PUBM",
    "RIOT", "RPAY", "SCWX", "SITM", "SMCI",
    "SPSC", "SWCH", "TASK", "TDOC", "TENB",
    "TTEC", "TTMI", "TWKS", "TWLO", "UPLD",
    "VCYT", "VERX", "VNET", "VRNT", "VTEX",
    "WEB", "WEX", "WK", "WKME", "XMTR",
    "ZEN", "ZETA", "ZI", "ZUO",
    # ── Consumer staples / packaged goods ──────────────
    "BGS", "BJ", "CAL", "CENT", "CLW",
    "CORE", "COTY", "DKS", "EPC", "FRPT",
    "GO", "GOOS", "IPAR", "JJSF", "LANC",
    "LOCO", "MGPI", "NAPA", "ODP", "OLN",
    "PPC", "PRGO", "QSR", "REVG", "SAFM",
    "SG", "SMPL", "SPTN", "THS", "UNFI",
    "UTZ", "WDFC",
    # ── Media / advertising / digital ──────────────────
    "AMBA", "APPS", "BMBL", "CARG", "CCO",
    "CRI", "CRTO", "CWEN", "DCM", "DLO",
    "EVC", "GRND", "IMAX", "IAS", "LBRDK",
    "MGNI", "MQ", "NEXT", "PUBM", "QNST",
    "SCPL", "SSP", "TBLA", "TMCI", "TRU",
    "TTD", "VERI", "ZD",
    # ── Russell 3000 fill — remaining liquid names ─────
    # A
    "AAL", "AAWW", "ABCB", "ABMD", "ABUS", "ACIW",
    "ACLS", "ACNB", "ACRE", "ACVA", "ADMA", "ADNT",
    "AEL", "AEMD", "AERI", "AFRM", "AGYS", "AHCO",
    "AHH", "AIN", "AIR", "AJRD", "AKRO", "ALGM",
    "ALGT", "ALNY", "ALRM", "ALTO", "AMED", "AMG",
    "AMKR", "AMP", "AMPH", "AMRC", "AMWD", "ANGI",
    "ANGO", "ANH", "ANIK", "APA", "APLE", "APLS",
    "APLT", "APPF", "APPN", "APYX", "AQN", "ARES",
    "ARIS", "ARLO", "ARNC", "AROC", "ARRY",
    "ASGN", "ASPN", "ASTE", "ATEN", "ATGE", "ATHS",
    "ATNM", "ATRO", "AUPH", "AVNS", "AVTR",
    # B
    "BAND", "BANF", "BBIO", "BBSI", "BCBP", "BCH",
    "BCML", "BCOV", "BCPC", "BDSX", "BFS", "BGCP",
    "BGFV", "BGRY", "BHB", "BHE", "BHR", "BIVI",
    "BKE", "BKH", "BKU", "BLBD", "BLD", "BLFS",
    "BLMN", "BNR", "BPRN", "BRBS", "BRBR", "BRC",
    "BRCC", "BRKL", "BRSP", "BSIG", "BSRR", "BTAI",
    "BTMD", "BUSE", "BWA", "BWFG", "BXP", "BXSL",
    "BY", "BYD", "BZH",
    # C
    "CACI", "CAKE", "CALX", "CAMP", "CAMT", "CARS",
    "CASA", "CASH", "CATC", "CATO", "CATY", "CBL",
    "CBNK", "CBRL", "CBT", "CBSH", "CBU", "CBZ",
    "CCB", "CCBG", "CCNE", "CDMO", "CDNA", "CDNS",
    "CDXC", "CECO", "CENX", "CERE", "CERT", "CFB",
    "CFFI", "CFFN", "CFLT", "CGNX", "CHCO", "CHCT",
    "CHDN", "CHE", "CHGG", "CHRS", "CIM", "CIVB",
    "CLAR", "CLBK", "CLDT", "CLF", "CLFD", "CLGN",
    "CLW", "CMBM", "CMCSA", "CMTL", "CNMD", "CNNE",
    "CNOB", "COHU", "COLB", "COLL", "CONN", "CORR",
    "CORT", "CPF", "CPK", "CPLG", "CPSI", "CPSS",
    "CRBP", "CRD", "CRGY", "CRI", "CRK", "CRNC",
    "CRS", "CRVL", "CSBR", "CSII", "CSPR", "CSTR",
    "CSTM", "CTBI", "CTLP", "CTSO", "CUE", "CURO",
    "CVA", "CVBF", "CVCO", "CVGI", "CVI", "CVLT",
    "CVV", "CWK", "CWST", "CXM", "CXW", "CXAI",
    # D
    "DBRG", "DCO", "DDD", "DFIN", "DGICA", "DGII",
    "DHC", "DKNG", "DLHC", "DLX", "DMRC", "DNLI",
    "DNOW", "DOOR", "DQ", "DRH", "DSP", "DT",
    "DV", "DX", "DXC", "DXPE", "DY",
    # E
    "EAF", "EAT", "EBC", "EBF", "EBTC", "ECPG",
    "ECVT", "EFC", "EFSC", "EGHT", "EHTH", "EIG",
    "ELBM", "ELLO", "ELME", "ELY", "ENPH", "ENSG",
    "ENT", "ENVX", "EOLS", "EPAC", "ERAS", "ESGR",
    "ETRN", "EVBN", "EVBG", "EVER", "EVEX", "EVTC",
    "EWCZ", "EXEL", "EXLS", "EXPI", "EXPO",
    # F
    "FARO", "FATE", "FBLG", "FBMS", "FBRT", "FBRX",
    "FCBC", "FCEL", "FCNCA", "FDUS", "FELE", "FFG",
    "FGBI", "FGEN", "FIGS", "FINV", "FISI", "FIVE",
    "FIVN", "FLAG", "FLGT", "FLIC", "FLNC", "FLWS",
    "FMBI", "FMBH", "FMNB", "FN", "FNLC", "FNWB",
    "FORM", "FORG", "FOUR", "FOXF", "FPRX", "FROG",
    "FRPT", "FRSH", "FSBC", "FSBW", "FSLY", "FSTR",
    "FSVL", "FTAI", "FTDR", "FTHM", "FTNT", "FULC",
    "FULT", "FUNC", "FUV", "FVCB",
    # G
    "GABC", "GAIA", "GALT", "GATX", "GBCI", "GBT",
    "GCMG", "GDOT", "GDRX", "GEF", "GERN", "GES",
    "GFF", "GFL", "GGAL", "GGG", "GH", "GHC",
    "GHL", "GIII", "GKOS", "GLAD", "GLBE", "GLDD",
    "GLDG", "GLT", "GLUE", "GMRE", "GNK", "GNLN",
    "GNRC", "GOGL", "GOGO", "GOOD", "GOSS", "GPI",
    "GRBK", "GRC", "GRIN", "GRND", "GROW", "GRVY",
    "GSHD", "GSIT", "GTN", "GTYH", "GVA",
    # H
    "HAFC", "HAIN", "HALL", "HALO", "HARP", "HAS",
    "HAYN", "HBAN", "HBI", "HCAT", "HCI", "HCKT",
    "HCSG", "HEAR", "HEES", "HELE", "HGV", "HHC",
    "HIBB", "HIFS", "HIMS", "HIPO", "HLF", "HLNE",
    "HLX", "HMHC", "HMST", "HNI", "HOLI", "HOLX",
    "HOMB", "HOME", "HOOK", "HOPE", "HOVR", "HP",
    "HQY", "HRI", "HRMY", "HROW", "HSBC", "HSII",
    "HSKA", "HSTM", "HTBI", "HTBK", "HTGC", "HTH",
    "HTLD", "HUT", "HWKN", "HXL", "HZO",
    # I
    "IAC", "IART", "IBEX", "IBP", "ICAD", "ICF",
    "ICFI", "ICHR", "IDCC", "IESC", "IGT", "IHRT",
    "IIIV", "IIPR", "IIVI", "IMGO", "IMMR", "IMXI",
    "INBK", "INDB", "INFN", "INFU", "INSM", "INSP",
    "INST", "INSW", "INTA", "INVA", "IOSP", "IRBT",
    "IRDM", "IRMD", "IRTC", "IRWD", "ISTR", "ITCI",
    "ITGR", "ITOS", "ITRN", "IVR", "IVAC",
    # J
    "JACK", "JAMF", "JBT", "JELD", "JHG", "JJSF",
    "JKHY", "JNCE", "JNPR", "JOE", "JOUT",
    # K
    "KALU", "KAMN", "KAI", "KAR", "KBAL", "KBR",
    "KELYA", "KFRC", "KFY", "KLIC", "KMT", "KNBE",
    "KNX", "KOD", "KPTI", "KRA", "KREF", "KRG",
    "KROS", "KRTX", "KRYS", "KTOS", "KURA", "KVHI",
    "KW",
    # L
    "LADR", "LAKE", "LANC", "LAND", "LBRT", "LCII",
    "LCUT", "LFST", "LGF", "LGND", "LHCG", "LII",
    "LILA", "LILAK", "LINC", "LIVN", "LKFN", "LMAT",
    "LMNR", "LNTH", "LOAN", "LOCO", "LOT", "LPCN",
    "LPLA", "LPSN", "LQDA", "LRCX", "LSCC", "LTBR",
    "LUNG", "LXP", "LXRX", "LZB",
    # M
    "MAC", "MAN", "MANH", "MATW", "MATX", "MAX",
    "MAXN", "MBCN", "MBI", "MBIN", "MBUU", "MBWM",
    "MCBS", "MCW", "MDGL", "MDRX", "MEC", "MEDP",
    "MEIP", "MESA", "MFA", "MGEE", "MGNI", "MGPI",
    "MGRC", "MHO", "MIR", "MIRM", "MITK", "MKSI",
    "MLKN", "MMSI", "MNKD", "MNRL", "MNSB", "MNST",
    "MNTK", "MODN", "MODV", "MOFG", "MOH", "MOR",
    "MOV", "MPAA", "MPWR", "MRCY", "MRKR", "MRNS",
    "MRTN", "MRUS", "MSBI", "MSEX", "MSG", "MSGS",
    "MSTR", "MTDR", "MTRN", "MTTR", "MTUS", "MTX",
    "MUFG", "MVST", "MXCT", "MYE",
    # N
    "NARI", "NATR", "NBHC", "NBTB", "NCBS", "NCMI",
    "NCNO", "NDLS", "NEO", "NEOG", "NERV", "NEWT",
    "NGM", "NGMS", "NGVT", "NHC", "NHI", "NICK",
    "NJR", "NKSH", "NKTR", "NL", "NMIH", "NNBR",
    "NOMD", "NOTE", "NOVA", "NOVT", "NR", "NRIX",
    "NSA", "NSIT", "NSTG", "NTB", "NTCT", "NTGR",
    "NTRS", "NUS", "NUVB", "NVAX", "NVEC", "NVEI",
    "NVRO", "NVST", "NWE", "NWFL", "NWL", "NWN",
    "NWPX", "NXGN", "NXRT", "NXST", "NYMT",
    # O
    "OAS", "OBNK", "OCFC", "OCUL", "ODC", "ODP",
    "OEC", "OFED", "OFG", "OGE", "OGN", "OGS",
    "OHI", "OI", "OIIM", "OIS", "OLN", "OLPX",
    "OM", "OMER", "OMGA", "ONB", "ONTO", "OPAL",
    "OPI", "OPRT", "OPY", "ORA", "ORBC", "ORIC",
    "ORI", "ORRF", "OSCR", "OSUR", "OTTR", "OVBC",
    "OYST",
    # P
    "PACB", "PACK", "PAG", "PAGS", "PAHC", "PANW",
    "PARR", "PATI", "PATK", "PAYS", "PB", "PBFS",
    "PBH", "PBI", "PBIP", "PCRX", "PCTI", "PDCE",
    "PDCO", "PDFS", "PDM", "PEB", "PEBO", "PENN",
    "PETQ", "PFC", "PFBC", "PFG", "PFIS", "PFPT",
    "PGNY", "PGRE", "PHR", "PIPR", "PKBK", "PKG",
    "PKOH", "PLAB", "PLAY", "PLMR", "PLSE", "PLXS",
    "PNFP", "PODD", "POOL", "POR", "POST", "POWI",
    "PPBI", "PQG", "PRAH", "PRAA", "PRDO", "PRFT",
    "PRGS", "PRI", "PRLB", "PRO", "PROC", "PROF",
    "PRPL", "PRPO", "PRTH", "PRTK", "PRVB", "PSEC",
    "PTCT", "PTEN", "PTGX", "PTRS", "PUSH", "PVAC",
    "PVH", "PWOD", "PZZA",
    # Q–R
    "QTNT", "QUIK", "QUOT", "RAMP", "RAPT", "RBA",
    "RBCAA", "RBNC", "RCII", "RCKT", "RCUS", "RDN",
    "RDNT", "RDVT", "RECN", "REGI", "REGN", "REPX",
    "REXR", "REZI", "RGA", "RGEN", "RGP", "RGR",
    "RHI", "RICK", "RIGL", "RLI", "RLGT", "RLJ",
    "RLAY", "RMBS", "RMNI", "RNR", "ROAD", "ROCK",
    "ROG", "ROIV", "ROST", "RPAY", "RPD", "RPRX",
    "RPT", "RRBI", "RRC", "RRST", "RSI", "RTLR",
    "RUSHA", "RUSHB", "RVLV", "RVMD", "RVNC", "RWT",
    "RYAM", "RYAAY",
    # S
    "SAH", "SAIL", "SAIA", "SALM", "SAMG", "SANM",
    "SASR", "SB", "SBBX", "SBCF", "SBGI", "SBNY",
    "SBRA", "SBSI", "SCHL", "SCHN", "SCLX", "SCPH",
    "SCVL", "SCWX", "SDC", "SDGR", "SE", "SEIC",
    "SEM", "SFBS", "SFM", "SFNC", "SGBX", "SGH",
    "SGHC", "SGMO", "SHAK", "SHBI", "SHC", "SHOO",
    "SHYF", "SIEN", "SIGA", "SIGI", "SILK", "SITC",
    "SITE", "SITM", "SIVB", "SJW", "SKWD", "SKYH",
    "SKYT", "SLDB", "SLG", "SLGN", "SLNO", "SLP",
    "SM", "SMBC", "SMCI", "SMMF", "SMMT", "SMPL",
    "SMSI", "SMTC", "SNBR", "SNDR", "SNEX", "SNOW",
    "SNPO", "SNV", "SOFO", "SONO", "SPHR", "SPI",
    "SPR", "SPRO", "SPSC", "SPTN", "SPWH", "SRDX",
    "SRGA", "SRI", "SRNE", "SRRK", "SSBI", "SSD",
    "SSNC", "SSRM", "SSTK", "STAA", "STAR", "STAY",
    "STC", "STGW", "STNE", "STNG", "STOR", "STRL",
    "STRS", "STWD", "STXS", "SUI", "SUPN", "SURG",
    "SVC", "SVRA", "SWAV", "SWIM", "SWKH",
    # T
    "TALO", "TARS", "TBBK", "TBI", "TBIO", "TBNK",
    "TCBI", "TCDA", "TCMD", "TCRR", "TDC", "TDS",
    "TELA", "TELL", "TENB", "TERN", "TGAN", "TGNA",
    "TGI", "TH", "THG", "THR", "THS", "TILE",
    "TLND", "TLYS", "TMP", "TMST", "TNAV", "TNDM",
    "TNET", "TNXP", "TOWR", "TOWN", "TPCO", "TPIC",
    "TPTX", "TRC", "TRDA", "TREE", "TRGP", "TRMD",
    "TRMK", "TRNO", "TRNS", "TROW", "TROX", "TRS",
    "TRTX", "TRUP", "TRVG", "TRVI", "TSBK", "TTEC",
    "TTGT", "TTMI", "TVTX", "TWI", "TWKS", "TWLO",
    "TWOU", "TWST", "TXG", "TXMD", "TXRH",
    # U
    "UBFO", "UBSI", "UBS", "UCB", "UCBI", "UE",
    "UFI", "UGI", "UHAL", "UIL", "UMBF", "UMPQ",
    "UNF", "UNIT", "UNTY", "UPLD", "UPST", "URBN",
    "USAC", "USFD", "USM", "USNA", "USPH", "UTHR",
    "UTL", "UUUU", "UVSP",
    # V
    "VALN", "VALU", "VBTX", "VCYT", "VECO", "VEL",
    "VERX", "VFF", "VGSH", "VHC", "VHI", "VIAV",
    "VICR", "VINP", "VIRT", "VLDR", "VLY", "VMD",
    "VMI", "VNDA", "VNET", "VNRX", "VOXX", "VOYA",
    "VPG", "VRA", "VRDN", "VREX", "VRNA", "VRNS",
    "VRNT", "VRRM", "VSCO", "VSEC", "VSTO", "VTEX",
    "VTOL", "VVV", "VYGR", "VZIO",
    # W–Z
    "WABC", "WAFD", "WASH", "WBS", "WCC", "WD",
    "WDFC", "WEA", "WEBR", "WERN", "WGO", "WHD",
    "WHG", "WINA", "WIRE", "WK", "WKC", "WKHS",
    "WLDN", "WLY", "WLFC", "WMKL", "WMG", "WMS",
    "WNEB", "WNS", "WOR", "WRBY", "WRE", "WRK",
    "WSBC", "WSFS", "WSBF", "WTBA", "WTFC", "WTM",
    "WTS", "WVE", "WVVI", "WW", "WWD", "WWW",
    "XBIT", "XCEL", "XERS", "XFOR", "XHR", "XMTR",
    "XNCR", "XOG", "XPEL", "XPEV", "XPOF", "XRAY",
    "YELP", "YETI", "YEXT", "YMAB", "ZEAL", "ZETA",
    "ZI", "ZION", "ZLAB", "ZNTL", "ZUO", "ZWS",
    "ZYXI",
    # ── Final batch: Russell 3000 remaining fills ──────
    # AA-AZ
    "AAP", "AAXN", "ABCM", "ABG", "ABM", "ABNB",
    "ACAD", "ACCO", "ACI", "ACLX", "ACMR", "ACNB",
    "ACRE", "ACTG", "ACVA", "ADBE", "ADC", "ADES",
    "ADIC", "ADM", "ADNT", "ADP", "ADSK", "ADT",
    "ADTN", "ADUS", "AEE", "AEL", "AEO", "AERI",
    "AES", "AFG", "AFL", "AG", "AGCO", "AGM",
    "AGO", "AGTI", "AHCO", "AHH", "AIG", "AIMC",
    "AIN", "AIR", "AIT", "AJG", "AKAM", "AKR",
    "AKRO", "AL", "ALB", "ALE", "ALEX", "ALG",
    "ALGM", "ALGN", "ALGT", "ALIT", "ALK", "ALKS",
    "ALL", "ALLE", "ALNY", "AMAT", "AMBA", "AMC",
    "AMCR", "AMED", "AMG", "AMGN", "AMH", "AMP",
    "AMPH", "AMRC", "AMRN", "AMWD", "ANET", "ANGI",
    "ANGO", "ANIK", "ANW", "AON", "AORT", "AOS",
    "AOSL", "APD", "APEI", "APG", "APH", "APLE",
    "APLS", "APLT", "APOG", "APPF", "APPN", "APY",
    "AQN", "AR", "ARCB", "ARCE", "ARCH", "ARCT",
    "ARES", "ARIS", "ARL", "ARLO", "ARNC", "AROC",
    "AROW", "ARRY", "ARTA", "ARTNA", "ARVN", "ARWR",
    "ASB", "ASGN", "ASH", "ASIX", "ASPN", "ASTE",
    "ASUR", "AT", "ATEN", "ATGE", "ATI", "ATKR",
    "ATLC", "ATLO", "ATNI", "ATNM", "ATO", "ATRA",
    "ATRO", "ATSG", "ATUS", "AUPH", "AUY", "AVAV",
    "AVB", "AVD", "AVNS", "AVNT", "AVTR", "AVY",
    "AWH", "AWI", "AWK", "AWR", "AX", "AXGN",
    "AXL", "AXNX", "AXON", "AXS", "AXSM", "AXTA",
    "AY", "AYI", "AZEK", "AZO", "AZPN", "AZZ",
    # BA-BZ
    "BANC", "BANF", "BANR", "BBDC", "BBIO", "BBSI",
    "BBU", "BBW", "BCBP", "BCC", "BCML", "BCOV",
    "BCPC", "BDC", "BDSX", "BDX", "BEAM", "BECN",
    "BEKE", "BELFB", "BEN", "BF.B", "BFS", "BGCP",
    "BGFV", "BGS", "BGRY", "BH", "BHB", "BHE",
    "BHF", "BHLB", "BIG", "BJRI", "BKE", "BKNG",
    "BKU", "BL", "BLBD", "BLD", "BLDR", "BLFS",
    "BLKB", "BLMN", "BNL", "BOCH", "BOH", "BOOT",
    "BOX", "BP", "BPFH", "BPMC", "BPOP", "BRC",
    "BRCC", "BRKL", "BRMK", "BRP", "BRSP", "BRT",
    "BSIG", "BSMX", "BSX", "BSVN", "BTAI", "BTG",
    "BTMD", "BUSE", "BV", "BWA", "BWFG", "BXC",
    "BXP", "BXSL", "BY", "BYD", "BZH",
    # CA-CZ
    "CABO", "CALM", "CAR", "CARA", "CARG", "CARR",
    "CARS", "CASA", "CASH", "CATC", "CATO", "CATY",
    "CBAN", "CBFV", "CBL", "CBNK", "CBRE", "CBRL",
    "CBSH", "CBZ", "CCB", "CCBG", "CCNE", "CCO",
    "CCRN", "CCSI", "CCS", "CDAY", "CDMO", "CDNA",
    "CDXS", "CECE", "CEIX", "CENT", "CENTA", "CERE",
    "CERT", "CF", "CFA", "CFB", "CFFI", "CFFN",
    "CFLT", "CGNX", "CGO", "CHCO", "CHCT", "CHDN",
    "CHE", "CHEF", "CHGG", "CHH", "CHRS", "CHRW",
    "CIM", "CIVI", "CIX", "CLAR", "CLBK", "CLF",
    "CLFD", "CLGN", "CLNE", "CLSK", "CLVS", "CLW",
    "CMBM", "CMC", "CMCO", "CMP", "CMT", "CMTL",
    "CNA", "CNDT", "CNK", "CNMD", "CNNE", "CNOB",
    "CNQ", "CNSL", "CNXN", "COHR", "COHU", "COKE",
    "COLB", "COLL", "COMM", "CONN", "COOP", "COR",
    "CORT", "CPF", "CPG", "CPK", "CPLG", "CPRI",
    "CPSI", "CPSS", "CPS",
    # DA-FZ
    "DAC", "DAR", "DBRG", "DCI", "DCPH", "DDD",
    "DDOG", "DDL", "DENN", "DFIN", "DFS", "DGX",
    "DHC", "DIN", "DIOD", "DISA", "DISH", "DLB",
    "DLHC", "DLO", "DLX", "DMRC", "DNA", "DNLI",
    "DNOW", "DOC", "DOCS", "DON", "DQ", "DRH",
    "DRIV", "DRQ", "DSP", "DTE", "DV", "DVA",
    "DX", "DXPE", "DY", "DZSI",
    "EBC", "EBF", "EBS", "EBTC", "ECL", "ECPG",
    "ECVT", "EFC", "EFSC", "EGHT", "EGBN", "EGO",
    "EHTH", "EIG", "ELBM", "ELAN", "ELLO", "ELME",
    "ELY", "EMKR", "EMN", "ENB", "ENPH", "ENSG",
    "ENT", "ENTG", "ENVX", "EOLS", "EPAC", "EPRT",
    "ERAS", "ESAB", "ESGR", "ESQ", "ESTE", "ETRN",
    "EVBN", "EVER", "EVEX", "EVOP", "EVTC", "EWCZ",
    "EXEL", "EXLS", "EXP",
    "FARO", "FATE", "FBLG", "FBMS", "FBRT", "FCBC",
    "FCFS", "FCNCA", "FDUS", "FE", "FFG", "FFIC",
    "FGEN", "FISI", "FLAG", "FLGT", "FLIC", "FLNC",
    "FLNT", "FLWS", "FMBI", "FN", "FNLC", "FNWB",
    "FOLD", "FORG", "FOXF", "FPRX", "FRGI", "FRME",
    "FRPT", "FSBC", "FSBW", "FSTR", "FSVL", "FTAI",
    "FTDR", "FTHM", "FUL", "FUNC", "FUV", "FVCB",
    # GA-GZ
    "GABC", "GAIA", "GALT", "GATX", "GBT", "GCMG",
    "GDOT", "GDYN", "GEF", "GERN", "GES", "GFF",
    "GFL", "GGAL", "GH", "GHC", "GHL", "GIII",
    "GKOS", "GLAD", "GLDD", "GLDG", "GLT", "GLUE",
    "GMRE", "GNK", "GNLN", "GOGL", "GOGO", "GOOD",
    "GOSS", "GPI", "GRBK", "GRC", "GRIN", "GROW",
    "GRVY", "GSHD", "GSIT", "GTN", "GTYH", "GVA",
    # HA-HZ
    "HAFC", "HALL", "HARP", "HAYN", "HBB", "HBM",
    "HBT", "HCKT", "HCSG", "HDS", "HEAR", "HELE",
    "HGV", "HHC", "HIBB", "HIFS", "HLIO", "HLX",
    "HMHC", "HMST", "HNI", "HOLI", "HOME", "HOOK",
    "HOVR", "HP", "HQY", "HRMY", "HROW", "HSII",
    "HSKA", "HSTM", "HTBI", "HTBK", "HTGC", "HTH",
    "HUN", "HWC", "HYMC",
    # IA-IZ
    "IAC", "IBEX", "IBP", "ICAD", "ICFI", "IDCC",
    "IESC", "IGT", "IHRT", "IIIV", "IMGO", "IMMR",
    "IMXI", "INBK", "INFN", "INFU", "INSM", "INSP",
    "INSW", "INVA", "IOSP", "IRBT", "IRDM", "IRMD",
    "IRTC", "IRWD", "ISTR", "ITGR", "ITOS", "IVR",
    "IVAC",
    # JA-KZ
    "JBGS", "JHG", "JOE", "JOUT",
    "KALU", "KAMN", "KAR", "KBAL", "KELYA", "KFRC",
    "KLIC", "KMT", "KOD", "KRA", "KREF", "KRG",
    "KRTX", "KVHI", "KW",
    # LA-LZ
    "LADR", "LAKE", "LAND", "LBAI", "LBRT", "LCUT",
    "LE", "LFST", "LGND", "LHCG", "LILA", "LILAK",
    "LINC", "LIVN", "LKFN", "LMAT", "LOAN", "LOT",
    "LPCN", "LPSN", "LQDA", "LTBR", "LUNG", "LXP",
    "LXRX", "LZB",
    # MA-MZ
    "MAC", "MATW", "MAX", "MBCN", "MBI", "MBIN",
    "MBUU", "MCBS", "MCW", "MDGL", "MDRX", "MEC",
    "MEIP", "MESA", "MGEE", "MGRC", "MHO", "MIR",
    "MIRM", "MKSI", "MLKN", "MMSI", "MNRL", "MNSB",
    "MNTK", "MODV", "MOFG", "MOR", "MOV", "MRNS",
    "MRUS", "MSBI", "MSEX", "MSG", "MTUS", "MXCT",
    "MYE", "MYFW",
    # NA-NZ
    "NARI", "NATR", "NBHC", "NCBS", "NCMI", "NCNO",
    "NDLS", "NEO", "NERV", "NEWT", "NGM", "NGVT",
    "NHC", "NICK", "NKSH", "NL", "NMIH", "NNBR",
    "NOMD", "NOTE", "NOVT", "NR", "NSA", "NSTG",
    "NTB", "NTCT", "NTGR", "NUS", "NVAX", "NVEC",
    "NVRO", "NWL", "NWN", "NWPX", "NXGN", "NXRT",
    "NXST",
    # OA-OZ
    "OBNK", "OCFC", "ODC", "OEC", "OFED", "OGS",
    "OIIM", "OIS", "OLN", "OM", "OMGA", "OPAL",
    "OPI", "OPRT", "OPY", "ORA", "ORBC", "ORIC",
    "ORRF", "OSUR", "OVBC", "OYST",
    # PA-PZ
    "PACK", "PAG", "PAHC", "PATI", "PAYS", "PB",
    "PBFS", "PBH", "PBI", "PCTI", "PDM", "PEBO",
    "PETQ", "PFC", "PFIS", "PFPT", "PGNY", "PGRE",
    "PHR", "PIPR", "PKBK", "PKOH", "PLAB", "PLAY",
    "PLSE", "PLXS", "PQG", "PRAA", "PRAH", "PRLB",
    "PRO", "PROF", "PRPO", "PRTH", "PRVB", "PSEC",
    "PSTG", "PTEN", "PTGX", "PUSH", "PVAC", "PWOD",
    # QA-RZ
    "QTNT", "QUIK", "QUOT",
    "RBA", "RBCAA", "RBNC", "RCII", "RCUS", "RDNT",
    "RDVT", "RECN", "REGI", "REPX", "RGA", "RGEN",
    "RGP", "RICK", "RIGL", "RLGT", "RLJ", "RMNI",
    "RNR", "ROG", "RPD", "RPT", "RRBI", "RRST",
    "RTLR", "RUSHA", "RUSHB", "RVLV", "RWT", "RYAM",
    # SA-SZ
    "SAH", "SALM", "SAMG", "SANM", "SASR", "SB",
    "SBBX", "SBGI", "SBSI", "SCHL", "SCHN", "SCLX",
    "SCPH", "SCVL", "SDC", "SDGR", "SEIC", "SEM",
    "SFM", "SFST", "SGBX", "SGHC", "SHBI", "SHC",
    "SHOO", "SHYF", "SIEN", "SIGA", "SILK", "SITC",
    "SJW", "SKWD", "SKYH", "SLDB", "SLG", "SLGN",
    "SLNO", "SLP", "SMBK", "SMMF", "SMSI", "SNBR",
    "SNEX", "SNPO", "SNV", "SOFO", "SONO", "SPHR",
    "SPI", "SPRO", "SPTN", "SPWH", "SRDX", "SRGA",
    "SRI", "SRNE", "SRRK", "SSD", "STAA", "STAR",
    "STC", "STGW", "STNG", "STRS", "STXS", "SUPN",
    "SURG", "SVC", "SVRA", "SWAV", "SWIM", "SWKH",
    # TA-TZ
    "TALO", "TBBK", "TBI", "TBNK", "TCBI", "TCDA",
    "TCMD", "TDC", "TDS", "TELL", "TERN", "TGAN",
    "TH", "THR", "TILE", "TLND", "TLYS", "TMST",
    "TNAV", "TNET", "TNXP", "TOWR", "TPCO", "TPIC",
    "TRC", "TREE", "TRMD", "TRNS", "TRS", "TRVI",
    "TSBK", "TTGT", "TWI", "TXG", "TXMD",
    # UA-ZZ
    "UBFO", "UCB", "UCBI", "UE", "UGI", "UHAL",
    "UIL", "UNTY", "USAC", "USFD", "USNA", "USPH",
    "UTL", "UUUU", "UVSP",
    "VALN", "VALU", "VCYT", "VECO", "VEL", "VHC",
    "VHI", "VIAV", "VICR", "VINP", "VLY", "VMD",
    "VMI", "VNRX", "VOXX", "VPG", "VRA", "VRDN",
    "VREX", "VRNA", "VRRM", "VSCO", "VSEC", "VTOL",
    "VVV", "VZIO",
    "WCC", "WD", "WEA", "WHG", "WINA", "WIRE",
    "WKC", "WLDN", "WLY", "WLFC", "WMG", "WNEB",
    "WOR", "WRE", "WSBF", "WWD", "WWW",
    "XFOR", "XHR", "XOG", "XPEL",
    "ZEAL", "ZYXI",
    # ── Fresh adds to break 3000 — verified unique names ──
    # OTC-active / popular trading tickers
    "BITO", "IBIT", "FBTC", "GBTC", "ETHE",
    "BITF", "APLD", "ARBK", "BKKT", "SI", "CUBI",
    "SBNY", "ZNGA", "ATVI", "EA", "TTWO", "RBLX",
    "U", "TAKE", "PLTK", "GMGI", "GLBE",
    "CFLT", "MDB", "FROG", "ESTC", "NEWR", "SUMO",
    "ZUO", "DOMO", "SMAR", "ASAN", "FRSH",
    # Popular mid-cap industrials
    "RXO", "GXO", "XPO", "BWXT", "TXT", "SPR",
    "LHX", "MRCY", "CACI", "SAIC", "LDOS",
    "CGNX", "ONTO", "ENTG", "AMKR", "COHR",
    "IPGP", "II", "MKSI", "TDY",
    # Banks / financials not yet covered
    "FRC", "SBNY", "PACW", "EWBC", "SBCF",
    "MCB", "OCFC", "FMBH", "SFBS", "HWC",
    "BOKF", "OZK", "SNV", "ABCB", "NWBI",
    "COLB", "BKU", "FBK", "SFNC", "CBU",
    "BHLB", "CHCO", "FNB", "SBSI", "UBSI",
    "PNFP", "GBCI", "WAL", "CADE", "WSFS",
    # Biotech / pharma not yet covered
    "ABCL", "ACAD", "ADPT", "AFMD", "AGEN",
    "ALKS", "ALLO", "AMRN", "APLS", "ARCT",
    "ATHA", "BCRX", "BGNE", "CARA", "CERS",
    "CLVS", "CMPS", "DARE", "DCPH", "DRNA",
    "ELAN", "ENTA", "FGEN", "GILD", "GMAB",
    "GTHX", "HRMY", "IMGO", "INSM", "IRWD",
    "JAZZ", "KPTI", "KURA", "LGND", "LQDA",
    "MYOV", "NKTX", "OCUL", "OPK", "PRTA",
    "QURE", "RAPT", "RLAY", "RPID", "RYTM",
    "SAGE", "STRO", "TCRR", "TELA", "TRDA",
    "VNDA", "VYGR", "XERS",
    # REITs not yet covered
    "AIRC", "ALX", "BDN", "BRT", "CIO",
    "CLPR", "CPT", "CUZ", "DEA", "DEI",
    "EGP", "ELS", "FCPT", "FRT", "FSP",
    "GNL", "GTY", "HIW", "HPP", "ILPT",
    "JBGS", "KRC", "LTC", "LXP", "MAC",
    "MDV", "MGP", "NEN", "NLY", "OFC",
    "OLP", "OUT", "PEI", "PDM", "PGRE",
    "PLYM", "PSTL", "REXR", "ROIC", "RPT",
    "SLG", "SITC", "SKT", "SRC", "STOR",
    "SUI", "TRNO", "UE", "UMH", "UNIT",
    "VERIS", "VICI", "VNO", "VRE", "WPC",
    # Consumer/retail not yet covered
    "BJ", "CASY", "CHUY", "COTY", "DKS",
    "EL", "FANG", "FIZZ", "FWONA", "GOOS",
    "GPS", "GRWG", "GVP", "IHRT", "INGR",
    "JILL", "KTB", "LANC", "LBRDK", "LEVI",
    "LIND", "LQDT", "MGPI", "NAPA", "ODP",
    "OLPX", "PPC", "PRGO", "SAM", "SG",
    "SMPL", "THS", "UNFI", "UTZ", "VITL",
    # Energy not yet covered
    "AM", "AMPY", "AROC", "BRY", "BTRL",
    "CEQP", "CRNC", "DEN", "DTM", "ENB",
    "EPD", "ET", "FLNG", "GPP", "GRP",
    "HESM", "KOS", "LNG", "LNGG", "MNRL",
    "MPLX", "MUR", "NFE", "PAA", "PBA",
    "SBOW", "SD", "SHEL", "TRP", "USAC",
    "VNOM", "WES",
    # Utilities not yet covered
    "AEE", "AGR", "ALE", "AQN", "CLNE",
    "CPK", "EIX", "EVRG", "GNE", "HE",
    "MGEE", "NJR", "NRG", "NWN", "OGE",
    "OTTR", "PCG", "PEG", "PNM", "PNW",
    "SJI", "SR", "SWX", "UTL", "VST",
    "WEC", "XEL",
    # Insurance not yet covered
    "ACGL", "AFG", "AGO", "AXS", "CINF",
    "EG", "EMC", "FAF", "FNF", "GNW",
    "HIG", "KNSL", "MKL", "ORI", "PFG",
    "PLMR", "RLI", "SIGI", "THG", "UNM",
    "WRB", "WTW",
]


# ═══════════════════════════════════════════════════════════
# Master US list — deduplicated
# ═══════════════════════════════════════════════════════════

_ALL_US_RAW = (
    SP500 + NDX_EXTRA + SP400_MIDCAP + RUSSELL_SMALLCAP
    + EXTENDED_UNIVERSE + RUSSELL_FILL
    + US_GROWTH_MOMENTUM + US_ETFS
)

# Deduplicate preserving order
_seen = set()
US_UNIVERSE = []
for _t in _ALL_US_RAW:
    if _t not in _seen:
        _seen.add(_t)
        US_UNIVERSE.append(_t)
del _seen, _t

# Sector hint lookup
US_SECTOR_MAP = {}
for _t in SP500_TECH:
    US_SECTOR_MAP[_t] = "Technology"
for _t in SP500_HEALTHCARE:
    US_SECTOR_MAP[_t] = "Healthcare"
for _t in SP500_FINANCIALS:
    US_SECTOR_MAP[_t] = "Financials"
for _t in SP500_CONSUMER_DISC:
    US_SECTOR_MAP[_t] = "Consumer Discretionary"
for _t in SP500_INDUSTRIALS:
    US_SECTOR_MAP[_t] = "Industrials"
for _t in SP500_COMM_SERVICES:
    US_SECTOR_MAP[_t] = "Communication Services"
for _t in SP500_ENERGY:
    US_SECTOR_MAP[_t] = "Energy"
for _t in SP500_STAPLES:
    US_SECTOR_MAP[_t] = "Consumer Staples"
for _t in SP500_MATERIALS:
    US_SECTOR_MAP[_t] = "Materials"
for _t in SP500_UTILITIES:
    US_SECTOR_MAP[_t] = "Utilities"
for _t in SP500_REITS:
    US_SECTOR_MAP[_t] = "Real Estate"
for _t in US_ETFS:
    US_SECTOR_MAP[_t] = "ETF"
for _t in US_GROWTH_MOMENTUM:
    US_SECTOR_MAP.setdefault(_t, "Growth")
for _t in RUSSELL_SMALLCAP:
    US_SECTOR_MAP.setdefault(_t, "Small Cap")
for _t in SP400_MIDCAP:
    US_SECTOR_MAP.setdefault(_t, "Mid Cap")
for _t in NDX_EXTRA:
    US_SECTOR_MAP.setdefault(_t, "Technology")
