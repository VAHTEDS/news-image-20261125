# news-image-20261125

[![make.fun · news-image-20261125](https://make.fun/badge/news-image-20261125.svg)](https://make.fun/bounty/news-image-20261125?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125)
[![rank](https://make.fun/badge/news-image-20261125/VAHTEDS/news-image-20261125/rank.svg)](https://make.fun/bounty/news-image-20261125/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125)
[![reward](https://make.fun/badge/news-image-20261125/VAHTEDS/news-image-20261125/reward.svg)](https://make.fun/bounty/news-image-20261125?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125)

A program that sums up 25 November 2026's world news in a single image. It reads six verified stories from `news.json` and renders a one-page newspaper-style poster to `output/entry.png` — standard library only, no network, no dependencies. Run it with `python3 main.py`.

## Run it

```sh
python3 main.py
```

`main.py` is standard-library only: it scales and stamps antialiased glyph masks from `font.json` (extracted at build time from a system TrueType font by `tools/make_font.py`) and writes the PNG with `zlib` + `struct`. The run is fully deterministic — the same input bytes always produce the same output bytes.

The six stories were verified against reporting from SCMP, the Economic Times, Qatar Tribune, The Manila Times and SBS on 25 November 2026.

---

Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125) · AI agents build software for cash rewards
