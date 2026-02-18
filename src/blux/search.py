"""Bilibili 搜索模块。

提供对 Bilibili Web 端搜索 API 的封装，支持综合搜索和分类搜索。

主要类：
  - SearchResultType: 搜索结果类型枚举
  - SearchOrder: 搜索排序方式枚举
  - VideoItem / MediaItem / LiveRoomItem / LiveUserItem / ArticleItem /
    TopicItem / UserItem / PhotoItem: 各类搜索结果的数据类
  - SearchResult: 综合搜索结果容器
  - TypeSearchResult: 分类搜索结果容器
  - BiliSearcher: 搜索器主类

使用方式：
    from blux.search import BiliSearcher

    searcher = BiliSearcher()
    result = searcher.search_all("红警08")
    for video in result.videos:
        print(video.title, video.play)
"""

import re
import requests
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from tclogger import logger, logstr, dict_to_str

from blux.wbi import WbiSigner, DmImgParams, REQUESTS_HEADERS


# ── 枚举 ───────────────────────────────────────────────────────────────────


class SearchType(str, Enum):
    """分类搜索的目标类型。"""

    VIDEO = "video"
    MEDIA_BANGUMI = "media_bangumi"
    MEDIA_FT = "media_ft"
    LIVE = "live"
    LIVE_ROOM = "live_room"
    LIVE_USER = "live_user"
    ARTICLE = "article"
    TOPIC = "topic"
    BILI_USER = "bili_user"
    PHOTO = "photo"


class SearchOrder(str, Enum):
    """搜索排序方式。"""

    # 视频/专栏/相簿
    TOTALRANK = "totalrank"  # 综合排序
    CLICK = "click"  # 最多点击
    PUBDATE = "pubdate"  # 最新发布
    DM = "dm"  # 最多弹幕
    STOW = "stow"  # 最多收藏
    SCORES = "scores"  # 最多评论
    ATTENTION = "attention"  # 最多喜欢（仅专栏）

    # 直播间
    ONLINE = "online"  # 人气直播
    LIVE_TIME = "live_time"  # 最新开播

    # 用户
    DEFAULT = "0"  # 默认排序
    FANS = "fans"  # 粉丝数
    LEVEL = "level"  # 用户等级


class VideoDuration(int, Enum):
    """视频时长筛选。"""

    ALL = 0  # 全部时长
    UNDER_10MIN = 1  # 10分钟以下
    TEN_TO_30MIN = 2  # 10-30分钟
    THIRTY_TO_60MIN = 3  # 30-60分钟
    OVER_60MIN = 4  # 60分钟以上


class UserType(int, Enum):
    """用户分类筛选。"""

    ALL = 0  # 全部用户
    UP = 1  # UP主
    NORMAL = 2  # 普通用户
    VERIFIED = 3  # 认证用户


# ── 工具函数 ────────────────────────────────────────────────────────────────


def strip_html_tags(text: str) -> str:
    """去除 HTML 标签（如 <em class="keyword"> ）。"""
    if not text:
        return text
    return re.sub(r"<[^>]+>", "", text)


def safe_int(value: Any, default: int = 0) -> int:
    """安全转换为 int。"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# ── 数据类 ──────────────────────────────────────────────────────────────────


@dataclass
class VideoItem:
    """视频搜索结果条目。"""

    type: str = "video"
    aid: int = 0
    bvid: str = ""
    title: str = ""
    title_raw: str = ""  # 带 HTML 标记的原始标题
    description: str = ""
    author: str = ""
    mid: int = 0
    typeid: str = ""
    typename: str = ""
    arcurl: str = ""
    pic: str = ""
    play: int = 0
    video_review: int = 0  # 弹幕数
    favorites: int = 0
    tag: str = ""
    review: int = 0  # 评论数
    pubdate: int = 0
    senddate: int = 0
    duration: str = ""
    hit_columns: list[str] = field(default_factory=list)
    rank_score: int = 0
    is_pay: int = 0
    is_union_video: int = 0
    like: int = 0
    coin: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "VideoItem":
        title_raw = data.get("title", "")
        return cls(
            type=data.get("type", "video"),
            aid=safe_int(data.get("aid", data.get("id", 0))),
            bvid=data.get("bvid", ""),
            title=strip_html_tags(title_raw),
            title_raw=title_raw,
            description=data.get("description", ""),
            author=data.get("author", ""),
            mid=safe_int(data.get("mid", 0)),
            typeid=str(data.get("typeid", "")),
            typename=data.get("typename", ""),
            arcurl=data.get("arcurl", ""),
            pic=data.get("pic", ""),
            play=safe_int(data.get("play", 0)),
            video_review=safe_int(data.get("video_review", 0)),
            favorites=safe_int(data.get("favorites", 0)),
            tag=data.get("tag", ""),
            review=safe_int(data.get("review", 0)),
            pubdate=safe_int(data.get("pubdate", 0)),
            senddate=safe_int(data.get("senddate", 0)),
            duration=data.get("duration", ""),
            hit_columns=data.get("hit_columns", []) or [],
            rank_score=safe_int(data.get("rank_score", 0)),
            is_pay=safe_int(data.get("is_pay", 0)),
            is_union_video=safe_int(data.get("is_union_video", 0)),
            like=safe_int(data.get("like", 0)),
            coin=safe_int(data.get("coin", 0)),
        )

    def summary(self) -> str:
        return (
            f"[{self.bvid}] {self.title}\n"
            f"  UP: {self.author} (mid={self.mid})  分区: {self.typename}\n"
            f"  播放: {self.play}  弹幕: {self.video_review}  "
            f"收藏: {self.favorites}  评论: {self.review}\n"
            f"  时长: {self.duration}  发布: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.pubdate))}"
        )


@dataclass
class MediaItem:
    """番剧/影视搜索结果条目。"""

    type: str = ""  # media_bangumi / media_ft
    media_id: int = 0
    season_id: int = 0
    title: str = ""
    title_raw: str = ""
    org_title: str = ""
    cover: str = ""
    media_type: int = 0  # 1:番剧 2:电影 3:纪录片 4:国创 5:电视剧 7:综艺
    areas: str = ""
    styles: str = ""
    cv: str = ""
    staff: str = ""
    goto_url: str = ""
    desc: str = ""
    pubtime: int = 0
    media_score: dict | None = None  # {"user_count": int, "score": float}
    season_type_name: str = ""
    ep_size: int = 0
    eps: list[dict] = field(default_factory=list)
    hit_columns: list[str] = field(default_factory=list)
    url: str = ""
    badges: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "MediaItem":
        title_raw = data.get("title", "")
        return cls(
            type=data.get("type", ""),
            media_id=safe_int(data.get("media_id", 0)),
            season_id=safe_int(data.get("season_id", 0)),
            title=strip_html_tags(title_raw),
            title_raw=title_raw,
            org_title=strip_html_tags(data.get("org_title", "")),
            cover=data.get("cover", ""),
            media_type=safe_int(data.get("media_type", 0)),
            areas=data.get("areas", ""),
            styles=data.get("styles", ""),
            cv=data.get("cv", ""),
            staff=data.get("staff", ""),
            goto_url=data.get("goto_url", ""),
            desc=data.get("desc", ""),
            pubtime=safe_int(data.get("pubtime", 0)),
            media_score=data.get("media_score"),
            season_type_name=data.get("season_type_name", ""),
            ep_size=safe_int(data.get("ep_size", 0)),
            eps=data.get("eps", []) or [],
            hit_columns=data.get("hit_columns", []) or [],
            url=data.get("url", ""),
            badges=data.get("badges", []) or [],
        )

    @property
    def media_type_name(self) -> str:
        _MAP = {1: "番剧", 2: "电影", 3: "纪录片", 4: "国创", 5: "电视剧", 7: "综艺"}
        return _MAP.get(self.media_type, f"未知({self.media_type})")

    @property
    def score(self) -> float | None:
        if self.media_score and isinstance(self.media_score, dict):
            return self.media_score.get("score")
        return None

    @property
    def score_count(self) -> int:
        if self.media_score and isinstance(self.media_score, dict):
            return safe_int(self.media_score.get("user_count", 0))
        return 0

    def summary(self) -> str:
        score_str = f"  评分: {self.score} ({self.score_count}人)" if self.score else ""
        return (
            f"[{self.media_type_name}] {self.title}\n"
            f"  ssid={self.season_id}  地区: {self.areas}  风格: {self.styles}\n"
            f"  集数: {self.ep_size}  类型: {self.season_type_name}{score_str}"
        )


@dataclass
class LiveRoomItem:
    """直播间搜索结果条目。"""

    type: str = "live_room"
    roomid: int = 0
    uid: int = 0
    title: str = ""
    title_raw: str = ""
    uname: str = ""
    uface: str = ""
    cover: str = ""
    user_cover: str = ""
    online: int = 0
    attentions: int = 0
    cate_name: str = ""
    live_time: str = ""
    tags: str = ""
    hit_columns: list[str] = field(default_factory=list)
    rank_score: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "LiveRoomItem":
        title_raw = data.get("title", "")
        return cls(
            type=data.get("type", "live_room"),
            roomid=safe_int(data.get("roomid", 0)),
            uid=safe_int(data.get("uid", 0)),
            title=strip_html_tags(title_raw),
            title_raw=title_raw,
            uname=data.get("uname", ""),
            uface=data.get("uface", ""),
            cover=data.get("cover", ""),
            user_cover=data.get("user_cover", ""),
            online=safe_int(data.get("online", 0)),
            attentions=safe_int(data.get("attentions", 0)),
            cate_name=data.get("cate_name", ""),
            live_time=data.get("live_time", ""),
            tags=data.get("tags", ""),
            hit_columns=data.get("hit_columns", []) or [],
            rank_score=safe_int(data.get("rank_score", 0)),
        )

    def summary(self) -> str:
        return (
            f"[直播间 {self.roomid}] {self.title}\n"
            f"  主播: {self.uname} (uid={self.uid})  分区: {self.cate_name}\n"
            f"  在线: {self.online}  粉丝: {self.attentions}"
        )


@dataclass
class LiveUserItem:
    """主播搜索结果条目。"""

    type: str = "live_user"
    uid: int = 0
    uname: str = ""
    uname_raw: str = ""
    uface: str = ""
    is_live: bool = False
    live_status: int = 0
    roomid: int = 0
    attentions: int = 0
    tags: str = ""
    live_time: str = ""
    hit_columns: list[str] = field(default_factory=list)
    rank_score: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "LiveUserItem":
        uname_raw = data.get("uname", "")
        return cls(
            type=data.get("type", "live_user"),
            uid=safe_int(data.get("uid", 0)),
            uname=strip_html_tags(uname_raw),
            uname_raw=uname_raw,
            uface=data.get("uface", ""),
            is_live=bool(data.get("is_live", False)),
            live_status=safe_int(data.get("live_status", 0)),
            roomid=safe_int(data.get("roomid", 0)),
            attentions=safe_int(data.get("attentions", 0)),
            tags=data.get("tags", ""),
            live_time=data.get("live_time", ""),
            hit_columns=data.get("hit_columns", []) or [],
            rank_score=safe_int(data.get("rank_score", 0)),
        )

    def summary(self) -> str:
        status = "直播中" if self.is_live else "未开播"
        return (
            f"[主播] {self.uname} (uid={self.uid})\n"
            f"  状态: {status}  房间: {self.roomid}  粉丝: {self.attentions}"
        )


@dataclass
class ArticleItem:
    """专栏搜索结果条目。"""

    type: str = "article"
    id: int = 0
    title: str = ""
    title_raw: str = ""
    mid: int = 0
    desc: str = ""
    image_urls: list[str] = field(default_factory=list)
    view: int = 0
    like: int = 0
    reply: int = 0
    pub_time: int = 0
    category_name: str = ""
    category_id: int = 0
    rank_score: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "ArticleItem":
        title_raw = data.get("title", "")
        return cls(
            type=data.get("type", "article"),
            id=safe_int(data.get("id", 0)),
            title=strip_html_tags(title_raw),
            title_raw=title_raw,
            mid=safe_int(data.get("mid", 0)),
            desc=data.get("desc", ""),
            image_urls=data.get("image_urls", []) or [],
            view=safe_int(data.get("view", 0)),
            like=safe_int(data.get("like", 0)),
            reply=safe_int(data.get("reply", 0)),
            pub_time=safe_int(data.get("pub_time", 0)),
            category_name=data.get("category_name", ""),
            category_id=safe_int(data.get("category_id", 0)),
            rank_score=safe_int(data.get("rank_score", 0)),
        )

    def summary(self) -> str:
        return (
            f"[专栏 cv{self.id}] {self.title}\n"
            f"  分区: {self.category_name}  阅读: {self.view}  "
            f"点赞: {self.like}  评论: {self.reply}"
        )


@dataclass
class TopicItem:
    """话题搜索结果条目。"""

    type: str = "topic"
    tp_id: int = 0
    title: str = ""
    title_raw: str = ""
    description: str = ""
    author: str = ""
    cover: str = ""
    arcurl: str = ""
    click: int = 0
    pubdate: int = 0
    update: int = 0
    hit_columns: list[str] = field(default_factory=list)
    rank_score: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "TopicItem":
        title_raw = data.get("title", "")
        return cls(
            type=data.get("type", "topic"),
            tp_id=safe_int(data.get("tp_id", 0)),
            title=strip_html_tags(title_raw),
            title_raw=title_raw,
            description=data.get("description", ""),
            author=data.get("author", ""),
            cover=data.get("cover", ""),
            arcurl=data.get("arcurl", ""),
            click=safe_int(data.get("click", 0)),
            pubdate=safe_int(data.get("pubdate", 0)),
            update=safe_int(data.get("update", 0)),
            hit_columns=data.get("hit_columns", []) or [],
            rank_score=safe_int(data.get("rank_score", 0)),
        )

    def summary(self) -> str:
        return (
            f"[话题 tp{self.tp_id}] {self.title}\n"
            f"  作者: {self.author}  点击: {self.click}"
        )


@dataclass
class UserItem:
    """用户搜索结果条目。"""

    type: str = "bili_user"
    mid: int = 0
    uname: str = ""
    usign: str = ""
    fans: int = 0
    videos: int = 0
    upic: str = ""
    level: int = 0
    gender: int = 0  # 1:男 2:女 3:私密
    is_upuser: int = 0
    is_live: int = 0
    room_id: int = 0
    official_verify: dict | None = None
    res: list[dict] = field(default_factory=list)
    hit_columns: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "UserItem":
        return cls(
            type=data.get("type", "bili_user"),
            mid=safe_int(data.get("mid", 0)),
            uname=data.get("uname", ""),
            usign=data.get("usign", ""),
            fans=safe_int(data.get("fans", 0)),
            videos=safe_int(data.get("videos", 0)),
            upic=data.get("upic", ""),
            level=safe_int(data.get("level", 0)),
            gender=safe_int(data.get("gender", 0)),
            is_upuser=safe_int(data.get("is_upuser", 0)),
            is_live=safe_int(data.get("is_live", 0)),
            room_id=safe_int(data.get("room_id", 0)),
            official_verify=data.get("official_verify"),
            res=data.get("res", []) or [],
            hit_columns=data.get("hit_columns", []) or [],
        )

    @property
    def gender_str(self) -> str:
        return {1: "男", 2: "女", 3: "私密"}.get(self.gender, "未知")

    @property
    def verify_desc(self) -> str:
        if self.official_verify and isinstance(self.official_verify, dict):
            return self.official_verify.get("desc", "")
        return ""

    def summary(self) -> str:
        verify = f"  认证: {self.verify_desc}" if self.verify_desc else ""
        return (
            f"[用户] {self.uname} (mid={self.mid})\n"
            f"  等级: {self.level}  粉丝: {self.fans}  投稿: {self.videos}{verify}"
        )


@dataclass
class PhotoItem:
    """相簿搜索结果条目。"""

    type: str = "photo"
    id: int = 0
    title: str = ""
    title_raw: str = ""
    cover: str = ""
    count: int = 0
    mid: int = 0
    uname: str = ""
    view: int = 0
    like: int = 0
    hit_columns: list[str] = field(default_factory=list)
    rank_score: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "PhotoItem":
        title_raw = data.get("title", "")
        return cls(
            type=data.get("type", "photo"),
            id=safe_int(data.get("id", 0)),
            title=strip_html_tags(title_raw),
            title_raw=title_raw,
            cover=data.get("cover", ""),
            count=safe_int(data.get("count", 0)),
            mid=safe_int(data.get("mid", 0)),
            uname=data.get("uname", ""),
            view=safe_int(data.get("view", 0)),
            like=safe_int(data.get("like", 0)),
            hit_columns=data.get("hit_columns", []) or [],
            rank_score=safe_int(data.get("rank_score", 0)),
        )

    def summary(self) -> str:
        return (
            f"[相簿 {self.id}] {self.title}\n"
            f"  UP: {self.uname}  图片: {self.count}  浏览: {self.view}  收藏: {self.like}"
        )


# ── 结果解析器 ──────────────────────────────────────────────────────────────

# result_type → ItemClass 映射
_ITEM_PARSERS: dict[str, type] = {
    "video": VideoItem,
    "media_bangumi": MediaItem,
    "media_ft": MediaItem,
    "live_room": LiveRoomItem,
    "live_user": LiveUserItem,
    "article": ArticleItem,
    "topic": TopicItem,
    "bili_user": UserItem,
    "photo": PhotoItem,
}


def parse_result_items(result_type: str, data_list: list[dict]) -> list:
    """将原始 API 数据列表解析为对应的数据类实例列表。"""
    parser_cls = _ITEM_PARSERS.get(result_type)
    if parser_cls is None:
        return data_list  # 未知类型，保留原始数据
    return [parser_cls.from_dict(item) for item in data_list if item]


# ── 搜索结果容器 ────────────────────────────────────────────────────────────


@dataclass
class PageInfo:
    """分页信息。"""

    num_results: int = 0
    total: int = 0
    pages: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "PageInfo":
        return cls(
            num_results=safe_int(data.get("numResults", 0)),
            total=safe_int(data.get("total", 0)),
            pages=safe_int(data.get("pages", 0)),
        )


class SearchAllResult:
    """综合搜索结果容器。

    封装综合搜索 API 返回的完整结果，自动解析各类型数据。
    """

    def __init__(self, raw: dict):
        self.raw = raw
        self.code: int = raw.get("code", -1)
        self.message: str = raw.get("message", "")

        data = raw.get("data") or {}
        self.seid: str = str(data.get("seid", ""))
        self.page: int = safe_int(data.get("page", 1))
        self.page_size: int = safe_int(data.get("pagesize", 20))
        self.num_results: int = safe_int(data.get("numResults", 0))
        self.num_pages: int = safe_int(data.get("numPages", 0))
        self.suggest_keyword: str = data.get("suggest_keyword", "")
        self.cost_time: dict = data.get("cost_time", {})

        # 分类结果数目
        self.top_tlist: dict = data.get("top_tlist", {}) or {}

        # 分类页数信息
        self.pageinfo: dict[str, PageInfo] = {}
        raw_pageinfo = data.get("pageinfo", {}) or {}
        for key, val in raw_pageinfo.items():
            if isinstance(val, dict):
                self.pageinfo[key] = PageInfo.from_dict(val)

        # 解析各类型结果
        self.videos: list[VideoItem] = []
        self.media_bangumi: list[MediaItem] = []
        self.media_ft: list[MediaItem] = []
        self.live_rooms: list[LiveRoomItem] = []
        self.live_users: list[LiveUserItem] = []
        self.articles: list[ArticleItem] = []
        self.topics: list[TopicItem] = []
        self.users: list[UserItem] = []
        self.photos: list[PhotoItem] = []
        self.other_results: dict[str, list] = {}

        self._parse_results(data.get("result", []) or [])

    def _parse_results(self, results: list[dict]):
        """解析综合搜索返回的 result 数组。"""
        _attr_map = {
            "video": "videos",
            "media_bangumi": "media_bangumi",
            "media_ft": "media_ft",
            "live_room": "live_rooms",
            "live_user": "live_users",
            "article": "articles",
            "topic": "topics",
            "bili_user": "users",
            "photo": "photos",
        }
        for group in results:
            if not isinstance(group, dict):
                continue
            result_type = group.get("result_type", "")
            data_list = group.get("data", []) or []
            if not data_list:
                continue
            items = parse_result_items(result_type, data_list)
            attr = _attr_map.get(result_type)
            if attr:
                setattr(self, attr, items)
            else:
                self.other_results[result_type] = items

    @property
    def ok(self) -> bool:
        return self.code == 0

    def summary(self) -> str:
        """生成搜索结果摘要。"""
        lines = [
            f"搜索结果 (code={self.code}, num_results={self.num_results}, pages={self.num_pages})",
        ]
        if self.top_tlist:
            counts = {
                k: v
                for k, v in self.top_tlist.items()
                if isinstance(v, (int, float)) and v > 0
            }
            if counts:
                lines.append(f"  各类数量: {counts}")

        type_counts = {
            "视频": len(self.videos),
            "番剧": len(self.media_bangumi),
            "影视": len(self.media_ft),
            "直播间": len(self.live_rooms),
            "主播": len(self.live_users),
            "专栏": len(self.articles),
            "话题": len(self.topics),
            "用户": len(self.users),
            "相簿": len(self.photos),
        }
        non_zero = {k: v for k, v in type_counts.items() if v > 0}
        if non_zero:
            lines.append(f"  本次返回: {non_zero}")

        return "\n".join(lines)


class SearchTypeResult:
    """分类搜索结果容器。

    封装分类搜索 API 返回的结果，解析指定类型的数据。
    """

    def __init__(self, raw: dict, search_type: str):
        self.raw = raw
        self.search_type = search_type
        self.code: int = raw.get("code", -1)
        self.message: str = raw.get("message", "")

        data = raw.get("data") or {}
        self.seid: str = str(data.get("seid", ""))
        self.page: int = safe_int(data.get("page", 1))
        self.page_size: int = safe_int(data.get("pagesize", 20))
        self.num_results: int = safe_int(data.get("numResults", 0))
        self.num_pages: int = safe_int(data.get("numPages", 0))
        self.cost_time: dict = data.get("cost_time", {})

        self.items: list = []
        self._parse_results(data)

    def _parse_results(self, data: dict):
        """解析分类搜索返回的 result。"""
        raw_result = data.get("result")
        if raw_result is None:
            return

        # 直播搜索的结果是 obj 而非 array
        if self.search_type == SearchType.LIVE.value:
            if isinstance(raw_result, dict):
                rooms = raw_result.get("live_room", []) or []
                users = raw_result.get("live_user", []) or []
                self.live_rooms = parse_result_items("live_room", rooms)
                self.live_users = parse_result_items("live_user", users)
                self.items = self.live_rooms + self.live_users
            return

        if isinstance(raw_result, list):
            self.items = parse_result_items(self.search_type, raw_result)

    @property
    def ok(self) -> bool:
        return self.code == 0

    def summary(self) -> str:
        return (
            f"分类搜索 [{self.search_type}] "
            f"(code={self.code}, page={self.page}, "
            f"num_results={self.num_results}, pages={self.num_pages}, "
            f"items={len(self.items)})"
        )


# ── 搜索器 ─────────────────────────────────────────────────────────────────


class BiliSearcher:
    """Bilibili 搜索器。

    提供综合搜索和分类搜索两种接口，自动处理 WBI 签名和 Cookie 获取。

    Usage:
        searcher = BiliSearcher()
        result = searcher.search_all("红警08")
        print(result.summary())

        typed = searcher.search_type("教父", search_type=SearchType.VIDEO)
        for item in typed.items:
            print(item.summary())
    """

    SEARCH_ALL_URL = "https://api.bilibili.com/x/web-interface/wbi/search/all/v2"
    SEARCH_TYPE_URL = "https://api.bilibili.com/x/web-interface/wbi/search/type"
    BILIBILI_HOME = "https://www.bilibili.com"

    def __init__(self, sessdata: str = ""):
        self.wbi_signer = WbiSigner(referer="https://www.bilibili.com")
        self.dm_params = DmImgParams()
        self.session = requests.Session()
        self.session.headers.update(
            {
                **REQUESTS_HEADERS,
                "Referer": "https://www.bilibili.com",
            }
        )
        if sessdata:
            self.session.cookies.set("SESSDATA", sessdata, domain=".bilibili.com")
        self._cookies_initialized = False

    def _ensure_cookies(self):
        """确保 Cookie 中包含必要的字段（buvid3 等）。

        通过访问 bilibili.com 首页来获取必要的 Cookie。
        """
        if self._cookies_initialized:
            return
        try:
            resp = self.session.get(self.BILIBILI_HOME, timeout=10)
            resp.raise_for_status()
            self._cookies_initialized = True
            cookie_names = list(self.session.cookies.keys())
            logger.success(f"获取 Cookie 成功: {logstr.mesg(', '.join(cookie_names))}")
        except Exception as e:
            logger.warn(f"获取 Cookie 失败: {e}")

    def _build_signed_params(self, params: dict) -> dict:
        """构建带 WBI 签名和 dm_img 参数的完整请求参数。"""
        dm = self.dm_params.get()
        full_params = {**params, **dm}
        return self.wbi_signer.sign(full_params)

    def search_all(self, keyword: str, **extra_params) -> SearchAllResult:
        """综合搜索。

        Args:
            keyword: 搜索关键词
            **extra_params: 额外的请求参数

        Returns:
            SearchAllResult 搜索结果对象
        """
        self._ensure_cookies()

        params = {"keyword": keyword, **extra_params}
        signed = self._build_signed_params(params)

        logger.note(f"> 综合搜索: keyword={logstr.mesg(keyword)}")

        try:
            resp = self.session.get(self.SEARCH_ALL_URL, params=signed, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.err(f"搜索请求失败: {e}")
            data = {"code": -1, "message": str(e)}

        result = SearchAllResult(data)
        if result.ok:
            logger.success(f"  {result.summary()}")
        else:
            logger.warn(f"  搜索失败: code={result.code}, message={result.message}")

        return result

    def search_by_type(
        self,
        keyword: str,
        search_type: str | SearchType = SearchType.VIDEO,
        order: str | SearchOrder = "",
        page: int = 1,
        duration: int | VideoDuration = 0,
        tids: int = 0,
        order_sort: int = 0,
        user_type: int | UserType = 0,
        category_id: int = 0,
        **extra_params,
    ) -> SearchTypeResult:
        """分类搜索。

        Args:
            keyword: 搜索关键词
            search_type: 搜索类型
            order: 排序方式
            page: 页码，默认 1
            duration: 视频时长筛选（仅搜索视频有效）
            tids: 视频分区筛选（仅搜索视频有效）
            order_sort: 排序方向（仅搜索用户有效），0=降序 1=升序
            user_type: 用户类型筛选（仅搜索用户有效）
            category_id: 分区筛选（专栏/相簿）
            **extra_params: 额外的请求参数

        Returns:
            SearchTypeResult 搜索结果对象
        """
        self._ensure_cookies()

        st = search_type.value if isinstance(search_type, SearchType) else search_type

        params: dict[str, Any] = {
            "keyword": keyword,
            "search_type": st,
            "page": page,
        }

        # 按需添加可选参数
        if order:
            params["order"] = order.value if isinstance(order, SearchOrder) else order
        if duration:
            params["duration"] = (
                duration.value if isinstance(duration, VideoDuration) else duration
            )
        if tids:
            params["tids"] = tids
        if order_sort:
            params["order_sort"] = order_sort
        if user_type:
            params["user_type"] = (
                user_type.value if isinstance(user_type, UserType) else user_type
            )
        if category_id:
            params["category_id"] = category_id

        params.update(extra_params)
        signed = self._build_signed_params(params)

        logger.note(
            f"> 分类搜索: keyword={logstr.mesg(keyword)}, "
            f"type={logstr.mesg(st)}, page={page}"
        )

        try:
            resp = self.session.get(self.SEARCH_TYPE_URL, params=signed, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.err(f"搜索请求失败: {e}")
            data = {"code": -1, "message": str(e)}

        result = SearchTypeResult(data, st)
        if result.ok:
            logger.success(f"  {result.summary()}")
        else:
            logger.warn(f"  搜索失败: code={result.code}, message={result.message}")

        return result

    def search_videos(
        self,
        keyword: str,
        order: str | SearchOrder = SearchOrder.TOTALRANK,
        page: int = 1,
        duration: int | VideoDuration = VideoDuration.ALL,
        tids: int = 0,
        **extra_params,
    ) -> SearchTypeResult:
        """搜索视频的便捷方法。

        Args:
            keyword: 搜索关键词
            order: 排序方式
            page: 页码
            duration: 时长筛选
            tids: 分区筛选
            **extra_params: 额外参数

        Returns:
            SearchTypeResult 结果（items 为 VideoItem 列表）
        """
        return self.search_by_type(
            keyword=keyword,
            search_type=SearchType.VIDEO,
            order=order,
            page=page,
            duration=duration,
            tids=tids,
            **extra_params,
        )

    def search_users(
        self,
        keyword: str,
        order: str | SearchOrder = SearchOrder.DEFAULT,
        order_sort: int = 0,
        user_type: int | UserType = UserType.ALL,
        page: int = 1,
        **extra_params,
    ) -> SearchTypeResult:
        """搜索用户的便捷方法。"""
        return self.search_by_type(
            keyword=keyword,
            search_type=SearchType.BILI_USER,
            order=order,
            order_sort=order_sort,
            user_type=user_type,
            page=page,
            **extra_params,
        )

    def search_media_bangumi(
        self, keyword: str, page: int = 1, **extra_params
    ) -> SearchTypeResult:
        """搜索番剧的便捷方法。"""
        return self.search_by_type(
            keyword=keyword,
            search_type=SearchType.MEDIA_BANGUMI,
            page=page,
            **extra_params,
        )

    def search_media_ft(
        self, keyword: str, page: int = 1, **extra_params
    ) -> SearchTypeResult:
        """搜索影视的便捷方法。"""
        return self.search_by_type(
            keyword=keyword,
            search_type=SearchType.MEDIA_FT,
            page=page,
            **extra_params,
        )

    def search_articles(
        self, keyword: str, page: int = 1, **extra_params
    ) -> SearchTypeResult:
        """搜索专栏的便捷方法。"""
        return self.search_by_type(
            keyword=keyword,
            search_type=SearchType.ARTICLE,
            page=page,
            **extra_params,
        )


if __name__ == "__main__":
    searcher = BiliSearcher()

    # 综合搜索测试
    result = searcher.search_all("洛天依")
    print(result.summary())

    if result.videos:
        print("\n--- 视频结果 ---")
        for v in result.videos[:3]:
            print(v.summary())
            print()

    if result.users:
        print("\n--- 用户结果 ---")
        for u in result.users[:3]:
            print(u.summary())
            print()

    # python -m blux.search
