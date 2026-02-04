#!/usr/bin/env python3
import csv
import io
import json
import os
import time
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from flask import Flask, Response, render_template, request, stream_with_context

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

KEYWORD_SEARCH_URL = "https://app.rakuten.co.jp/services/api/Travel/KeywordHotelSearch/20170426"
DETAIL_SEARCH_URL = "https://app.rakuten.co.jp/services/api/Travel/HotelDetailSearch/20170426"

APP_ID = os.getenv("RAKUTEN_APP_ID", "")
AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", "")

app = Flask(__name__)

def http_get_json(url, timeout=30):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; RakutenTravelCSV/1.0)"})
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return json.loads(data.decode("utf-8"))
    except HTTPError as e:
        logger.error(f"HTTP Error: {e.code} - {e.reason} for URL: {url}")
        # Try to read the error body if possible
        try:
             error_body = e.read().decode("utf-8")
             return json.loads(error_body) # Return the error JSON so caller can parse it
        except:
             pass
        return {"error": f"HTTP {e.code}", "error_description": str(e.reason)}
    except URLError as e:
        logger.error(f"URL Error: {e.reason} for URL: {url}")
        return {"error": "URLError", "error_description": str(e.reason)}
    except Exception as e:
        logger.error(f"General Error: {str(e)} for URL: {url}")
        return {"error": "Exception", "error_description": str(e)}

def build_url(base, params):
    return f"{base}?{urlencode(params)}"

def extract_hotels(keyword_json):
    hotels = []
    if not isinstance(keyword_json, dict):
        return hotels
        
    # Handle API errors inside the JSON response
    if "error" in keyword_json:
        logger.warning(f"API returned error: {keyword_json}")
        return hotels

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
    if not isinstance(detail_json, dict):
        return None
    
    if "hotels" in detail_json and isinstance(detail_json["hotels"], list):
        if not detail_json["hotels"]:
            return None
        first = detail_json["hotels"][0]
        if isinstance(first, dict) and "hotel" in first:
            hotel = first["hotel"]
        else:
            hotel = first
        if isinstance(hotel, dict):
            return hotel.get("hotelRoomNum")
    elif "Hotel" in detail_json: # Some older API versions or structure variations
        return detail_json["Hotel"].get("hotelRoomNum")
    return None

def extract_api_error(payload):
    if isinstance(payload, dict):
        if "error" in payload:
             return f"{payload.get('error')} {payload.get('error_description', '')}".strip()
        if "Error" in payload:
            return str(payload.get("Error"))
        if "errorMessage" in payload:
            return str(payload.get("errorMessage"))
    return None

def fetch_hotels(keyword, hits, max_pages, sleep_sec):
    seen_hotel_no = set()
    total_found = 0
    
    logger.info(f"Starting fetch for keyword='{keyword}', hits={hits}, max_pages={max_pages}")

    for page in range(1, max_pages + 1):
        logger.info(f"Fetching page {page}...")
        
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
            logger.error(f"Keyword search API error on page {page}: {err}")
            # If it's a "not found" or "no auth" error, stop
            if "not_found" in err or "auth" in err:
                 break
            # Otherwise continue perhaps?
            break

        hotels = extract_hotels(keyword_json)
        if not hotels:
            logger.info(f"No more hotels found on page {page}.")
            break

        for h in hotels:
            if not isinstance(h, dict):
                continue
            hotel_no = h.get("hotelNo") or h.get("hotel_no")
            if not hotel_no:
                 continue
                 
            if hotel_no in seen_hotel_no:
                continue
            seen_hotel_no.add(hotel_no)
            total_found += 1

            hotel_name = h.get("hotelName")
            min_charge = h.get("hotelMinCharge")
            url_info = h.get("hotelInformationUrl")
            address = "".join(filter(None, [h.get("address1"), h.get("address2")]))
            tel = h.get("telephoneNo")

            total_rooms = None
            # Only fetch details if we need 'total_rooms' and we have a valid hotel_no
            # Detail API call
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
            # Short sleep before detail call to be nice, but we primarily sleep after the loop
            # time.sleep(0.1) 
            detail_json = http_get_json(detail_url)
            
            # Check error in detail but don't stop the whole process
            detail_err = extract_api_error(detail_json)
            if not detail_err:
                total_rooms = extract_room_num(detail_json)
            else:
                logger.warning(f"Detail API error for hotel {hotel_no}: {detail_err}")

            yield {
                "hotel_name": hotel_name,
                "min_charge": min_charge,
                "url": url_info,
                "address": address,
                "tel": tel,
                "total_rooms": total_rooms,
            }
            
            # Sleep between detail calls if needed to avoid rate limiting
            # The 'sleep_sec' argument was historically for between pages or items? 
            # Let's use it per item if it's small, or per page.
            # Usually Rakuten API limit is 1 request per sec allowed continuously. 
            # We strictly sleep to allow ~1 req/sec combined.
            time.sleep(max(sleep_sec, 0.5)) 

        if len(hotels) < hits:
            logger.info("Retrieved fewer items than requested hits, assuming end of results.")
            break

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html", app_id=APP_ID)

    if not APP_ID:
        return render_template("index.html", app_id=APP_ID, error="RAKUTEN_APP_ID environment variable is missing.")

    keyword = request.form.get("keyword", "貸し別荘").strip() or "貸し別荘"
    try:
        hits = int(request.form.get("hits", "30"))
        max_pages = int(request.form.get("max_pages", "10"))
        sleep_sec = float(request.form.get("sleep", "1.0"))
    except ValueError:
        hits = 30
        max_pages = 5
        sleep_sec = 1.0

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

        try:
            for row in fetch_hotels(keyword, hits, max_pages, sleep_sec):
                writer.writerow(row)
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
        except Exception as e:
            logger.error(f"Error during CSV generation: {e}")
            # In a streaming response, we can't easily change the status code once started.
            # But the user will see the stream stop. Check logs.
            pass

    filename = f"rakuten_hotels_{keyword}.csv"
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
    }
    
    return Response(stream_with_context(generate_csv()), mimetype="text/csv; charset=utf-8", headers=headers)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
