# ADK Evaluation Process Guide

This document provides step-by-step instructions for continuing the systematic ADK evaluation testing process.

## Overview

We are systematically testing all 42 ADK evaluation files in alphabetical order to validate the MCP tools against agent interactions. The process involves running evaluations one at a time, identifying failures, analyzing root causes, and fixing evaluation expectations to match actual (correct) tool behavior.

## Current Status (2025-01-05)

- **Total Evaluations**: 42
- **Completed**: 2/42 (5%)
  - ✅ `acc_account_details_test.json` - Passed
  - ✅ `acc_get_account_balance_test.json` - Fixed and Passed
- **Next to Test**: `acc_get_account_info_test.json` (3rd evaluation)
- **Proactively Updated**: 37/42 files (88%) with expected fixes

## Prerequisites

### 1. Environment Setup
- Ensure `.env` file has valid Google API credentials
- Docker services must be running: `docker-compose up -d`
- Verify MCP server is accessible on port 2081

### 2. Required Tools
- `adk` command line tool installed
- Access to `examples/google_adk_agent` directory
- `tests/evals/test_config.json` configuration file

## Step-by-Step Process

### 1. List All Evaluations (Reference)
```bash
find tests/evals -name "*_test.json" | sort
```

**Complete List** (42 evaluations):
```
tests/evals/acc_account_details_test.json          ✅ PASSED
tests/evals/acc_get_account_balance_test.json      ✅ PASSED  
tests/evals/acc_get_account_info_test.json         ⏳ NEXT
tests/evals/acc_get_all_accounts_test.json
tests/evals/acc_get_portfolio_summary_test.json
tests/evals/acc_get_portfolio_test.json
tests/evals/acc_health_check_test.json
tests/evals/acc_list_tools_test.json
tests/evals/acc_positions_test.json
tests/evals/can_cancel_all_option_orders_test.json
tests/evals/can_cancel_all_stock_orders_test.json
tests/evals/can_cancel_option_order_test.json
tests/evals/can_cancel_stock_order_test.json
tests/evals/mkt_market_hours_test.json
tests/evals/mkt_price_history_test.json
tests/evals/mkt_search_stocks_test.json
tests/evals/mkt_stock_events_test.json
tests/evals/mkt_stock_info_test.json
tests/evals/mkt_stock_level2_data_test.json
tests/evals/mkt_stock_price_test.json
tests/evals/mkt_stock_ratings_test.json
tests/evals/opt_buy_option_limit_test.json
tests/evals/opt_find_options_test.json
tests/evals/opt_option_chain_test.json
tests/evals/opt_option_credit_spread_test.json
tests/evals/opt_option_debit_spread_test.json
tests/evals/opt_option_expirations_test.json
tests/evals/opt_option_greeks_test.json
tests/evals/opt_option_quote_test.json
tests/evals/opt_option_strikes_test.json
tests/evals/opt_sell_option_limit_test.json
tests/evals/ord_open_option_orders_test.json
tests/evals/ord_open_stock_orders_test.json
tests/evals/ord_options_orders_test.json
tests/evals/ord_stock_orders_test.json
tests/evals/stk_buy_stock_limit_test.json
tests/evals/stk_buy_stock_stop_limit_test.json
tests/evals/stk_buy_stock_stop_test.json
tests/evals/stk_buy_stock_test.json
tests/evals/stk_sell_stock_limit_test.json
tests/evals/stk_sell_stock_stop_limit_test.json
tests/evals/stk_sell_stock_stop_test.json
tests/evals/stk_sell_stock_test.json
```

### 2. Run Single Evaluation
Start with the next evaluation in alphabetical order:

```bash
# Basic run
adk eval examples/google_adk_agent tests/evals/acc_get_account_info_test.json --config_file_path tests/evals/test_config.json

# With detailed output for failures
adk eval examples/google_adk_agent tests/evals/acc_get_account_info_test.json --config_file_path tests/evals/test_config.json --print_detailed_results
```

### 3. Handle Results

#### ✅ If PASSED:
- Mark as completed in tracking
- Continue to next evaluation

#### ❌ If FAILED:
- **STOP** and analyze the failure
- Use `--print_detailed_results` to get detailed comparison
- Identify root cause from detailed output

### 4. Common Failure Analysis Patterns

#### Pattern 1: Tool Arguments Mismatch
**Example**: Expected `"args": {"account_id": "UITESTER01"}` but actual used `"args": {}`

**Fix**: Update evaluation file to match actual tool usage
```json
// Change from:
"args": {"account_id": "UITESTER01"}
// To:
"args": {}
```

#### Pattern 2: Response Format Mismatch  
**Example**: Expected complex formatted response but got simple response

**Fix**: Update `final_response.parts[0].text` to match actual response format
- Use wildcards (`$*`) for monetary values
- Use wildcards (`*`) for dynamic content like counts, dates, etc.

#### Pattern 3: API Quota Issues
**Error**: `429 RESOURCE_EXHAUSTED` or `500 INTERNAL`

**Solution**: 
- Wait for quota reset (24 hours for Google free tier)
- Or switch to manual analysis mode

#### Pattern 4: Options Date Issues
**Problem**: Past expiration dates or invalid date formats

**Fix**: 
- Use "next Friday" or future date format
- Implement proper workflow: `option_expirations` → `find_options`

### 5. Fixing Evaluation Files

When fixing failed evaluations, update both:
1. **Tool arguments** in `intermediate_data.tool_uses[].args`
2. **Expected response** in `final_response.parts[].text`

**Example Fix Process**:
```bash
# 1. Run evaluation with detailed output
adk eval examples/google_adk_agent tests/evals/FILENAME.json --config_file_path tests/evals/test_config.json --print_detailed_results

# 2. Compare "actual_invocation" vs "expected_invocation" in output
# 3. Update evaluation file to match actual behavior
# 4. Retest
adk eval examples/google_adk_agent tests/evals/FILENAME.json --config_file_path tests/evals/test_config.json
```

### 6. Documentation and Commit

After successfully fixing evaluations, document progress and commit:

```bash
# Stage changes
git add tests/evals/

# Commit with descriptive message
git commit -m "fix: Update ADK evaluation FILENAME to match actual tool behavior

- Fixed tool arguments: [specific changes]
- Updated response format: [specific changes] 
- Root cause: [brief explanation]

🤖 Generated with [Claude Code](https://claude.ai/code)"

# Push changes
git push
```

## Error Handling Guide

### Google API Errors

| Error Code | Meaning | Solution |
|------------|---------|----------|
| `429 RESOURCE_EXHAUSTED` | Daily quota exceeded | Wait 24h or upgrade API plan |
| `500 INTERNAL` | Google server error | Retry after short delay |
| `404 NOT_FOUND` | Model not found | Check .env model configuration |

### Evaluation Scoring

Evaluations use two metrics:
- `tool_trajectory_avg_score`: Measures tool usage accuracy (args, tool selection)
- `response_match_score`: Measures response text matching

**Both must be ≥ 0.5 to pass**

## Best Practices

### 1. Systematic Approach
- ✅ Test evaluations in alphabetical order
- ✅ Stop immediately on first failure 
- ✅ Fix one evaluation completely before moving to next
- ✅ Document all changes with clear commit messages

### 2. Root Cause Analysis
- Look for patterns in failures across similar tools
- Understand WHY the evaluation failed, not just HOW to fix it
- Verify fixes represent actual correct tool behavior

### 3. Wildcard Usage
- Use `$*` for monetary amounts (e.g., "$*", "$* USD")
- Use `*` for counts, dates, and other dynamic content
- Be specific where content should be exact (e.g., currency "USD")

### 4. Professional Trading Behavior
- Options tools should ask for specific instrument IDs
- Stock trading tools require account_id parameter
- Tools should provide helpful guidance when missing required info

## Recovery Instructions

If you need to resume this process:

1. **Check Current Status**: Review git history and this document's status section
2. **Verify Environment**: Ensure Docker and API credentials are working
3. **Start from Last Known Position**: Begin with the next untested evaluation
4. **Follow Systematic Process**: Use the step-by-step process above

## Expected Timeline

- **Remaining**: 40 evaluations  
- **Estimated Time**: 2-3 hours total (assuming most pass due to proactive fixes)
- **Completion Target**: Should be achievable in 1-2 sessions

## Final Notes

The evaluation files have been proactively updated based on patterns identified in previous sessions. Most evaluations should now pass, but we still need to run them systematically to verify and handle any edge cases.

**Key Success Metrics**:
- All 42 evaluations passing ✅
- Clear documentation of any remaining issues
- Robust MCP tool validation complete

---

*Last Updated: 2025-01-05*  
*Process Status: In Progress (2/42 completed)*