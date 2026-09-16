| Metric | Result |
|---|---|
| Positions explained (one n8n run) | 45 |
| Draft cards the Claude verifier corrected | 20/45 (44%), 29 distinct corrections |
| Draft cards the Gemini verifier corrected | 0/45 |
| Cards the deterministic guard flags after verification (Claude run) | 0/45 |
| Cards the deterministic guard flags after verification (Gemini run) | 20/45 |
| Guard recall on planted errors | 528/585 (90%) |
| Guard false positives on clean cards | 0/45 |
| Quoted headline exists verbatim (draft -> verified) | 44/45 -> 45/45 |
| Company sentence fully supported (draft -> verified) | 29/45 -> 33/45 |
| Tokens per position (writer + verifier) | 9,283 in, 976 out |
| Seconds per position (LLM time) | 7.68 |
| Whole book, wall clock | 346 s of LLM time over 5 batches |
| Ask-the-book exact answers | 19/20 |
| Ask-the-book out-of-scope refused | 5/5 |