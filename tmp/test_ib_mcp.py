#!/usr/bin/env python3
"""Test IB MCP server: health check, market data, account info."""

import asyncio
import os
import sys
from pathlib import Path

# Set IB Gateway host for local testing
os.environ.setdefault("IB_GATEWAY_HOST", "localhost")
os.environ.setdefault("IB_GATEWAY_PORT", "4002")

# Add ibmcp to path
sys.path.insert(0, str(Path("/opt/data/trading/mcp_ib/src")))

from ibmcp.server import (
    health_check,
    get_stock_price,
    get_positions,
    get_account_summary,
    get_pnl,
)


async def main():
    print("=" * 70)
    print("IB MCP Server Test")
    print("=" * 70)

    # Step 1: Health check
    print("\n[1] Health Check...")
    try:
        result = await health_check(connect=True)
        print(f"    Status: {result['status']}")
        print(f"    Server version: {result['server_version']}")
        print(f"    Accounts: {result['managed_accounts']}")
    except Exception as e:
        print(f"    ERROR: {e}")
        return 1

    # Step 2: Get stock prices
    print("\n[2] Stock Prices...")
    symbols = ["NVDA", "AAPL", "MSFT"]
    for symbol in symbols:
        try:
            result = await get_stock_price(symbol)
            if result["success"]:
                print(f"    {symbol}: ${result['last']:.2f} (bid: ${result['bid']:.2f}, ask: ${result['ask']:.2f})")
            else:
                print(f"    {symbol}: ERROR - {result.get('error', 'Unknown')}")
        except Exception as e:
            print(f"    {symbol}: ERROR - {e}")

    # Step 3: Account summary
    print("\n[3] Account Summary...")
    try:
        result = await get_account_summary()
        if result["success"]:
            summary = result.get("summary", {})
            print(f"    Net Liquidation: ${summary.get('NetLiquidation', 'N/A')}")
            print(f"    Buying Power: ${summary.get('BuyingPower', 'N/A')}")
            print(f"    Available Funds: ${summary.get('AvailableFunds', 'N/A')}")
        else:
            print(f"    ERROR: {result.get('error', 'Unknown')}")
    except Exception as e:
        print(f"    ERROR: {e}")

    # Step 4: P&L
    print("\n[4] P&L Summary...")
    try:
        result = await get_pnl()
        if result["success"]:
            daily = result.get('daily_pnl')
            unrealized = result.get('unrealized_pnl')
            realized = result.get('realized_pnl')
            print(f"    Daily P&L: ${daily:.2f}" if daily is not None else "    Daily P&L: N/A")
            print(f"    Unrealized P&L: ${unrealized:.2f}" if unrealized is not None else "    Unrealized P&L: N/A")
            print(f"    Realized P&L: ${realized:.2f}" if realized is not None else "    Realized P&L: N/A")
        else:
            print(f"    ERROR: {result.get('error', 'Unknown')}")
    except Exception as e:
        print(f"    ERROR: {e}")

    # Step 5: Positions
    print("\n[5] Positions...")
    try:
        result = await get_positions()
        if result["success"]:
            positions = result.get("positions", [])
            if positions:
                for p in positions[:5]:
                    print(f"    {p['symbol']}: {p['position']} shares @ ${p.get('avg_cost', 0):.2f}")
            else:
                print(f"    No open positions")
        else:
            print(f"    ERROR: {result.get('error', 'Unknown')}")
    except Exception as e:
        print(f"    ERROR: {e}")

    print("\n" + "=" * 70)
    print("IB MCP Test Complete")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
