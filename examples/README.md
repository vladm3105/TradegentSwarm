# TradegentSwarm Examples

This directory contains example outputs and configurations.

## Files

| File | Description |
|------|-------------|
| `sample_stock_analysis.yaml` | Example stock analysis output from the platform |
| `sample_scanner_config.yaml` | Example scanner configuration |

## Stock Analysis

The `sample_stock_analysis.yaml` shows the structure of analysis documents:

- **Phase 1**: Catalyst identification and thesis
- **Phase 2**: Market environment assessment
- **Phase 3**: Technical analysis
- **Phase 4**: Options analysis
- **Phase 5**: Risk assessment
- **Gate Check**: Trade decision
- **Trade Setup**: Entry/exit levels

## Scanner Configuration

The `sample_scanner_config.yaml` demonstrates scanner definition:

- **Scanner Config**: Name, schedule, limits
- **Scanner Definition**: IB scanner parameters
- **Quality Filters**: Liquidity and fundamental filters
- **Scoring**: Weighted criteria for ranking candidates
- **Routing**: Thresholds for analyze vs watchlist

## Usage

These files are for reference only. To generate real analyses:

```bash
cd tradegent
python orchestrator.py analyze AAPL --type stock
```

To run scanners:

```bash
python orchestrator.py scan
```
