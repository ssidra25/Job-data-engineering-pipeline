# LLM Extraction Cost Analysis

## Model
Gemini 3.5 Flash-Lite

## Extraction Statistics

- Total candidates processed: 156
- Successfully extracted jobs: 130
- Input tokens: 229,541
- Output tokens: 36,529
- Total tokens: 266,070

## Estimated API Cost

| Metric | Cost (USD) |
|---|---:|
| Input token cost | $0.06886 |
| Output token cost | $0.09132 |
| Total estimated cost | $0.16018 |
| Cost per extracted job | $0.00123 |

## Calculation Method

- Input cost = (229,541 / 1,000,000) × $0.30
- Output cost = (36,529 / 1,000,000) × $2.50
- Cost per extracted job = $0.16018 / 130

## Summary

The extraction pipeline processed 156 candidate postings using Gemini 3.5 Flash-Lite and successfully extracted 130 structured job records. The run consumed 229,541 input tokens and 36,529 output tokens. Based on standard API pricing, the estimated total cost was approximately $0.1602, equivalent to approximately $0.00123 per extracted job.

## Note

Costs are estimates based on standard API pricing. Actual charges may differ depending on API billing tier, free-tier usage, and applicable pricing.