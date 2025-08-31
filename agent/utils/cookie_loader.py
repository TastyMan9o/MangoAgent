# agent/utils/cookie_loader.py (API适用版)
# -*- coding: utf-8 -*-
import time
import requests
import browser_cookie3
from typing import Optional, Dict, Any
import os

UA = os.getenv("BILI_UA", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

def generate_qr_code_data() -> Dict[str, Any]:
    '''
    生成用于登录的二维码数据。
    返回包含 url 和 qrcode_key 的字典。
    '''
    print("📲 正在生成二维码数据...")
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": UA})

        get_qrcode_url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
        resp = session.get(get_qrcode_url)
        resp.raise_for_status()
        data = resp.json()["data"]
        return {"url": data["url"], "qrcode_key": data["qrcode_key"]}
    except Exception as e:
        print(f"❌ 生成二维码数据时发生错误: {e}")
        raise

def poll_qr_code_status(qrcode_key: str) -> Dict[str, Any]:
    '''
    轮询二维码的扫描状态。
    '''
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    poll_url = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
    poll_resp = session.get(poll_url, params={"qrcode_key": qrcode_key})
    poll_resp.raise_for_status()

    response_data = poll_resp.json()["data"]

    if response_data.get("code") == 0:
        cookies = poll_resp.cookies
        cookie_str = "; ".join([f"{c.name}={c.value}" for c in cookies])
        response_data["cookie_str"] = cookie_str

    return response_data

def _load_from_browser() -> Optional[str]:
    '''尝试从浏览器加载Cookie'''
    print("🍪 正在尝试从浏览器自动加载 Bilibili Cookie...")
    try:
        cj = browser_cookie3.load(domain_name=".bilibili.com")
        cookie_dict = {}
        for cookie in cj:
            if cookie.name in ["SESSDATA", "bili_jct", "DedeUserID", "buvid3"]:
                cookie_dict[cookie.name] = cookie.value
        if "SESSDATA" in cookie_dict and "bili_jct" in cookie_dict:
            print("✅ 成功从浏览器加载 Cookie！")
            return "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
        else:
            print("⚠️ 未能在浏览器中找到完整的B站登录Cookie。")
            return None
    except Exception as e:
        print(f"❌ 自动加载 Cookie 失败: {e}")
        return None

def get_bili_cookie() -> Optional[str]:
    cookie = _load_from_browser()
    if cookie:
        return cookie
    print("⚠️ 自动加载Cookie失败，请启动UI并通过扫码登录。")
    return None