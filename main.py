import re
from datetime import datetime
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from requests_cache import CachedSession

app = FastAPI()
starrail_session = CachedSession('starrail_cache', expire_after=600)
genshin_session = CachedSession('genshin_cache', expire_after=600)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=5000, log_level="info", reload=True)


@app.get("/", include_in_schema=False)
async def docs_redirect():
    return RedirectResponse(url='/docs')


def parse_duration(duration_text):
    if not duration_text:
        return None

    discovered = "Unknown"
    valid_until = "Unknown"

    # Check for "Discovered: <date>" pattern
    discovered_match = re.search(r"Discovered:\s*(\w+\s\d+,\s\d+)", duration_text)
    if discovered_match:
        discovered_date = discovered_match.group(1)
        if discovered_date.lower() not in ["unknown", "indefinite"]:
            discovered = datetime.strptime(discovered_date, "%B %d, %Y").timestamp()

    # Check for "Valid until: <date>" pattern
    valid_until_match = re.search(r"Valid until:\s*(\w+\s\d+,\s\d+|[a-zA-Z]+)", duration_text)
    if valid_until_match:
        valid_until_date = valid_until_match.group(1)
        if valid_until_date.lower() not in ["unknown", "indefinite"]:
            valid_until = datetime.strptime(valid_until_date, "%B %d, %Y").timestamp()

    # Check for "Expired: <date>" pattern
    expired_match = re.search(r"Expired:\s*(\w+\s\d+,\s\d+|[a-zA-Z]+)", duration_text)
    if expired_match:
        expired_date = expired_match.group(1)
        if expired_date.lower() not in ["unknown", "indefinite", ""]:
            valid_until = datetime.strptime(expired_date, "%B %d, %Y").timestamp()

    # Check for "Valid: (<date>)" pattern
    valid_match = re.search(r"Valid:\s*\((\w+)\)", duration_text)
    if valid_match:
        valid_date = valid_match.group(1)
        if valid_date.lower() not in ["unknown", "indefinite"]:
            valid_until = datetime.strptime(valid_date, "%B %d, %Y").timestamp()

    return {
        "discovered": discovered,
        "valid_until": valid_until
    }


def starrail_scrape_table_data():
    url = "https://honkai-star-rail.fandom.com/wiki/Redemption_Code"
    response = starrail_session.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    data = []
    table_rows = soup.find_all("tr")

    for row in table_rows:
        code_elements = row.find_all("code")
        if code_elements:
            code = code_elements[0].text

            redeem_link = row.find("a", {"class": "external"})
            redeem_url = redeem_link["href"] if redeem_link else None

            server = row.find_all("td")[1].text.strip()

            rewards = []
            reward_elements = row.find_all("span", {"class": "item"})
            for reward_element in reward_elements:
                item_name_element = reward_element.find("span", {"class": "item-text"}).find("a")
                item_name = item_name_element.text if item_name_element else None

                item_quantity = re.search(r"×(\d+)", reward_element.text)
                item_quantity = int(item_quantity.group(1)) if item_quantity else None

                image_element = reward_element.find("img")
                if image_element:
                    image_url = image_element.get("data-src")
                    if not image_url:
                        image_url = image_element.get("src")
                        if "nocookie.net" in image_url:
                            image_url = image_url
                    if image_url:
                        image_url = re.sub(r"/revision/.*", "", image_url)
                else:
                    image_url = None

                rewards.append({
                    "name": item_name,
                    "quantity": item_quantity,
                    "image_url": image_url
                })

            duration_element = row.find("td", {"class": ["bg-new", "bg-old"]})
            if duration_element:
                duration = duration_element.text.strip()
                active = "bg-new" in duration_element.get("class", [])
            else:
                duration = None
                active = False

            data.append({
                "code": code,
                "active": active,
                "server": server,
                "redeem_url": redeem_url,
                "rewards": rewards,
                "duration_info": parse_duration(duration)
            })

    return data


def genshin_scrape_table_data():
    url = "https://genshin-impact.fandom.com/wiki/Promotional_Code"
    response = genshin_session.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    data = []
    table_rows = soup.find_all("tr")

    for row in table_rows:
        code_elements = row.find_all("code")
        if code_elements:
            codes = [code.text.strip() for code in code_elements]
            redeem_urls = ["https://genshin.hoyoverse.com/en/gift?code=" + code for code in codes]

            server = row.find_all("td")[1].text.strip()

            rewards = []
            reward_elements = row.find_all("span", {"class": "item"})
            for reward_element in reward_elements:
                item_name_element = reward_element.find("span", {"class": "item-text"}).find("a")
                item_name = item_name_element.text if item_name_element else None

                item_quantity = re.search(r"×(\d+)", reward_element.text)
                item_quantity = int(item_quantity.group(1)) if item_quantity else None

                image_element = reward_element.find("img")
                if image_element:
                    image_url = image_element.get("data-src")
                    if not image_url:
                        image_url = image_element.get("src")
                        if "nocookie.net" in image_url:
                            image_url = image_url
                    if image_url:
                        image_url = re.sub(r"/revision/.*", "", image_url)
                else:
                    image_url = None

                rewards.append({
                    "name": item_name,
                    "quantity": item_quantity,
                    "image_url": image_url
                })

            duration_element = row.find("td", {
                "style": ["background-color:rgb(153,255,153,0.5)", "background-color:rgb(255,153,153,0.5)"]})
            if duration_element:
                duration = duration_element.text.strip()
                active = "background-color:rgb(153,255,153,0.5)" in duration_element.get("style", [])
            else:
                duration = None
                active = False

            # Check if "Notes:" is present in the duration column
            if "Notes:" in duration:
                # If "Notes:" is present, combine codes
                data.append({
                    "code": codes,
                    "redeem_url": redeem_urls,
                    "active": active,
                    "server": server,
                    "rewards": rewards,
                    "duration_info": parse_duration(duration)
                })
            else:
                # If "Notes:" is not present, treat each code separately
                for code, redeem_url in zip(codes, redeem_urls):
                    data.append({
                        "code": code,
                        "redeem_url": redeem_url,
                        "active": active,
                        "server": server,
                        "rewards": rewards,
                        "duration_info": parse_duration(duration)
                    })

    return data


###################
# Star Rail Start #
###################

@app.get("/starrail/redemption-codes")
def get_starrail_redemption_codes():
    data = starrail_scrape_table_data()
    codes = [code for code in data if code["server"] != "China"]
    return {"codes": codes}


@app.get("/starrail/redemption-codes/active")
def get_starrail_active_redemption_codes():
    data = starrail_scrape_table_data()
    active_codes = [code for code in data if code["active"] and code["server"] != "China"]
    return {"codes": active_codes}


@app.get("/starrail/redemption-codes/stellar-jade")
def get_starrail_stellar_jade_redemption_codes():
    data = starrail_scrape_table_data()
    stellar_jade_codes = [code for code in data if
                          any(reward["name"] == "Stellar Jade" for reward in code["rewards"]) and code[
                              "server"] != "China"]
    return {"codes": stellar_jade_codes}


@app.get("/starrail/redemption-codes/china")
def get_starrail_china_redemption_codes():
    data = starrail_scrape_table_data()
    china_codes = [code for code in data if code["server"] == "China" or code["server"] == "All"]
    return {"codes": china_codes}


@app.get("/starrail/redemption-codes/china/active")
def get_starrail_china_active_codes():
    data = starrail_scrape_table_data()
    china_active_codes = [code for code in data if
                          code["active"] and code["server"] == "China" or code["server"] == "All"]
    return {"codes": china_active_codes}


@app.get("/starrail/redemption-codes/china/stellar-jade")
def get_starrail_china_stellar_jade_redemption_codes():
    data = starrail_scrape_table_data()
    china_stellar_jade_codes = [code for code in data if
                                any(reward["name"] == "Stellar Jade" for reward in code["rewards"]) and code[
                                    "server"] == "China" or code["server"] == "All"]
    return {"codes": china_stellar_jade_codes}


#################
# Genshin Start #
#################

@app.get("/genshin/redemption-codes")
def get_genshin_redemption_codes():
    data = genshin_scrape_table_data()
    codes = [code for code in data if code["server"] != "China"]
    return {"codes": codes}


@app.get("/genshin/redemption-codes/active")
def get_genshin_active_redemption_codes():
    data = genshin_scrape_table_data()
    active_codes = [code for code in data if code["active"] and code["server"] != "China"]
    return {"codes": active_codes}


@app.get("/genshin/redemption-codes/primogem")
def get_genshin_primogem_redemption_codes():
    data = genshin_scrape_table_data()
    primogem_codes = [code for code in data if
                      any(reward["name"] == "Primogem" for reward in code["rewards"]) and code["server"] != "China"]
    return {"codes": primogem_codes}


@app.get("/genshin/redemption-codes/china")
def get_genshin_china_redemption_codes():
    data = genshin_scrape_table_data()
    china_codes = [code for code in data if code["server"] == "China" or code["server"] == "All"]
    return {"codes": china_codes}


@app.get("/genshin/redemption-codes/china/active")
def get_genshin_china_active_codes():
    data = genshin_scrape_table_data()
    china_active_codes = [code for code in data if
                          code["active"] and code["server"] == "China" or code["server"] == "All"]
    return {"codes": china_active_codes}


@app.get("/genshin/redemption-codes/china/primogem")
def get_genshin_china_primogem_redemption_codes():
    data = genshin_scrape_table_data()
    china_primogem_codes = [code for code in data if
                            any(reward["name"] == "Primogem" for reward in code["rewards"]) and code[
                                "server"] == "China" or code["server"] == "All"]
    return {"codes": china_primogem_codes}
