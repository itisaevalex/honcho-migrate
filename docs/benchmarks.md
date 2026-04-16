# Benchmarks

We benchmarked the self-hosted setup against Honcho Cloud (`api.honcho.dev`) to verify memory quality is equivalent.

## Smoke Test (Custom -- 5 Phases)

Tests memory ingestion, deriver processing, dialectic recall, semantic search, and cross-session persistence using 10 diverse conversations.

```
Phase 1  Memory Ingestion     10/10 (100%)
Phase 2  Deriver Processing   10/10 (100%)
Phase 3  Memory Recall        10/10 (100%)
Phase 4  Search Accuracy       8/8  (100%)
Phase 5  Cross-session         5/5  (100%)
──────────────────────────────────────────
Total                         43/43 (100%)
```

We also ran this against Honcho Cloud (84%) but the comparison was unfair -- cloud scores were lower due to API rate limiting dropping a conversation and the shared deriver not finishing before we queried. The LoCoMo benchmark below gives a fair head-to-head with proper deriver wait times.

## LoCoMo Academic Benchmark

[LoCoMo](https://github.com/snap-research/locomo) evaluates long-term conversational memory across multi-session dialogues (~300 turns, 19 sessions per conversation). Both instances had **full deriver processing + dream consolidation** before evaluation -- a fair comparison.

```
                              Local           Cloud
Single-hop (direct recall)    3.0/5  (60%)    4.0/5  (80%)
Multi-hop  (cross-fact)       0.0/8   (0%)    0.0/8   (0%)
Temporal   (time-based)       0.0/1   (0%)    0.0/1   (0%)
Open-domain (commonsense)     1.5/2  (75%)    1.0/2  (50%)
─────────────────────────────────────────────────────
Total                         4.5/16 (28%)    5.0/16 (31%)
```

**Essentially a draw.** Both share the same weakness on temporal/multi-hop questions -- Honcho extracts semantic observations ("user is vegetarian"), not timestamped event logs ("user said X on May 7"). This is by design; Honcho is built for understanding people, not timeline reconstruction.

## Model Stack Comparison

| Role | Self-hosted (Ollama) | Cloud (Honcho managed) |
|------|---------------------|----------------------|
| Deriver | qwen3.5:397b | Gemini 2.5 Flash Lite |
| Dialectic (low) | qwen3.5:397b | Gemini 2.5 Flash Lite |
| Dialectic (high) | minimax-m2.7 | Claude Haiku 4.5 |
| Dreamer | minimax-m2.7 | Claude Sonnet 4 |
| Embeddings | bge-m3 (1024d, local) | text-embedding-3-small (1536d) |

Open-weight models via Ollama Cloud match proprietary models on memory quality.

## Migration Test Suite

17 automated tests covering dry run, basic migration, edge cases (unicode, HTML injection, 3000-char messages), empty workspaces, workspace filtering, and idempotency. All passing.

```bash
python3 tests/test_migrate.py
# Results: 17/17 passed
```
