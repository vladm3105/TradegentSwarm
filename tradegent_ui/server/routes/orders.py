"""Order management routes."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal, Optional
import structlog

from ..auth import get_current_user, UserClaims

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/orders", tags=["orders"])


class BracketOrderRequest(BaseModel):
    symbol: str
    action: Literal['BUY', 'SELL']
    quantity: int
    entry_type: Literal['MARKET', 'LIMIT', 'STOP_LIMIT']
    entry_price: Optional[float] = None
    stop_loss_price: float
    take_profit_price: Optional[float] = None
    time_in_force: Literal['DAY', 'GTC'] = 'DAY'


class BracketOrderResponse(BaseModel):
    success: bool
    parent_order_id: Optional[str]
    stop_order_id: Optional[str]
    profit_order_id: Optional[str]
    message: str


class ModifyStopRequest(BaseModel):
    order_id: str
    new_stop_price: float


class OrderTemplate(BaseModel):
    id: int
    name: str
    symbol: Optional[str]
    action: Literal['BUY', 'SELL']
    quantity_type: Literal['shares', 'dollars', 'pct_portfolio']
    quantity_value: float
    entry_type: str
    stop_pct: Optional[float]
    target_pct: Optional[float]


@router.post("/bracket", response_model=BracketOrderResponse)
async def place_bracket_order(
    body: BracketOrderRequest,
    user: UserClaims = Depends(get_current_user),
) -> BracketOrderResponse:
    """Place a bracket order (entry + stop loss + optional take profit)."""
    try:
        from ..mcp_client import get_mcp_pool
        pool = await get_mcp_pool()

        # Place parent order
        parent_params = {
            "symbol": body.symbol,
            "action": body.action,
            "quantity": body.quantity,
            "order_type": body.entry_type,
            "time_in_force": body.time_in_force,
        }
        if body.entry_price and body.entry_type != 'MARKET':
            parent_params["limit_price"] = body.entry_price

        parent_result = await pool.call_ib_mcp("place_order", parent_params)

        if not parent_result.success:
            return BracketOrderResponse(
                success=False,
                parent_order_id=None,
                stop_order_id=None,
                profit_order_id=None,
                message=f"Failed to place parent order: {parent_result.error}",
            )

        parent_order_id = parent_result.result.get("order_id")
        stop_order_id = None
        profit_order_id = None

        # Place stop loss order
        stop_action = "SELL" if body.action == "BUY" else "BUY"
        stop_result = await pool.call_ib_mcp("place_order", {
            "symbol": body.symbol,
            "action": stop_action,
            "quantity": body.quantity,
            "order_type": "STOP",
            "stop_price": body.stop_loss_price,
            "parent_id": parent_order_id,
            "time_in_force": "GTC",
        })

        if stop_result.success:
            stop_order_id = stop_result.result.get("order_id")

        # Place take profit order if specified
        if body.take_profit_price:
            profit_result = await pool.call_ib_mcp("place_order", {
                "symbol": body.symbol,
                "action": stop_action,
                "quantity": body.quantity,
                "order_type": "LIMIT",
                "limit_price": body.take_profit_price,
                "parent_id": parent_order_id,
                "time_in_force": "GTC",
                "oca_group": f"bracket_{parent_order_id}",
            })

            if profit_result.success:
                profit_order_id = profit_result.result.get("order_id")

        log.info(
            "bracket_order.placed",
            symbol=body.symbol,
            parent_id=parent_order_id,
            stop_id=stop_order_id,
            profit_id=profit_order_id,
            user=user.email,
        )

        return BracketOrderResponse(
            success=True,
            parent_order_id=parent_order_id,
            stop_order_id=stop_order_id,
            profit_order_id=profit_order_id,
            message="Bracket order placed successfully",
        )

    except Exception as e:
        log.error("bracket_order.failed", error=str(e), symbol=body.symbol)
        return BracketOrderResponse(
            success=False,
            parent_order_id=None,
            stop_order_id=None,
            profit_order_id=None,
            message=str(e),
        )


@router.post("/modify-stop")
async def modify_stop_order(
    body: ModifyStopRequest,
    user: UserClaims = Depends(get_current_user),
):
    """Modify an existing stop order price."""
    try:
        from ..mcp_client import get_mcp_pool
        pool = await get_mcp_pool()

        result = await pool.call_ib_mcp("modify_order", {
            "order_id": body.order_id,
            "stop_price": body.new_stop_price,
        })

        if not result.success:
            raise HTTPException(400, f"Failed to modify stop: {result.error}")

        log.info(
            "stop_order.modified",
            order_id=body.order_id,
            new_price=body.new_stop_price,
            user=user.email,
        )

        return {"success": True, "order_id": body.order_id}

    except HTTPException:
        raise
    except Exception as e:
        log.error("modify_stop.failed", error=str(e), order_id=body.order_id)
        raise HTTPException(500, str(e))


@router.post("/cancel/{order_id}")
async def cancel_order(
    order_id: str,
    user: UserClaims = Depends(get_current_user),
):
    """Cancel an open order."""
    try:
        from ..mcp_client import get_mcp_pool
        pool = await get_mcp_pool()

        result = await pool.call_ib_mcp("cancel_order", {"order_id": order_id})

        if not result.success:
            raise HTTPException(400, f"Failed to cancel order: {result.error}")

        log.info("order.cancelled", order_id=order_id, user=user.email)
        return {"success": True, "order_id": order_id}

    except HTTPException:
        raise
    except Exception as e:
        log.error("cancel_order.failed", error=str(e), order_id=order_id)
        raise HTTPException(500, str(e))


@router.get("/open")
async def get_open_orders(
    user: UserClaims = Depends(get_current_user),
):
    """Get all open orders."""
    try:
        from ..mcp_client import get_mcp_pool
        pool = await get_mcp_pool()

        result = await pool.call_ib_mcp("get_open_orders", {})

        if not result.success:
            raise HTTPException(500, f"Failed to get orders: {result.error}")

        return {"orders": result.result or []}

    except HTTPException:
        raise
    except Exception as e:
        log.error("get_open_orders.failed", error=str(e))
        raise HTTPException(500, str(e))
