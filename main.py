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

AD_ACCOUNT_ID = "act_1769581373920367"   # YOUR REAL AD ACCOUNT ID
GRAPH_VERSION = "v21.0"


def get_token(authorization: str | None):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    scheme, token = parts
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization scheme must be Bearer")
    return token


@app.get("/spend/today")
def spend_today(authorization: str | None = Header(default=None)):
    token = get_token(authorization)

    today = datetime.date.today().isoformat()
    params = {
        "time_range": json.dumps({"since": today, "until": today}),
        "fields": "spend,account_currency",
        "access_token": token
    }

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{AD_ACCOUNT_ID}/insights"
    r = requests.get(url, params=params, timeout=20)

    try:
        data = r.json()
    except:
        raise HTTPException(status_code=500, detail="Meta response invalid")

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=data)

    spend = 0
    currency = None
    if data.get("data"):
        row = data["data"][0]
        spend = float(row.get("spend", 0) or 0)
        currency = row.get("account_currency")

    return {"amount": spend, "currency": currency}
