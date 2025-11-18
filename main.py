from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import datetime
import json

app = FastAPI(title="Meta Ads GPT Bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 👉 Your ad account
AD_ACCOUNT_ID = "act_1769581373920367"
GRAPH_VERSION = "v21.0"

# 👉 1) API key that ChatGPT will send (use the SAME one as in your GPT)
API_KEY = "FIOxMETA_2025_SECRET_KEY_AS25"

# 👉 2) Meta access token from Graph API Explorer (SAME as before)
META_ACCESS_TOKEN = "EAAWLtOqAxxwBP5fdiBQqENm2k2wvjNpudp1CCxwqRhjEuAG9zBMi1TLTVXM1AcLmh8eOi3Y7sKlEPLaQZC6kBYZAz3pDfbMLmt0K7WTKCj1cpTqsBZAz9pcG3qyAA8II2r1dc7d3uxw0cOaYesW9TkUq5l3s98SZAbe7hVCqkYH3QPZBhgQMNXngGNnTa"


def verify_api_key(authorization: str | None):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    scheme, key = parts
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


def get_date_range(days: int):
    """Return since/until ISO dates for last N days (including today)."""
    today = datetime.date.today()
    since = today - datetime.timedelta(days=days - 1)
    return since.isoformat(), today.isoformat()


def extract_action_count(row: dict, action_type: str) -> int:
    """
    Given an insights row and an action_type (e.g. 'lead', 'video_view'),
    return the total count for that action across all actions in the row.
    """
    total = 0
    for action in row.get("actions", []) or []:
        if action.get("action_type") == action_type:
            try:
                total += int(action.get("value", 0) or 0)
            except ValueError:
                continue
    return total


@app.get("/spend/today")
def spend_today(authorization: str | None = Header(default=None)):
    """
    Returns today's total Meta Ads spend.
    """
    verify_api_key(authorization)

    since, until = get_date_range(1)
    params = {
        "time_range": json.dumps({"since": since, "until": until}),
        "fields": "spend,account_currency",
        "access_token": META_ACCESS_TOKEN,
    }

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{AD_ACCOUNT_ID}/insights"
    r = requests.get(url, params=params, timeout=20)

    try:
        data = r.json()
    except Exception:
        raise HTTPException(status_code=500, detail="Meta response invalid")

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=data)

    spend = 0.0
    currency = None
    if data.get("data"):
        row = data["data"][0]
        spend = float(row.get("spend", 0) or 0)
        currency = row.get("account_currency")

    return {"amount": spend, "currency": currency}


@app.get("/insights/campaigns")
def campaign_insights(
    authorization: str | None = Header(default=None),
    days: int = 7,
):
    """
    Campaign-level performance for the last N days (default 7).
    Includes CPL, impressions, clicks, views (video views), etc.
    """
    verify_api_key(authorization)
    if days < 1 or days > 60:
        raise HTTPException(status_code=400, detail="days must be between 1 and 60")

    since, until = get_date_range(days)

    params = {
        "time_range": json.dumps({"since": since, "until": until}),
        "level": "campaign",
        "fields": ",".join(
            [
                "campaign_id",
                "campaign_name",
                "objective",
                "impressions",
                "reach",
                "clicks",
                "spend",
                "cpc",
                "cpm",
                "ctr",
                "actions",        # needed for leads & views
            ]
        ),
        "access_token": META_ACCESS_TOKEN,
    }

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{AD_ACCOUNT_ID}/insights"
    r = requests.get(url, params=params, timeout=30)

    try:
        data = r.json()
    except Exception:
        raise HTTPException(status_code=500, detail="Meta response invalid")

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=data)

    results = []
    for row in data.get("data", []):
        spend = float(row.get("spend", 0) or 0)
        impressions = int(row.get("impressions", 0) or 0)
        clicks = int(row.get("clicks", 0) or 0)
        ctr = float(row.get("ctr", 0) or 0)
        cpc = float(row.get("cpc", 0) or 0)
        cpm = float(row.get("cpm", 0) or 0)

        # Leads and cost per lead (CPL)
        leads = extract_action_count(row, "lead")
        cpl = (spend / leads) if leads > 0 else None

        # Video views (if your campaigns are video; may be 0 if not present)
        video_views = extract_action_count(row, "video_view")

        results.append(
            {
                "campaign_id": row.get("campaign_id"),
                "campaign_name": row.get("campaign_name"),
                "objective": row.get("objective"),
                "impressions": impressions,
                "reach": int(row.get("reach", 0) or 0),
                "clicks": clicks,
                "spend": spend,
                "cpc": cpc,
                "cpm": cpm,
                "ctr": ctr,
                "leads": leads,
                "cpl": cpl,
                "video_views": video_views,
            }
        )

    return {
        "since": since,
        "until": until,
        "campaigns": results,
    }


@app.get("/insights/ads")
def ad_insights(
    authorization: str | None = Header(default=None),
    days: int = 7,
):
    """
    Ad/creative-level performance for the last N days (default 7).
    Includes CPL, impressions, clicks, views (video views), etc.
    """
    verify_api_key(authorization)
    if days < 1 or days > 60:
        raise HTTPException(status_code=400, detail="days must be between 1 and 60")

    since, until = get_date_range(days)

    params = {
        "time_range": json.dumps({"since": since, "until": until}),
        "level": "ad",
        "fields": ",".join(
            [
                "ad_id",
                "ad_name",
                "impressions",
                "reach",
                "clicks",
                "spend",
                "cpc",
                "cpm",
                "ctr",
                "actions",        # needed for leads & views
            ]
        ),
        "access_token": META_ACCESS_TOKEN,
    }

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{AD_ACCOUNT_ID}/insights"
    r = requests.get(url, params=params, timeout=30)

    try:
        data = r.json()
    except Exception:
        raise HTTPException(status_code=500, detail="Meta response invalid")

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=data)

    results = []
    for row in data.get("data", []):
        spend = float(row.get("spend", 0) or 0)
        impressions = int(row.get("impressions", 0) or 0)
        clicks = int(row.get("clicks", 0) or 0)
        ctr = float(row.get("ctr", 0) or 0)
        cpc = float(row.get("cpc", 0) or 0)
        cpm = float(row.get("cpm", 0) or 0)

        leads = extract_action_count(row, "lead")
        cpl = (spend / leads) if leads > 0 else None
        video_views = extract_action_count(row, "video_view")

        results.append(
            {
                "ad_id": row.get("ad_id"),
                "ad_name": row.get("ad_name"),
                "impressions": impressions,
                "reach": int(row.get("reach", 0) or 0),
                "clicks": clicks,
                "spend": spend,
                "cpc": cpc,
                "cpm": cpm,
                "ctr": ctr,
                "leads": leads,
                "cpl": cpl,
                "video_views": video_views,
            }
        )

    return {
        "since": since,
        "until": until,
        "ads": results,
    }
