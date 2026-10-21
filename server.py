"""MCP server for Ozon Seller API (api-seller.ozon.ru)."""

import os
import json
import asyncio
from datetime import datetime, timedelta, timezone
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ozon-seller")

BASE_URL = "https://api-seller.ozon.ru"
_client: httpx.AsyncClient | None = None


def _load_env_file() -> None:
    """Load .env file if present and variables not already set."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


_load_env_file()


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        client_id = os.environ.get("OZON_CLIENT_ID", "")
        api_key = os.environ.get("OZON_API_KEY", "")
        if not client_id or not api_key:
            raise ValueError(
                "OZON_CLIENT_ID and OZON_API_KEY environment variables are required"
            )
        _client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "Client-Id": client_id,
                "Api-Key": api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
    return _client


def _to_rfc3339(date_str: str, is_end: bool = False) -> str:
    """Normalize date string (YYYY-MM-DD or partial) to RFC3339 format."""
    if not date_str:
        return ""
    if "T" in date_str:
        if not date_str.endswith("Z"):
            return date_str + "Z"
        return date_str
    time_part = "23:59:59Z" if is_end else "00:00:00Z"
    return f"{date_str}T{time_part}"


def _normalize_money(
    val: float | int | str | dict, default_currency: str = "RUB"
) -> dict:
    """Normalize money value to Ozon Money format: {'amount': '...', 'currency': 'RUB'}."""
    if isinstance(val, dict):
        return val
    if isinstance(val, float):
        val_str = f"{val:.2f}".rstrip("0").rstrip(".")
    else:
        val_str = str(val)
    return {"amount": val_str, "currency": default_currency}


async def _post(path: str, body: dict | None = None) -> str:
    """Make a POST request to Ozon Seller API and return JSON string."""
    client = _get_client()
    try:
        resp = await client.post(path, json=body if body is not None else {})
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False, indent=2)
    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        return json.dumps(
            {"error": f"HTTP {e.response.status_code}", "detail": error_body},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def _get(path: str, params: dict | None = None) -> str:
    """Make a GET request to Ozon Seller API and return JSON string."""
    client = _get_client()
    try:
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False, indent=2)
    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        return json.dumps(
            {"error": f"HTTP {e.response.status_code}", "detail": error_body},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ── Products ─────────────────────────────────────────────────────────────────


@mcp.tool()
async def product_list(
    limit: int = 100,
    last_id: str = "",
    offer_id_filter: list[str] | None = None,
    product_id_filter: list[int] | None = None,
    visibility: str = "ALL",
) -> str:
    """List seller's products. Visibility: ALL, VISIBLE, INVISIBLE, EMPTY_STOCK, NOT_MODERATED, MODERATED, DISABLED, STATE_FAILED, READY_TO_SUPPLY, VALIDATION_STATE_PENDING, VALIDATION_STATE_FAIL, VALIDATION_STATE_SUCCESS, TO_SUPPLY, IN_SALE, REMOVED_FROM_SALE, BAN_REASON_DUPLICATE_DESCRIPTION, BAN_REASON_MANUAL, BAN_REASON_LEGAL."""
    filt: dict = {"visibility": visibility}
    if offer_id_filter:
        filt["offer_id"] = offer_id_filter
    if product_id_filter:
        filt["product_id"] = product_id_filter
    body: dict = {"filter": filt, "limit": limit}
    if last_id:
        body["last_id"] = last_id
    return await _post("/v3/product/list", body)


@mcp.tool()
async def product_info(product_id: int = 0, offer_id: str = "", sku: int = 0) -> str:
    """Get detailed info about a single product by product_id, offer_id, or sku."""
    body: dict = {}
    if product_id:
        body["product_id"] = [product_id]
    elif offer_id:
        body["offer_id"] = [offer_id]
    elif sku:
        body["sku"] = [sku]
    else:
        return json.dumps(
            {"error": "Provide at least one of product_id, offer_id, or sku"},
            ensure_ascii=False,
        )
    return await _post("/v3/product/info/list", body)


@mcp.tool()
async def product_info_list(
    product_id: list[int] | None = None,
    offer_id: list[str] | None = None,
    sku: list[int] | None = None,
) -> str:
    """Get detailed info for multiple products (prices, barcode, moderation status). Provide product_id list, offer_id list, or sku list."""
    body: dict = {}
    if product_id:
        body["product_id"] = product_id
    if offer_id:
        body["offer_id"] = offer_id
    if sku:
        body["sku"] = sku
    if not body:
        return json.dumps(
            {"error": "Provide at least one of product_id, offer_id, or sku"},
            ensure_ascii=False,
        )
    return await _post("/v3/product/info/list", body)


@mcp.tool()
async def product_info_attributes(
    product_id: list[int] | None = None,
    offer_id: list[str] | None = None,
    limit: int = 100,
    last_id: str = "",
    sort_by: str = "",
    sort_dir: str = "ASC",
) -> str:
    """Get product attributes/characteristics."""
    filt: dict = {}
    if product_id:
        filt["product_id"] = product_id
    if offer_id:
        filt["offer_id"] = offer_id
    body: dict = {"filter": filt, "limit": limit}
    if last_id:
        body["last_id"] = last_id
    if sort_by:
        body["sort_by"] = sort_by
        body["sort_dir"] = sort_dir
    return await _post("/v4/product/info/attributes", body)


@mcp.tool()
async def product_import(items: list[dict]) -> str:
    """Import/create/update products. Each item dict should contain: name, offer_id, category_id, price, vat, attributes, etc. Returns task_id for async tracking. Max 100 items."""
    return await _post("/v3/product/import", {"items": items})


@mcp.tool()
async def product_import_info(task_id: int) -> str:
    """Check the status of a product import task by task_id."""
    return await _post("/v1/product/import/info", {"task_id": task_id})


@mcp.tool()
async def product_archive(product_id: list[int]) -> str:
    """Archive products by their IDs."""
    return await _post("/v1/product/archive", {"product_id": product_id})


@mcp.tool()
async def product_unarchive(product_id: list[int]) -> str:
    """Unarchive products by their IDs."""
    return await _post("/v1/product/unarchive", {"product_id": product_id})


@mcp.tool()
async def product_delete(offer_ids: list[str]) -> str:
    """Delete products that haven't been assigned an SKU yet by offer_ids list."""
    return await _post(
        "/v2/products/delete",
        {"products": [{"offer_id": oid} for oid in offer_ids]},
    )


@mcp.tool()
async def product_description(product_id: int = 0, offer_id: str = "") -> str:
    """Get product description."""
    body: dict = {}
    if product_id:
        body["product_id"] = product_id
    if offer_id:
        body["offer_id"] = offer_id
    if not body:
        return json.dumps(
            {"error": "Provide product_id or offer_id"}, ensure_ascii=False
        )
    return await _post("/v1/product/info/description", body)


@mcp.tool()
async def product_attributes_update(items: list[dict]) -> str:
    """Update product attributes. Each item: {product_id, attributes: [{id, values: [{value, dictionary_value_id}]}]}."""
    return await _post("/v1/product/attributes/update", {"items": items})


@mcp.tool()
async def product_pictures_import(product_id: int, images: list[str]) -> str:
    """Upload product images by URLs. images is a list of image URLs."""
    return await _post(
        "/v1/product/pictures/import",
        {"product_id": product_id, "images": images},
    )


# ── Prices ───────────────────────────────────────────────────────────────────


@mcp.tool()
async def prices_info(
    product_id_filter: list[int] | None = None,
    offer_id_filter: list[str] | None = None,
    limit: int = 100,
    last_id: str = "",
) -> str:
    """Get prices, commissions, and marketing data for products."""
    filt: dict = {}
    if product_id_filter:
        filt["product_id"] = product_id_filter
    if offer_id_filter:
        filt["offer_id"] = offer_id_filter
    body: dict = {"filter": filt, "limit": limit}
    if last_id:
        body["last_id"] = last_id
    return await _post("/v5/product/info/prices", body)


@mcp.tool()
async def prices_update(prices: list[dict]) -> str:
    """Update product prices. Each item: {product_id, price, old_price, min_price, auto_action_enabled, currency_code}. Max 1000 items. Rate limit: 10 updates/hour per product."""
    return await _post("/v1/product/import/prices", {"prices": prices})


# ── Stocks ───────────────────────────────────────────────────────────────────


@mcp.tool()
async def stocks_info(
    product_id_filter: list[int] | None = None,
    offer_id_filter: list[str] | None = None,
    limit: int = 100,
    last_id: str = "",
) -> str:
    """Get FBS/rFBS stock levels for products."""
    filt: dict = {}
    if product_id_filter:
        filt["product_id"] = product_id_filter
    if offer_id_filter:
        filt["offer_id"] = offer_id_filter
    body: dict = {"filter": filt, "limit": limit}
    if last_id:
        body["last_id"] = last_id
    return await _post("/v4/product/info/stocks", body)


@mcp.tool()
async def stocks_update(stocks: list[dict]) -> str:
    """Update stock quantities. Each item: {offer_id, product_id, stock, warehouse_id}. Max 100 items. Rate limit: 80 req/min."""
    return await _post("/v2/products/stocks", {"stocks": stocks})


@mcp.tool()
async def stocks_by_warehouse_fbs(sku: list[str], limit: int = 100) -> str:
    """Get FBS stock by warehouse for given SKUs (list of SKU strings or ints). Limit between 1 and 1000."""
    return await _post(
        "/v2/product/info/stocks-by-warehouse/fbs",
        {"sku": [str(s) for s in sku], "limit": limit},
    )


# ── FBS Orders (Fulfilled by Seller) ────────────────────────────────────────


@mcp.tool()
async def fbs_unfulfilled_list(
    limit: int = 50,
    offset: int = 0,
    status: str = "",
    sort_by: str = "created_at",
    sort_dir: str = "ASC",
    cutoff_from: str = "",
    cutoff_to: str = "",
    delivering_date_from: str = "",
    delivering_date_to: str = "",
) -> str:
    """List unprocessed FBS shipments. Status: awaiting_packaging, awaiting_deliver, arbitration, delivering, driver_pickup, delivered, cancelled."""
    now = datetime.now(timezone.utc)
    c_from = (
        _to_rfc3339(cutoff_from)
        if cutoff_from
        else (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    )
    c_to = (
        _to_rfc3339(cutoff_to, is_end=True)
        if cutoff_to
        else (now + timedelta(days=14)).strftime("%Y-%m-%dT23:59:59Z")
    )
    filt: dict = {
        "cutoff_from": c_from,
        "cutoff_to": c_to,
    }
    if status:
        filt["status"] = status
    if delivering_date_from:
        filt["delivering_date_from"] = _to_rfc3339(delivering_date_from)
    if delivering_date_to:
        filt["delivering_date_to"] = _to_rfc3339(delivering_date_to, is_end=True)
    body: dict = {
        "dir": sort_dir,
        "filter": filt,
        "limit": limit,
        "offset": offset,
        "sort_by": sort_by,
    }
    return await _post("/v3/posting/fbs/unfulfilled/list", body)


@mcp.tool()
async def fbs_posting_list(
    limit: int = 50,
    offset: int = 0,
    since: str = "",
    to: str = "",
    status: str = "",
    sort_dir: str = "ASC",
) -> str:
    """List FBS shipments with filters. Dates in RFC3339 format or YYYY-MM-DD. Defaults to last 30 days if not set."""
    now = datetime.now(timezone.utc)
    since_rfc = (
        _to_rfc3339(since)
        if since
        else (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    )
    to_rfc = (
        _to_rfc3339(to, is_end=True)
        if to
        else now.strftime("%Y-%m-%dT23:59:59Z")
    )
    filt: dict = {
        "since": since_rfc,
        "to": to_rfc,
    }
    if status:
        filt["status"] = status
    body: dict = {"dir": sort_dir, "filter": filt, "limit": limit, "offset": offset}
    return await _post("/v3/posting/fbs/list", body)


@mcp.tool()
async def fbs_posting_get(posting_number: str) -> str:
    """Get detailed info about a single FBS shipment by posting number."""
    return await _post("/v3/posting/fbs/get", {"posting_number": posting_number})


@mcp.tool()
async def fbs_ship(posting_number: str, packages: list[dict]) -> str:
    """Pack and confirm FBS shipment. packages: [{products: [{product_id, quantity}]}]."""
    return await _post(
        "/v4/posting/fbs/ship",
        {"posting_number": posting_number, "packages": packages},
    )


@mcp.tool()
async def fbs_cancel(
    posting_number: str, cancel_reason_id: int, cancel_reason_message: str = ""
) -> str:
    """Cancel an FBS shipment."""
    body: dict = {
        "posting_number": posting_number,
        "cancel_reason_id": cancel_reason_id,
    }
    if cancel_reason_message:
        body["cancel_reason_message"] = cancel_reason_message
    return await _post("/v2/posting/fbs/cancel", body)


@mcp.tool()
async def fbs_cancel_reasons() -> str:
    """Get list of available cancellation reasons for FBS."""
    return await _post("/v2/posting/fbs/cancel-reason/list")


@mcp.tool()
async def fbs_package_label(posting_number: list[str]) -> str:
    """Generate PDF shipping labels for FBS postings. Returns base64-encoded PDF. Max 20 postings."""
    return await _post(
        "/v2/posting/fbs/package-label", {"posting_number": posting_number}
    )


@mcp.tool()
async def fbs_set_tracking_number(
    posting_number: str, tracking_number: str
) -> str:
    """Set tracking number for an FBS shipment."""
    return await _post(
        "/v2/fbs/posting/tracking-number/set",
        {
            "tracking_numbers": [
                {
                    "posting_number": posting_number,
                    "tracking_number": tracking_number,
                }
            ]
        },
    )


@mcp.tool()
async def fbs_act_create(delivery_method_id: int, departure_date: str) -> str:
    """Create a transfer certificate (act) for FBS delivery. departure_date: YYYY-MM-DD or RFC3339."""
    return await _post(
        "/v2/posting/fbs/act/create",
        {
            "delivery_method_id": delivery_method_id,
            "departure_date": _to_rfc3339(departure_date),
        },
    )


@mcp.tool()
async def fbs_act_check_status(id: int) -> str:
    """Check status of a transfer certificate generation."""
    return await _post("/v2/posting/fbs/act/check-status", {"id": id})


# ── FBO Orders (Fulfilled by Ozon) ──────────────────────────────────────────


@mcp.tool()
async def fbo_posting_list(
    limit: int = 50,
    offset: int = 0,
    since: str = "",
    to: str = "",
    status: str = "",
    sort_by: str = "created_at",
    sort_dir: str = "ASC",
) -> str:
    """List FBO shipments. Dates in RFC3339 format or YYYY-MM-DD."""
    body: dict = {"dir": sort_dir, "limit": limit, "offset": offset}
    filt: dict = {}
    if since:
        filt["since"] = _to_rfc3339(since)
    if to:
        filt["to"] = _to_rfc3339(to, is_end=True)
    if status:
        filt["status"] = status
    if filt:
        body["filter"] = filt
    return await _post("/v2/posting/fbo/list", body)


@mcp.tool()
async def fbo_posting_get(posting_number: str) -> str:
    """Get detailed info about a single FBO shipment."""
    return await _post("/v2/posting/fbo/get", {"posting_number": posting_number})


# ── Warehouses ───────────────────────────────────────────────────────────────


@mcp.tool()
async def warehouse_list() -> str:
    """List seller's warehouses."""
    return await _post("/v2/warehouse/list")


@mcp.tool()
async def warehouse_fbo_list(
    search: str = "Москва", supply_types: list[str] | None = None
) -> str:
    """List FBO (Ozon) warehouses for supplies. search: city/address query (min 4 chars). supply_types: ['CREATE_TYPE_DIRECT', 'CREATE_TYPE_CROSSDOCK']."""
    types = supply_types or ["CREATE_TYPE_DIRECT", "CREATE_TYPE_CROSSDOCK"]
    body: dict = {
        "filter_by_supply_type": types,
        "search": search or "Москва",
    }
    return await _post("/v1/warehouse/fbo/list", body)


# ── Categories ───────────────────────────────────────────────────────────────


@mcp.tool()
async def category_tree(language: str = "DEFAULT") -> str:
    """Get the description categories tree (categories and type_ids for product creation/attributes)."""
    return await _post("/v1/description-category/tree", {"language": language})


@mcp.tool()
async def category_attributes(
    description_category_id: int,
    type_id: int,
    language: str = "DEFAULT",
) -> str:
    """Get attributes for a product description category and type."""
    return await _post(
        "/v1/description-category/attribute",
        {
            "description_category_id": description_category_id,
            "type_id": type_id,
            "language": language,
        },
    )


@mcp.tool()
async def category_attribute_values(
    description_category_id: int,
    type_id: int,
    attribute_id: int,
    limit: int = 100,
    last_value_id: int = 0,
) -> str:
    """Get dictionary values for a category attribute."""
    body: dict = {
        "description_category_id": description_category_id,
        "type_id": type_id,
        "attribute_id": attribute_id,
        "limit": limit,
    }
    if last_value_id:
        body["last_value_id"] = last_value_id
    return await _post("/v1/description-category/attribute/values", body)


# ── Analytics ────────────────────────────────────────────────────────────────


@mcp.tool()
async def analytics_data(
    date_from: str,
    date_to: str,
    metrics: list[str],
    dimension: list[str],
    limit: int = 100,
    offset: int = 0,
    sort: list[dict] | None = None,
    filters: list[dict] | None = None,
) -> str:
    """Get analytical data. Metrics: revenue, ordered_units, hits_view, hits_tocart, session_view, conv_tocart_percent, returns, cancellations, delivered_units, adv_sum_all, position_category. Dimensions: sku, spu, day, week, month, year, category1-4, brand."""
    body: dict = {
        "date_from": date_from,
        "date_to": date_to,
        "dimension": dimension,
        "limit": limit,
        "metrics": metrics,
        "offset": offset,
    }
    if sort:
        body["sort"] = sort
    if filters:
        body["filters"] = filters
    return await _post("/v1/analytics/data", body)


@mcp.tool()
async def analytics_stocks(
    limit: int = 100, offset: int = 0, warehouse_type: str = ""
) -> str:
    """Get stock on warehouses report."""
    body: dict = {"limit": limit, "offset": offset}
    if warehouse_type:
        body["warehouse_type"] = warehouse_type
    return await _post("/v2/analytics/stock_on_warehouses", body)


# ── Finance ──────────────────────────────────────────────────────────────────


@mcp.tool()
async def finance_accrual_by_day(date: str) -> str:
    """Get daily financial accruals and fees breakdown. date: YYYY-MM-DD."""
    return await _post("/v1/finance/accrual/by-day", {"date": date})


@mcp.tool()
async def finance_decompensation(date: str) -> str:
    """Get monthly withholdings report (fines, anti-fraud, promotions, insurance). date: YYYY-MM."""
    return await _post("/v1/finance/decompensation", {"date": date})


@mcp.tool()
async def finance_compensation(date: str) -> str:
    """Get monthly compensations report (refunds to seller). date: YYYY-MM."""
    return await _post("/v1/finance/compensation", {"date": date})


@mcp.tool()
async def finance_transactions(
    date_from: str = "",
    date_to: str = "",
    date: str = "",
) -> str:
    """Get financial accruals for a date. Note: Ozon disabled v3 transaction list on July 6, 2026; this retrieves daily accruals via /v1/finance/accrual/by-day."""
    target_date = date or date_from or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if "T" in target_date:
        target_date = target_date.split("T")[0]
    return await _post("/v1/finance/accrual/by-day", {"date": target_date})


@mcp.tool()
async def finance_realization(
    date: str = "", year: int = 0, month: int = 0
) -> str:
    """Get monthly sales/returns realization report. date: YYYY-MM (e.g. 2026-09), or specify year and month."""
    if date and ("-" in date):
        parts = date.split("-")
        y = int(parts[0])
        m = int(parts[1])
    elif year and month:
        y = year
        m = month
    else:
        now = datetime.now(timezone.utc)
        y = now.year if now.month > 1 else now.year - 1
        m = now.month - 1 if now.month > 1 else 12
    return await _post("/v2/finance/realization", {"month": m, "year": y})


# ── Returns ──────────────────────────────────────────────────────────────────


@mcp.tool()
async def returns_report_create(
    date_from: str = "",
    date_to: str = "",
    status: int = 1,
) -> str:
    """Generate a returns report. date_from, date_to: YYYY-MM-DD or RFC3339 (defaults to last 30 days). status: 1 (all/accepted) to 14."""
    now = datetime.now(timezone.utc)
    df = (
        _to_rfc3339(date_from)
        if date_from
        else (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    )
    dt = (
        _to_rfc3339(date_to, is_end=True)
        if date_to
        else now.strftime("%Y-%m-%dT23:59:59Z")
    )
    return await _post(
        "/v2/report/returns/create",
        {"filter": {"date_from": df, "date_to": dt, "status": status}},
    )


# ── Chats ────────────────────────────────────────────────────────────────────


@mcp.tool()
async def chat_list(
    limit: int = 30, offset: int = 0, unread_only: bool = False
) -> str:
    """List chats with buyers. Note: Access requires active Premium Plus subscription."""
    body: dict = {"limit": limit, "offset": offset}
    if unread_only:
        body["filter"] = {"unread_only": True}
    return await _post("/v3/chat/list", body)


@mcp.tool()
async def chat_history(
    chat_id: str, limit: int = 50, from_message_id: int = 0
) -> str:
    """Get chat message history by chat_id/guid. Note: Access requires active Premium Plus subscription."""
    body: dict = {"chat_id": chat_id, "limit": limit}
    if from_message_id:
        body["from_message_id"] = from_message_id
    return await _post("/v3/chat/history", body)


@mcp.tool()
async def chat_send_message(chat_id: str, text: str) -> str:
    """Send a message in a chat with a buyer. Note: Access requires active Premium Plus subscription."""
    return await _post(
        "/v1/chat/send/message", {"chat_id": chat_id, "text": text}
    )


@mcp.tool()
async def chat_start(posting_number: str) -> str:
    """Start a new chat with a buyer by posting number. Note: Access requires active Premium Plus subscription."""
    return await _post("/v1/chat/start", {"posting_number": posting_number})


@mcp.tool()
async def chat_mark_read(chat_id: str) -> str:
    """Mark chat as read by chat_id/guid. Note: Access requires active Premium Plus subscription."""
    return await _post("/v2/chat/read", {"chat_id": chat_id})


# ── Reviews ──────────────────────────────────────────────────────────────────


@mcp.tool()
async def review_list(
    limit: int = 20,
    sort_dir: str = "DESC",
    last_id: str = "",
    is_answered: bool | None = None,
) -> str:
    """List product reviews. Limit must be between 20 and 100 (automatically clamped)."""
    safe_limit = max(20, min(limit, 100))
    body: dict = {"limit": safe_limit, "sort_dir": sort_dir}
    if last_id:
        body["last_id"] = last_id
    if is_answered is not None:
        body["filter"] = {"is_answered": is_answered}
    return await _post("/v1/review/list", body)


@mcp.tool()
async def review_info(review_id: str) -> str:
    """Get details of a single review."""
    return await _post("/v1/review/info", {"review_id": review_id})


@mcp.tool()
async def review_reply(review_id: str, text: str) -> str:
    """Reply to a product review."""
    return await _post(
        "/v1/review/comment/create", {"review_id": review_id, "text": text}
    )


# ── Rating ───────────────────────────────────────────────────────────────────


DEFAULT_RATINGS = [
    "rating_shipment_delay_cb",
    "rating_general_indicator_fbs_rfbs",
    "rating_delivery_complaints_fbo",
    "rating_delivery_complaints_fbs",
    "rating_review_avg_score_total",
]


@mcp.tool()
async def rating_summary() -> str:
    """Get current seller rating summary."""
    return await _post("/v1/rating/summary")


@mcp.tool()
async def rating_history(
    date_from: str = "",
    date_to: str = "",
    ratings: list[str] | None = None,
) -> str:
    """Get seller rating history for a period. Dates: YYYY-MM-DD or RFC3339 (defaults to last 30 days). ratings: list of rating keys (optional, defaults to key metrics)."""
    now = datetime.now(timezone.utc)
    df = (
        _to_rfc3339(date_from)
        if date_from
        else (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    )
    dt = (
        _to_rfc3339(date_to, is_end=True)
        if date_to
        else now.strftime("%Y-%m-%dT23:59:59Z")
    )
    r_list = ratings or DEFAULT_RATINGS
    return await _post(
        "/v1/rating/history",
        {"date_from": df, "date_to": dt, "ratings": r_list},
    )


# ── Promotions ───────────────────────────────────────────────────────────────


@mcp.tool()
async def promotions_list() -> str:
    """List available promotions."""
    return await _get("/v1/actions")


@mcp.tool()
async def promotion_candidates(
    action_id: int, limit: int = 100, offset: int = 0
) -> str:
    """Find products eligible for a promotion."""
    return await _post(
        "/v1/actions/candidates",
        {"action_id": action_id, "limit": limit, "offset": offset},
    )


@mcp.tool()
async def promotion_products(
    action_id: int, limit: int = 100, offset: int = 0
) -> str:
    """Get products already in a promotion."""
    return await _post(
        "/v1/actions/products",
        {"action_id": action_id, "limit": limit, "offset": offset},
    )


@mcp.tool()
async def promotion_products_update(action_id: int, products: list[dict]) -> str:
    """Add, update, or remove products in a promotion based on action_price (POST /v1/actions/products/update).
    Universal method replacing deprecated /v1/actions/products/activate.
    products: list of items [{product_id: int, action_price: number | str | {amount, currency}, stock: optional int}].
    If action_price <= required promo price, product is added; if > promo price, product is removed.
    Max 1000 items.
    """
    normalized_products = []
    for p in products:
        item = dict(p)
        if "action_price" in item and not isinstance(item["action_price"], dict):
            item["action_price"] = _normalize_money(item["action_price"])
        normalized_products.append(item)
    return await _post(
        "/v1/actions/products/update",
        {"action_id": action_id, "products": normalized_products},
    )


@mcp.tool()
async def promotion_activate(action_id: int, products: list[dict]) -> str:
    """Add or update products in a promotion.
    Delegates to modern POST /v1/actions/products/update endpoint.
    products: [{product_id: int, action_price: number | str | {amount, currency}, stock: optional int}].
    """
    return await promotion_products_update(action_id=action_id, products=products)


@mcp.tool()
async def promotion_deactivate(action_id: int, product_ids: list[int]) -> str:
    """Remove products from a promotion (POST /v1/actions/products/deactivate).
    Note: For actions with unified price logic (like elastic boosting), removal is performed
    via promotion_products_update by setting action_price higher than threshold, or via auto_add_products_delete.
    """
    return await _post(
        "/v1/actions/products/deactivate",
        {"action_id": action_id, "product_ids": product_ids},
    )


@mcp.tool()
async def auto_add_products_list(
    action_id: int,
    auto_add_date: str,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """Get list of products in promotion auto-addition (POST /v2/actions/auto-add/products/list).
    action_id: Promotion ID (from promotions_list).
    auto_add_date: Auto-addition date in RFC3339 format (available dates are in auto_add_dates field of promotions_list).
    limit: Number of items to return (1 to 100, default 100).
    offset: Pagination offset (default 0).
    """
    body = {
        "action_id": action_id,
        "auto_add_date": _to_rfc3339(auto_add_date) if "T" not in auto_add_date else auto_add_date,
        "limit": limit,
        "offset": offset,
    }
    return await _post("/v2/actions/auto-add/products/list", body)


@mcp.tool()
async def auto_add_products_candidates(
    action_id: int,
    auto_add_date: str,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """Get list of candidate products eligible for promotion auto-addition (POST /v2/actions/auto-add/products/candidates).
    action_id: Promotion ID (from promotions_list).
    auto_add_date: Auto-addition date in RFC3339 format (from auto_add_dates field of promotions_list).
    limit: Number of items to return (1 to 100, default 100).
    offset: Pagination offset (default 0).
    """
    body = {
        "action_id": action_id,
        "auto_add_date": _to_rfc3339(auto_add_date) if "T" not in auto_add_date else auto_add_date,
        "limit": limit,
        "offset": offset,
    }
    return await _post("/v2/actions/auto-add/products/candidates", body)


@mcp.tool()
async def auto_add_products_delete(
    action_id: int,
    auto_add_date: str,
    product_ids: list[int],
) -> str:
    """Remove products from promotion auto-addition (POST /v2/actions/auto-add/products/delete).
    action_id: Promotion ID.
    auto_add_date: Auto-addition date in RFC3339 format.
    product_ids: List of product IDs to remove (1 to 1000 items).
    """
    body = {
        "action_id": action_id,
        "auto_add_date": _to_rfc3339(auto_add_date) if "T" not in auto_add_date else auto_add_date,
        "product_ids": product_ids,
    }
    return await _post("/v2/actions/auto-add/products/delete", body)


@mcp.tool()
async def auto_add_products_update(
    action_id: int,
    auto_add_date: str,
    products: list[dict],
) -> str:
    """Add or update products in promotion auto-addition (POST /v2/actions/auto-add/products/update).
    action_id: Promotion ID.
    auto_add_date: Auto-addition date in RFC3339 format.
    products: List of product items [{id: int, action_price: optional number | str | {amount, currency}}]. Max 1000 items.
    """
    normalized_products = []
    for p in products:
        item = dict(p)
        if "action_price" in item and not isinstance(item["action_price"], dict):
            item["action_price"] = _normalize_money(item["action_price"])
        normalized_products.append(item)
    body = {
        "action_id": action_id,
        "auto_add_date": _to_rfc3339(auto_add_date) if "T" not in auto_add_date else auto_add_date,
        "products": normalized_products,
    }
    return await _post("/v2/actions/auto-add/products/update", body)


# ── Entry point ──────────────────────────────────────────────────────────────


def main():
    asyncio.run(_run())


async def _run():
    await mcp.run_stdio_async()


if __name__ == "__main__":
    main()
