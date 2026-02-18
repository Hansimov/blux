"""WBI 签名模块。

移植自 bili-scraper/networks/wbi.py，用于对 Bilibili Web 端 API 请求进行 WBI 签名。

WBI 签名流程：
  1. 通过 /x/web-interface/nav 接口获取 img_key 和 sub_key
  2. 将两个 key 拼接后按 MAGIC_KEYS 混淆表重排，取前 32 位作为 magic_key
  3. 将请求参数加上 wts (当前时间戳) 后排序，拼接成 query string
  4. 对 query + magic_key 取 MD5 得到 w_rid，附加到参数中

参考文档：
  - https://socialsisteryi.github.io/bilibili-API-collect/docs/misc/sign/wbi.html
  - https://github.com/SocialSisterYi/bilibili-API-collect/issues/868
  - https://github.com/SocialSisterYi/bilibili-API-collect/issues/885
"""

import json
import math
import random
import requests
import time
import urllib.parse

from functools import reduce
from hashlib import md5

from tclogger import logger, logstr

REQUESTS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
}


class WbiSigner:
    """WBI 参数签名器。

    通过 Bilibili 导航接口获取 img_key / sub_key，
    对请求参数进行 WBI 签名，生成 w_rid 和 wts 参数。
    """

    # https://s1.hdslb.com/bfs/static/jinkela/space/9.space.2132ac79b6ef79e76593b55234927666e0aadac0.js
    # fmt: off
    MAGIC_KEYS = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52
    ]
    # fmt: on

    NAV_URL = "https://api.bilibili.com/x/web-interface/nav"

    def __init__(self, referer: str = "https://www.bilibili.com"):
        self.headers = {**REQUESTS_HEADERS, "Referer": referer}
        self.img_key: str | None = None
        self.sub_key: str | None = None

    def _get_magic_key(self, text: str) -> str:
        """按 MAGIC_KEYS 混淆表对 img_key + sub_key 进行重排，取前 32 位。"""
        return reduce(lambda s, i: s + text[i], self.MAGIC_KEYS, "")[:32]

    def fetch_wbi_keys(self) -> tuple[str, str]:
        """从导航接口获取最新的 img_key 和 sub_key。

        Returns:
            (img_key, sub_key) 元组
        """
        resp = requests.get(self.NAV_URL, headers=self.headers)
        resp.raise_for_status()
        data = resp.json()
        wbi_img = data["data"]["wbi_img"]

        img_url = wbi_img["img_url"]
        sub_url = wbi_img["sub_url"]

        self.img_key = img_url.rsplit("/", 1)[1].split(".")[0]
        self.sub_key = sub_url.rsplit("/", 1)[1].split(".")[0]
        return self.img_key, self.sub_key

    def sign(self, params: dict, wts: int | None = None) -> dict:
        """对请求参数进行 WBI 签名。

        会自动在首次调用时获取 wbi_keys，之后复用缓存的 key。

        Args:
            params: 原始请求参数字典（会被复制，不修改原始数据）
            wts: 指定时间戳，默认使用当前时间

        Returns:
            签名后的参数字典，包含 wts 和 w_rid
        """
        if self.img_key is None or self.sub_key is None:
            self.fetch_wbi_keys()

        magic_key = self._get_magic_key(self.img_key + self.sub_key)

        signed = dict(params)
        signed["wts"] = wts if wts is not None else round(time.time())

        # 按 key 排序
        signed = dict(sorted(signed.items()))

        # 值序列化：dict → compact JSON，其他 → str
        signed = {
            k: json.dumps(v).replace(" ", "") if isinstance(v, dict) else str(v)
            for k, v in signed.items()
        }

        query = urllib.parse.urlencode(signed, quote_via=urllib.parse.quote)
        w_rid = md5((query + magic_key).encode()).hexdigest()
        signed["w_rid"] = w_rid
        return signed


class DmImgParams:
    """生成反爬 dm_img 系列参数。

    这些参数模拟浏览器的窗口尺寸和滚动位置等信息，
    用于通过 Bilibili 的反爬检测。
    """

    def __init__(self, dm_img_str: str = "XXcXXXVXXX"):
        self.dm_img_str = dm_img_str

    @staticmethod
    def _calc_wh(win_width: int = 1920, win_height: int = 1080) -> list[int]:
        i, j = win_width, win_height
        rnd = math.floor(114 * random.random())
        return [2 * i + 2 * j + 3 * rnd, 4 * i - j + rnd, rnd]

    @staticmethod
    def _calc_of(scroll_top: int = 10, scroll_left: int = 10) -> list[int]:
        i, j = scroll_top, scroll_left
        rnd = math.floor(514 * random.random())
        return [3 * i + 2 * j + rnd, 4 * i - 4 * j + 2 * rnd, rnd]

    def get(self) -> dict:
        """生成一组 dm_img 参数。

        Returns:
            包含 dm_img_list, dm_img_str, dm_cover_img_str, dm_img_inter 的字典
        """
        return {
            "dm_img_list": [],
            "dm_img_str": self.dm_img_str,
            "dm_cover_img_str": self.dm_img_str,
            "dm_img_inter": {
                "wh": self._calc_wh(),
                "of": self._calc_of(),
            },
        }


if __name__ == "__main__":
    signer = WbiSigner()
    img_key, sub_key = signer.fetch_wbi_keys()
    logger.success(f"img_key: {logstr.mesg(img_key)}")
    logger.success(f"sub_key: {logstr.mesg(sub_key)}")

    test_params = {"keyword": "test", "page": 1}
    signed = signer.sign(test_params)
    logger.note(f"signed params:")
    for k, v in signed.items():
        logger.mesg(f"  {k}: {v}")

    # python -m blux.wbi
