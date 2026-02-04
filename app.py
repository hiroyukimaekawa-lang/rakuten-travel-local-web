#!/usr/bin/env python3
import csv
import io
import json
import os
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Flask, Response, render_template, request

KEYWORD_SEARCH_URL = "https://app.rakuten.co.jp/services/api/Travel/KeywordHotelSearch/20170426"
DETAIL_SEARCH_URL = "https://app.rakuten.co.jp/services/api/Travel/HotelDetailSearch/20170426"

APP_ID = os.getenv("RAKUTEN_APP_ID", "")
AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", "")

app = Flask(__name__)


def http_get_json(url, timeout=30):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; RakutenTravelCSV/1.0)"})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8"))


def build_url(base, params):
    return f"{base}?{urlencode(params)}"


def extract_hotels(keyword_json):
    hotels = []
    if isinstance(keyword_json, dict):
        if "hotels" in keyword_json and isinstance(keyword_json["hotels"], list):
            for h in keyword_json["hotels"]:
                if isinstance(h, dict) and "hotel" in h:
                    hotels.append(h["hotel"])
                else:
                    hotels.append(h)
        elif "Hotels" in keyword_json and isinstance(keyword_json["Hotels"], list):
            for h in keyword_json["Hotels"]:
                if isinstance(h, dict) and "Hotel" in h:
                    hotels.append(h["Hotel"])
    return hotels


def extract_room_num(detail_json):
    if isinstance(detail_json, dict):
        if "hotels" in detail_json and isinstance(detail_json["hotels"], list):
            first = detail_json["hotels"][0]
            if isinstance(first, dict) and "hotel" in first:
                hotel = first["hotel"]
            else:
                hotel = first
            if isinstance(hotel, dict):
                return hotel.get("hotelRoomNum")
        elif "Hotel" in detail_json:
            return detail_json["Hotel"].get("hotelRoomNum")
    return None


def extract_api_error(payload):
    if isinstance(payload, dict):
        if "error" in payload or "error_description" in payload:
            return f"{payload.get('error')} {payload.get('error_description')}".strip()
        if "Error" in payload:
            return str(payload.get("Error"))
        if "errorMessage" in payload:
            return str(payload.get("errorMessage"))
    return None


def fetch_hotels(keyword, hits, max_pages, sleep_sec):
    seen_hotel_no = set()

    for page in range(1, max_pages + 1):
        params = {
            "applicationId": APP_ID,
            "format": "json",
            "formatVersion": 2,
            "keyword": keyword,
            "hits": hits,
            "page": page,
            "responseType": "large",
        }
        if AFFILIATE_ID:
            params["affiliateId"] = AFFILIATE_ID

        url = build_url(KEYWORD_SEARCH_URL, params)
        keyword_json = http_get_json(url)
        err = extract_api_error(keyword_json)
        if err:
            raise RuntimeError(f"Keyword search API error: {err}")

        hotels = extract_hotels(keyword_json)
        if not hotels:
            break

        for h in hotels:
            if not isinstance(h, dict):
                continue
            hotel_no = h.get("hotelNo") or h.get("hotel_no")
            if hotel_no in seen_hotel_no:
                continue
            seen_hotel_no.add(hotel_no)

            hotel_name = h.get("hotelName")
            min_charge = h.get("hotelMinCharge")
            url_info = h.get("hotelInformationUrl")
            address = "".join(filter(None, [h.get("address1"), h.get("address2")]))
            tel = h.get("telephoneNo")

            total_rooms = None
            if hotel_no:
                detail_params = {
                    "applicationId": APP_ID,
                    "format": "json",
                    "formatVersion": 2,
                    "hotelNo": hotel_no,
                    "responseType": "large",
                }
                if AFFILIATE_ID:
                    detail_params["affiliateId"] = AFFILIATE_ID
                detail_url = build_url(DETAIL_SEARCH_URL, detail_params)
                detail_json = http_get_json(detail_url)
                err = extract_api_error(detail_json)
                if not err:
                    total_rooms = extract_room_num(detail_json)

            yield {
                "hotel_name": hotel_name,
                "min_charge": min_charge,
                "url": url_info,
                "address": address,
                "tel": tel,
                "total_rooms": total_rooms,
            }

            time.sleep(sleep_sec)

        if len(hotels) < hits:
            break

        time.sleep(sleep_sec)


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html", app_id=APP_ID)

    if not APP_ID:
        return render_template("index.html", app_id=APP_ID, error="RAKUTEN_APP_ID が設定されていません。")

    keyword = request.form.get("keyword", "貸し別荘").strip() or "貸し別荘"
    hits = int(request.form.get("hits", "30"))
    max_pages = int(request.form.get("max_pages", "10"))
    sleep_sec = float(request.form.get("sleep", "0.5"))

    hits = min(max(hits, 1), 30)
    max_pages = min(max(max_pages, 1), 100)
    sleep_sec = max(sleep_sec, 0.0)

    def generate_csv():
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "hotel_name", "min_charge", "url", "address", "tel", "total_rooms"
        ])
        writer.writeheader()
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for row in fetch_hotels(keyword, hits, max_pages, sleep_sec):
            writer.writerow(row)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = f"rakuten_hotels_{keyword}.csv"
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
    }
    return Response(generate_csv(), mimetype="text/csv; charset=utf-8", headers=headers)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
