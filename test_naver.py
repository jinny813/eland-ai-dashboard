import os
import urllib.request
import json
import urllib.parse

client_id = "1aZvlPJmqsJugRyrkysw"
client_secret = "oC7QQkGQWe"

def search_naver(query):
    encText = urllib.parse.quote(query)
    url = "https://openapi.naver.com/v1/search/shop.json?query=" + encText + "&display=10"
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    try:
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        if rescode == 200:
            response_body = response.read()
            data = json.loads(response_body.decode('utf-8'))
            print(f"--- Query: {query} ---")
            for item in data.get("items", []):
                print(f"Title: {item['title'].replace('<b>','').replace('</b>','')}")
                print(f"Brand: {item.get('brand', '')}")
                print(f"Category: {item.get('category3', '')}")
                print("---")
    except Exception as e:
        print("Error:", e)

search_naver("데코 P4H21WBL090")
search_naver("데코 P1G22KP0800")
search_naver("데코 P1G21WBL020")
