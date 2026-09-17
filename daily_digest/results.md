# Daily Digest — evaluation results

Mornings evaluated: **1** (2026-09-16)  
Items labelled: **13**  
Labellers: **AJW-claude**

## Extraction quality by configuration

| Config | Items | True | False | Precision | Missed | Recall | F1 | Priority acc. | Attribution |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| A_original | 5 | 5 | 0 | 1.00 | 2 | 0.71 | 0.83 | 1.00 | 1.00 |
| B_v3 | 8 | 7 | 1 | 0.88 | 0 | 1.00 | 0.93 | 1.00 | 1.00 |

_Precision = of what it surfaced, how much was a real action item. Recall = of the real action items in that inbox, how many it found (denominator includes the misses logged by hand). Attribution = did `source_ref` really appear in the original message._

## Inter-rater agreement (your human ceiling)

_No item was labelled by two people — fill the `labeller` column on two passes to get this. It is worth the twenty minutes._

## What it missed

| Config | Date | Missed item | Source | Should have been |
|---|---|---|---|---|
| A_original | 2026-09-16 | Approve invoice #4471 in the portal today | email | high |
| A_original | 2026-09-16 | Countersign and return the NDA by end of week | email | normal |
