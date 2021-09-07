from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent
import re
import pandas as pd
import numpy as np
import ast
# import pymorphy2
# from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager

req_params = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
              "Accept-Encoding": "gzip, deflate, br",
              "Accept-Language": "ru-RU, ru; q=0.9",
              # "Host": "httpbin.org",
              "Sec-Fetch-Dest": "document",
              # "Sec-Fetch-Mode": "navigate",
              # "Sec-Fetch-Site": "none",
              "Sec-Fetch-User": "?1",
              # "Upgrade-Insecure-Requests": "1",
              # "X-Amzn-Trace-Id": "Root=1-60ff12e8-229efca73430280304023fb9",
              'Pragma': 'no-cache',
              'referrer': 'https://google.com'
              }

ua = UserAgent(verify_ssl=False, cache=False)


def get_html_page(url, user_agent=ua, params=req_params):
    ses = requests.Session()
    header = {'User-Agent': user_agent.random, **params}
    raw_html = ses.get(url, headers=header)
    raw_html.raise_for_status()
    html_text = raw_html.text.encode(raw_html.encoding)
    soup = BeautifulSoup(html_text, 'html.parser')
    return soup


def split_to_offers(soup):
    offers = []
    offers_raw = soup.find_all('div', {'data-name': 'Offers'})
    if offers_raw:
        offers = offers_raw[0].find_all('article', {'data-name': 'CardComponent'})
    return offers


def get_offer_title(offer_soup):
    offer_title = None
    if offer_soup.select("span[data-mark='OfferTitle']"):
        offer_title = offer_soup.select("span[data-mark='OfferTitle']")[0].text
    return offer_title


def get_offer_subtitle(offer_soup):
    offer_subtitle = None
    if offer_soup.select("span[data-mark='OfferSubtitle']"):
        offer_subtitle = offer_soup.select("span[data-mark='OfferSubtitle']")[0].text
    return offer_subtitle


def parse_title_info(title):
    rooms = np.nan
    meters = np.nan
    floor = np.nan
    total_floor = np.nan

    if title is not None:
        title = title.lower().replace(',', '.')
        raw = title.split()
        if 'м².' in raw:
            idx = raw.index('м².')
            meters = int(float(raw[idx - 1]))

        rooms_raw = raw[0]
        if 'комн' in rooms_raw:
            rooms = rooms_raw.split('комн')[0]
            if '-' in rooms:
                rooms = int(rooms.split('-')[0])
            else:
                rooms = int(rooms)
        elif 'студия' in rooms_raw:
            rooms = 0
        else:
            rooms = np.nan

        if 'этаж' in raw:
            floor, total_floor = int(raw[-2].split('/')[0]), int(raw[-2].split('/')[1])

    return {'rooms': rooms,
            'meters': meters,
            'floor': floor,
            'total_floor': total_floor}


def get_general_info(offer_soup):
    title = get_offer_subtitle(offer_soup)
    if title is None:
        title = get_offer_title(offer_soup)
    return parse_title_info(title)


def get_author(offer_soup):
    author = None
    if offer_soup.select("a[data-name='AgentTitle']"):
        author = offer_soup.select("a[data-name='AgentTitle']")[0].text
    elif offer_soup.select("span[data-name='AgentTitle']"):
        author = offer_soup.select("span[data-name='AgentTitle']")[0].text
    return {'author': author}


# def get_metro_station(offer_soup):
#     station_raw= offer_soup.select("div[data-name='SpecialGeo']")[0].text
#     res = re.split('(\d+)', station_raw)
#     #farness = res[1]
#     return res[0]


def get_full_address(offer_soup):
    address = []
    for geo_label in offer_soup.select("a[data-name='GeoLabel']"):
        address.append(geo_label.text)
    if len(address) == 6:
        address_dict = {'region': address[0],
                        'zone': address[1],
                        'district': address[2],
                        'metro': address[3],
                        'street': address[4],
                        'house': address[5]}
    elif len(address) > 6:
        address_dict = {'region': address[0],
                        'zone': address[1],
                        'district': address[3],
                        'metro': address[2],
                        'street': address[-2],
                        'house': address[-1]}
    elif len(address) < 6:
        address_dict = {'region': address[0],
                        'zone': address[1],
                        'district': address[2],
                        'metro': address[-3],
                        'street': address[-2],
                        'house': address[-1]}
    return address_dict


def get_price(offer_soup):
    price = np.nan
    if offer_soup.select("span[data-mark='MainPrice']"):
        price_raw = offer_soup.select("span[data-mark='MainPrice']")[0].text
        price = int(price_raw.split("₽")[0][:-1].replace(' ', ''))
    return {'price': price}


def get_price_additional_info(offer_soup):
    commission = np.nan
    collateral = np.nan
    if offer_soup.select("p[data-mark='PriceInfo']"):
        desc_raw = offer_soup.select("p[data-mark='PriceInfo']")[0].text
        if "%" in desc_raw:
            commission = int(desc_raw[desc_raw.find("%") - 2: desc_raw.find("%")].replace(" ", ""))
        else:
            commission = 0

        if "\xa0₽" in desc_raw:
            collateral = int(re.split('(\d+)', desc_raw.split('\xa0₽')[0].replace(' ', ''))[-2])
        else:
            collateral = 0

    return {'commission': commission, 'collateral': collateral}


def get_link(offer_soup):
    link = np.nan
    if offer_soup.select("div[data-name='LinkArea']"):
        if offer_soup.select("div[data-name='LinkArea']")[0].select("a"):
            link = offer_soup.select("div[data-name='LinkArea']")[0].select("a")[0].get('href')
    return {'link': link}


def get_time_label(offer_soup):
    time_label = np.nan
    if offer_soup.select("div[data-name='TimeLabel']"):
        time_raw = offer_soup.select("div[data-name='TimeLabel']")[0]
        if time_raw.select('div[class="_93444fe79c--absolute--1BX9t"]'):
            time_label = time_raw.select('div[class="_93444fe79c--absolute--1BX9t"]')[0].text
    return {"time_label": time_label}


def get_coordinates(offer_page):
    # Fucking heuristics
    coordinates = offer_page.find_all('script')[14].text.split('coordinates')[1][2:34]
    coordinates = ast.literal_eval(coordinates)
    return coordinates


def incept_from_offer(offer_soup):
    link = get_link(offer_soup)
    info = get_general_info(offer_soup)
    price = get_price(offer_soup)
    price_info = get_price_additional_info(offer_soup)
    author = get_author(offer_soup)
    full_address = get_full_address(offer_soup)
    time_label = get_time_label(offer_soup)
    res = {**link, **info, **price, **price_info, **author, **full_address, **time_label}
    df = pd.DataFrame.from_dict(res, orient='index').T
    return df


def scrap_page(offers):
    dfs = []
    for offer in offers:
        df = incept_from_offer(offer)
        dfs.append(df)
    return dfs


def build_url_page(url, page_num):
    if page_num == 1:
        return url
    else:
        url_p = url + f'&p={page_num}' + '&region=1&type=-2'
        return url_p


def scrap_cian(url_base, from_page, to_page):
    assert to_page > from_page, "Invalid args"
    dfs = []
    for i in range(from_page, to_page):
        print(f'Current page = {i}/{to_page}')
        url_i = build_url_page(url_base, i)
        soup_i = None
        try:
            soup_i = get_html_page(url_i)
        except Exception as e:
            print(f'Error with loading page = {i}. {e}')

        if soup_i:
            offers_i = split_to_offers(soup_i)
            df_offers = scrap_page(offers_i)
            dfs.extend(df_offers)
        else:
            continue
    return pd.concat(dfs)
