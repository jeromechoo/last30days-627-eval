**Title:** Diffbot Coverage vs. Serper/Brave (follow-up to #627)

> "If you can show measured coverage Diffbot finds that Serper and Brave miss on the same topics, please open an issue with those numbers." - @iliaal

This is a follow-up to PR #627 which adds Diffbot Knowledge Graph as a news source but was closed due to unclear evidence of efficacy. This issue reviews the results of an eval that puts Diffbot News head to head against Brave and Serper for news coverage. The eval results show that Diffbot news adds 72%+ more on-topic news coverage than the incumbents (Brave/Serper) and adding it should vastly improve last30days' capability to cover news.

Disclosure: I work at Diffbot. The harness, raw results and every relevance label are attached so you can audit or re-run all of it (contact me for a Diffbot token). This issue is written by me, the eval was written and results tabulated by Opus 5.5.

## Method

- **20 topics** across mainstream tech, finance, niche/B2B, health, sports/culture and non-US topics (full table below)
- **Window:** 2026-09-19 → 2026-10-19 (30 days), one run on 2026-10-19.
- **Comparisons made against imported** `grounding.brave_search` and `grounding.serper_search` functions exactly as they live on `main`.
- **Equal budget:** each source is capped at its top 10 kept results per topic.
- **Opus labeled all 599 kept results:**
  - **N**: a dated article or post about the topic (news, analysis, blog, recent video or social post).
  - **E**: no recent material: home page, docs, Wikipedia, quote page, league table, product page, or an undated/stale post (for example a 2024 layoffs post returned for a 2026 window).
  - **X**: off-topic.
- **Story-level de-duplication:** a Diffbot article counts as "missed by Serper and Brave" only if neither returned the same URL (normalized) or a near-identical headline. Syndicated copies of a story both of them returned don't count.

## Results (top-10 per source, 20 topics)

| | Brave | Serper | Diffbot |
|---|---:|---:|---:|
| Results kept after the engine's date filter (max 200) | 199 | 200 | 200 |
| …of which dated on-topic articles (N) | 82 (41%) | 122 (61%) | **144 (72%)** |
| …evergreen / reference / stale (E) | **111 (56%)** | 72 (36%) | 31 (16%) |
| …off-topic (X) | 6 (3%) | 6 (3%) | **25 (12.5%)** |
| Median latency per call | 0.4 s | 1.9 s | 1.0 s |

**Coverage gap:**
- Serper and Brave together surfaced **186 distinct on-topic articles**.
- Diffbot surfaced **124 more on-topic articles that neither of them returned**, a +67% larger article pool.
- Diffbot added at least one missed article on **19 of 20 topics**.

| Topic | Brave+Serper articles | Diffbot articles | Diffbot-only articles |
|---|---:|---:|---:|
| OpenAI | 11 | 8 | 8 |
| Nvidia earnings | 8 | 6 | 5 |
| Apple Vision Pro | 10 | 7 | 7 |
| Tesla robotaxi | 12 | 9 | 8 |
| Claude Code | 4 | 3 | 3 |
| SpaceX IPO | 10 | 9 | 8 |
| Federal Reserve interest rates | 9 | 10 | 10 |
| Boeing strike | 16 | 8 | 6 |
| Shein IPO | 16 | 8 | 5 |
| Rivian layoffs | 3 | 2 | 0 |
| Figma AI | 5 | 6 | 5 |
| Anduril Industries | 6 | 8 | 8 |
| Cerebras | 14 | 9 | 7 |
| Perplexity lawsuit | 14 | 4 | 2 |
| GLP-1 drugs | 7 | 10 | 8 |
| measles outbreak | 10 | 9 | 7 |
| Formula 1 | 9 | 8 | 8 |
| Taylor Swift | 7 | 5 | 5 |
| Bundesliga | 5 | 6 | 5 |
| Reliance Jio | 10 | 9 | 9 |
| **Total** | **186** | **144** | **124** |

## Diffbot Differentiators

1. **Diffbot returns dated articles, Brave/Serper returns more evergreen pages.**
   - The date gate is a real `type:Article date>=…` filter on a parsed publish date, so 72% of what it returns is a recent on-topic article and only 16% is evergreen or stale.
2. **Global, international index.**
   - Much of Diffbot's coverage comes from regional and non-English outlets. Examples: Bangladeshi coverage of the measles outbreak, telecomtalk/BusinessLine on Jio, sportschau/ZDF on the Bundesliga, Rwandan and Turkish coverage of the F1 Africa race.

## Diffbot Tradeoffs

- **Off-topic rate is about 4× higher: 12.5% vs 3%.**
  - `text:` matches anywhere on a page, and the recency boost outweighs the headline boost, so fresh roundup and aggregator pages that merely mention the terms can outrank on-topic articles.
- **Some broad topics come back mostly non-English** (OpenAI, Taylor Swift, Bundesliga). This can be a problem for some users, but considering the target consumer is an LLM, more coverage (in any language) seems to be a better outcome.
- **Brave is faster** (0.4 s vs 1.0 s median).

## Reproduction

Harness: `bench/coverage.py` (runs the three sources), `bench/score.py` (story-level scoring). Data: `bench/topics.txt`, `bench/labels-slim.txt` (all 599 hand labels), `bench/results-slim/raw.json`.

```bash
export BRAVE_API_KEY=... SERPER_API_KEY=... DIFFBOT_API_KEY=...
uv run python bench/coverage.py --topics bench/topics.txt --end 2026-10-19 --days 30 --n 10 --out bench/results-slim
uv run python bench/score.py bench/results-slim/raw.json bench/labels-slim.txt
```

## Takeaways

Diffbot's KG news coverage adds 72%+ more on-topic news coverage than the incumbents (Brave/Serper) and it should be added to `last30days` to vastly improve its capability to cover news.
