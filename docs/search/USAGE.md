# blux 搜索模块使用指南

本文档介绍如何使用 `blux` 的搜索模块获取 Bilibili 搜索结果。

---

## 目录

- [安装](#安装)
- [快速开始](#快速开始)
- [WBI 签名器](#wbi-签名器)
- [综合搜索](#综合搜索)
- [分类搜索](#分类搜索)
  - [搜索视频](#搜索视频)
  - [搜索番剧](#搜索番剧)
  - [搜索影视](#搜索影视)
  - [搜索用户](#搜索用户)
  - [搜索专栏](#搜索专栏)
- [数据类说明](#数据类说明)
- [枚举类型](#枚举类型)
- [进阶用法](#进阶用法)
  - [带登录态搜索](#带登录态搜索)
  - [分页遍历](#分页遍历)
  - [筛选和排序](#筛选和排序)
  - [访问原始数据](#访问原始数据)
- [工具函数](#工具函数)

---

## 安装

```bash
pip install -e .
# 或
pip install blux
```

依赖：`requests`, `tclogger`

---

## 快速开始

```python
from blux.search import BiliSearcher

searcher = BiliSearcher()

# 综合搜索
result = searcher.search_all("猫和老鼠")
print(result.summary())

# 输出:
# 搜索结果 (code=0, num_results=1000, pages=50)
#   各类数量: {'video': 1000, 'bili_user': 1000, 'media_bangumi': 18, 'media_ft': 2, ...}
#   本次返回: {'视频': 20, '用户': 1, '番剧': 3, '影视': 1}

# 遍历视频结果
for video in result.videos[:3]:
    print(video.title, f"播放:{video.play}")
```

---

## WBI 签名器

`WbiSigner` 负责对请求参数进行 WBI 签名，通常由 `BiliSearcher` 自动调用，也可独立使用：

```python
from blux.wbi import WbiSigner

signer = WbiSigner()

# 获取 WBI 密钥（首次调用时自动获取）
img_key, sub_key = signer.fetch_wbi_keys()
print(f"img_key: {img_key}")
print(f"sub_key: {sub_key}")

# 对参数进行签名
params = {"keyword": "test", "page": 1}
signed_params = signer.sign(params)
print(signed_params)
# {'keyword': 'test', 'page': '1', 'wts': '1739750400', 'w_rid': 'a67c...'}
```

`DmImgParams` 用于生成反爬参数：

```python
from blux.wbi import DmImgParams

dm = DmImgParams()
params = dm.get()
# {'dm_img_list': [], 'dm_img_str': 'XXcXXXVXXX', 'dm_cover_img_str': 'XXcXXXVXXX', 'dm_img_inter': {...}}
```

---

## 综合搜索

`search_all()` 使用 Bilibili 综合搜索接口，返回多种类型的结果：

```python
from blux.search import BiliSearcher

searcher = BiliSearcher()
result = searcher.search_all("红警08")

# 检查是否成功
assert result.ok  # code == 0

# 基本信息
print(f"总结果数: {result.num_results}")
print(f"总页数: {result.num_pages}")

# 各类型结果数目（从 API 返回的统计）
print(result.top_tlist)
# {'video': 1000, 'bili_user': 45, 'live_room': 8, 'article': 1000, ...}

# 获取各类型的结果列表
print(f"视频: {len(result.videos)} 条")
print(f"用户: {len(result.users)} 条")
print(f"番剧: {len(result.media_bangumi)} 条")
print(f"影视: {len(result.media_ft)} 条")
print(f"直播间: {len(result.live_rooms)} 条")
print(f"主播: {len(result.live_users)} 条")
print(f"专栏: {len(result.articles)} 条")
print(f"话题: {len(result.topics)} 条")
print(f"相簿: {len(result.photos)} 条")
```

### SearchAllResult 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| ok | bool | 是否成功 |
| code | int | 返回码 |
| message | str | 错误信息 |
| num_results | int | 总结果数 |
| num_pages | int | 总页数 |
| top_tlist | dict | 各类结果数目 |
| pageinfo | dict[str, PageInfo] | 各类分页信息 |
| videos | list[VideoItem] | 视频结果 |
| media_bangumi | list[MediaItem] | 番剧结果 |
| media_ft | list[MediaItem] | 影视结果 |
| users | list[UserItem] | 用户结果 |
| live_rooms | list[LiveRoomItem] | 直播间结果 |
| live_users | list[LiveUserItem] | 主播结果 |
| articles | list[ArticleItem] | 专栏结果 |
| topics | list[TopicItem] | 话题结果 |
| photos | list[PhotoItem] | 相簿结果 |
| raw | dict | 原始 JSON 数据 |

---

## 分类搜索

### 搜索视频

```python
from blux.search import BiliSearcher, SearchOrder, VideoDuration

searcher = BiliSearcher()

# 基本视频搜索
result = searcher.search_videos("红警08")
for video in result.items[:5]:
    print(f"[{video.bvid}] {video.title}")
    print(f"  播放: {video.play}  弹幕: {video.video_review}  收藏: {video.favorites}")
    print(f"  UP: {video.author}  分区: {video.typename}")
    print()

# 按最新发布排序
result = searcher.search_videos("红警08", order=SearchOrder.PUBDATE)

# 按最多播放排序
result = searcher.search_videos("红警08", order=SearchOrder.CLICK)

# 筛选时长（10-30分钟）
result = searcher.search_videos("红警08", duration=VideoDuration.TEN_TO_30MIN)

# 指定分区
result = searcher.search_videos("红警08", tids=236)  # 单机游戏分区

# 翻页
result_page2 = searcher.search_videos("红警08", page=2)
```

### 搜索番剧

```python
result = searcher.search_media_bangumi("猫和老鼠")
for media in result.items:
    print(f"[{media.season_type_name}] {media.title}")
    print(f"  地区: {media.areas}  风格: {media.styles}")
    if media.score:
        print(f"  评分: {media.score} ({media.score_count}人)")
    print(f"  集数: {media.ep_size}")
    print()
```

### 搜索影视

```python
result = searcher.search_media_ft("教父")
for media in result.items:
    print(f"[{media.media_type_name}] {media.title}")
    print(f"  ssid={media.season_id}")
    if media.score:
        print(f"  评分: {media.score} ({media.score_count}人)")
```

### 搜索用户

```python
from blux.search import SearchOrder, UserType

result = searcher.search_users("红警08")
for user in result.items:
    print(f"[{user.uname}] mid={user.mid}")
    print(f"  粉丝: {user.fans}  投稿: {user.videos}  等级: {user.level}")
    if user.verify_desc:
        print(f"  认证: {user.verify_desc}")

# 只搜索认证用户，按粉丝数排序
result = searcher.search_users(
    "红警08",
    order=SearchOrder.FANS,
    user_type=UserType.VERIFIED
)
```

### 搜索专栏

```python
result = searcher.search_articles("教父")
for article in result.items:
    print(f"[cv{article.id}] {article.title}")
    print(f"  阅读: {article.view}  点赞: {article.like}  评论: {article.reply}")
```

### 通用分类搜索

使用 `search_by_type()` 可搜索任意类型：

```python
from blux.search import SearchType

# 搜索直播间
result = searcher.search_by_type("猫和老鼠", search_type=SearchType.LIVE_ROOM)

# 搜索话题
result = searcher.search_by_type("猫和老鼠", search_type=SearchType.TOPIC)

# 搜索相簿
result = searcher.search_by_type("猫和老鼠", search_type=SearchType.PHOTO)
```

### SearchTypeResult 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| ok | bool | 是否成功 |
| code | int | 返回码 |
| message | str | 错误信息 |
| search_type | str | 搜索类型 |
| page | int | 当前页码 |
| num_results | int | 总结果数 |
| num_pages | int | 总页数 |
| items | list | 结果列表（类型取决于 search_type） |
| raw | dict | 原始 JSON 数据 |

---

## 数据类说明

所有数据类都提供：
- `from_dict(data)` 类方法：从原始字典解析
- `summary()` 方法：生成可读的摘要文本

### VideoItem 主要字段

```python
video = result.videos[0]
video.aid        # int: avid
video.bvid       # str: bvid
video.title      # str: 标题（已去除 HTML 标签）
video.title_raw  # str: 原始标题（含 <em> 标签）
video.author     # str: UP 主昵称
video.mid        # int: UP 主 mid
video.typename   # str: 分区名
video.play       # int: 播放量
video.video_review  # int: 弹幕数
video.favorites  # int: 收藏数
video.review     # int: 评论数
video.tag        # str: TAG（逗号分隔）
video.pubdate    # int: 时间戳
video.duration   # str: 时长
video.pic        # str: 封面 URL
video.hit_columns  # list[str]: 匹配类型列表
```

### MediaItem 主要字段

```python
media = result.media_ft[0]
media.title          # str: 标题
media.season_id      # int: ssid
media.media_type     # int: 类型编号
media.media_type_name  # str: "番剧"/"电影"/"纪录片"/...
media.areas          # str: 地区
media.styles         # str: 风格
media.score          # float | None: 评分
media.score_count    # int: 评分人数
media.ep_size        # int: 集数
media.eps            # list[dict]: 分集信息
```

### UserItem 主要字段

```python
user = result.users[0]
user.mid          # int: 用户 mid
user.uname        # str: 昵称
user.fans         # int: 粉丝数
user.videos       # int: 投稿数
user.level        # int: 等级
user.gender_str   # str: "男"/"女"/"私密"
user.verify_desc  # str: 认证说明
user.res          # list[dict]: 近期投稿
```

---

## 枚举类型

### SearchType

```python
from blux.search import SearchType

SearchType.VIDEO          # "video"
SearchType.MEDIA_BANGUMI  # "media_bangumi"
SearchType.MEDIA_FT       # "media_ft"
SearchType.LIVE           # "live"
SearchType.LIVE_ROOM      # "live_room"
SearchType.LIVE_USER      # "live_user"
SearchType.ARTICLE        # "article"
SearchType.TOPIC          # "topic"
SearchType.BILI_USER      # "bili_user"
SearchType.PHOTO          # "photo"
```

### SearchOrder

```python
from blux.search import SearchOrder

# 视频/专栏/相簿
SearchOrder.TOTALRANK  # "totalrank" 综合排序
SearchOrder.CLICK      # "click"     最多点击
SearchOrder.PUBDATE    # "pubdate"   最新发布
SearchOrder.DM         # "dm"        最多弹幕
SearchOrder.STOW       # "stow"      最多收藏
SearchOrder.SCORES     # "scores"    最多评论

# 用户
SearchOrder.FANS       # "fans"      粉丝数
SearchOrder.LEVEL      # "level"     等级
```

### VideoDuration

```python
from blux.search import VideoDuration

VideoDuration.ALL            # 0  全部
VideoDuration.UNDER_10MIN    # 1  <10分钟
VideoDuration.TEN_TO_30MIN   # 2  10-30分钟
VideoDuration.THIRTY_TO_60MIN  # 3  30-60分钟
VideoDuration.OVER_60MIN     # 4  >60分钟
```

### UserType

```python
from blux.search import UserType

UserType.ALL       # 0  全部
UserType.UP        # 1  UP主
UserType.NORMAL    # 2  普通用户
UserType.VERIFIED  # 3  认证用户
```

---

## 进阶用法

### 带登录态搜索

传入 `SESSDATA` Cookie 可获取个性化结果（如是否追番等信息）：

```python
searcher = BiliSearcher(sessdata="your_sessdata_here")
result = searcher.search_all("猫和老鼠")
```

### 分页遍历

```python
import time

keyword = "教父"
all_videos = []

for page in range(1, 6):  # 遍历前5页
    result = searcher.search_videos(keyword, page=page)
    if not result.ok or not result.items:
        break
    all_videos.extend(result.items)
    print(f"第 {page} 页: {len(result.items)} 条")
    time.sleep(0.5)  # 注意请求间隔，避免被拦截

print(f"共获取 {len(all_videos)} 条视频")
```

### 筛选和排序

```python
# 搜索30-60分钟的长视频，按收藏数排序
result = searcher.search_videos(
    "教父",
    order=SearchOrder.STOW,
    duration=VideoDuration.THIRTY_TO_60MIN,
    page=1,
)

# 只搜索认证UP主，按粉丝数降序
result = searcher.search_users(
    "红警",
    order=SearchOrder.FANS,
    order_sort=0,  # 0=降序
    user_type=UserType.VERIFIED,
)
```

### 访问原始数据

所有结果对象都保留了原始 JSON 数据：

```python
result = searcher.search_all("猫和老鼠")

# 原始完整响应
print(result.raw)

# 原始 cost_time
print(result.cost_time)

# 原始 pageinfo
print(result.raw["data"]["pageinfo"])
```

---

## 工具函数

### strip_html_tags

去除搜索结果中的 HTML 标签：

```python
from blux.search import strip_html_tags

raw_title = '<em class="keyword">猫和老鼠</em>大电影'
clean = strip_html_tags(raw_title)
print(clean)  # "猫和老鼠大电影"
```

### safe_int

安全转换为 int：

```python
from blux.search import safe_int

safe_int("12345")   # 12345
safe_int(None)      # 0
safe_int("abc", -1) # -1
```
