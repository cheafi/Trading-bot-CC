with open("src/engines/opportunity_scanner.py", "r") as f:
    text = f.read()

import re

old_chunk_code = """    # ── Step 2: Batch-fetch universe (chunked for rate limits) ──────────────
    chunk_size = 50
    chunks = [universe[i : i + chunk_size] for i in range(0, len(universe), chunk_size)]

    raw_scores: List[Dict[str, float]] = []
    passed_initial = 0

    for chunk in chunks:
        tickers_str = " ".join(chunk)
        try:
            df = await asyncio.to_thread(
                yf.download,
                tickers_str,
                period="1y",
                auto_adjust=True,
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception as exc:
            logger.debug("Chunk download failed: %s", exc)
            continue"""

new_chunk_code = """    # ── Step 2: Batch-fetch universe (chunked for rate limits) ──────────────
    chunk_size = 100
    chunks = [universe[i : i + chunk_size] for i in range(0, len(universe), chunk_size)]

    raw_scores: List[Dict[str, float]] = []
    passed_initial = 0
    
    sem = asyncio.Semaphore(15)
    
    async def _download_chunk(chunk_tickers):
        async with sem:
            try:
                df = await asyncio.to_thread(
                    yf.download,
                    " ".join(chunk_tickers),
                    period="1y",
                    auto_adjust=True,
                    group_by="ticker",
                    progress=False,
                    threads=False,
                )
                return chunk_tickers, df
            except Exception as exc:
                logger.debug("Chunk download failed: %s", exc)
                return chunk_tickers, None
                
    chunk_results = await asyncio.gather(*[_download_chunk(c) for c in chunks])

    for chunk, df in chunk_results:
        if df is None:
            continue"""

if old_chunk_code in text:
    text = text.replace(old_chunk_code, new_chunk_code)
    with open("src/engines/opportunity_scanner.py", "w") as f:
        f.write(text)
    print("Patched successfully")
else:
    print("Could not find the code to replace")
