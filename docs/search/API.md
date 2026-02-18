# Bilibili 搜索 API 文档

本文档记录 Bilibili Web 端搜索相关 API 的接口说明、参数和返回值。

> **注意**：B 站于 2022 年 8 月 24 日更新了搜索 API，增加了 Cookie 校验。如果 Cookie 不足会返回 `-412` 搜索被拦截。调用前需先 GET `https://www.bilibili.com` 获取必要的 Cookie（如 `buvid3`）。

---

## 目录

- [WBI 签名](#wbi-签名)
- [综合搜索](#综合搜索)
- [分类搜索](#分类搜索)
- [搜索结果类型](#搜索结果类型)
  - [视频 (video)](#视频-video)
  - [番剧/影视 (media_bangumi / media_ft)](#番剧影视-media_bangumi--media_ft)
  - [直播间 (live_room)](#直播间-live_room)
  - [主播 (live_user)](#主播-live_user)
  - [专栏 (article)](#专栏-article)
  - [话题 (topic)](#话题-topic)
  - [用户 (bili_user)](#用户-bili_user)
  - [相簿 (photo)](#相簿-photo)
- [错误码](#错误码)

---

## WBI 签名

Bilibili Web 端大部分接口需要 WBI 签名鉴权。签名流程如下：

### 1. 获取签名密钥

**接口：** `GET https://api.bilibili.com/x/web-interface/nav`

从返回数据的 `data.wbi_img` 中提取 `img_url` 和 `sub_url`，取 URL 路径最后一段文件名（去掉扩展名）分别作为 `img_key` 和 `sub_key`。

**返回示例：**
```json
{
  "data": {
    "wbi_img": {
      "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
      "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"
    }
  }
}
```

提取结果：
- `img_key` = `7cd084941338484aae1ad9425b84077c`
- `sub_key` = `4932caff0ff746eab6f01bf08b70ac45`

### 2. 生成 magic_key

将 `img_key + sub_key` 拼接成 64 字符的字符串，按以下混淆表重排后取前 32 位：

```python
MAGIC_KEYS = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52
]
```

### 3. 签名

1. 在参数中添加 `wts=当前时间戳`
2. 按 key 字典序排序
3. 将 dict 类型的值转为紧凑 JSON，其他值转为字符串
4. URL 编码成 query string
5. 计算 `MD5(query_string + magic_key)` 得到 `w_rid`
6. 将 `w_rid` 附加到参数中

---

## 综合搜索

**接口：** `GET https://api.bilibili.com/x/web-interface/wbi/search/all/v2`

**鉴权：** WBI 签名 + Cookie 中含 `buvid3`

返回和关键字相关的信息，包括视频、用户、番剧、影视等多种类型的结果。

### 请求参数

| 参数名 | 类型 | 必要性 | 说明 |
|--------|------|--------|------|
| keyword | str | 必要 | 搜索关键词 |
| wts | int | 必要 | 当前时间戳（WBI 签名自动添加） |
| w_rid | str | 必要 | WBI 签名（自动生成） |

### 返回结构

**根对象：**

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | 返回码，0=成功，-400=请求错误，-412=被拦截 |
| message | str | 错误信息 |
| data | obj | 数据本体 |

**`data` 对象：**

| 字段 | 类型 | 说明 |
|------|------|------|
| seid | str | 搜索 ID |
| page | int | 页数（固定为 1） |
| pagesize | int | 每页条数（固定为 20） |
| numResults | int | 总条数（最大 1000） |
| numPages | int | 分页数（最大 50） |
| suggest_keyword | str | 建议关键词 |
| cost_time | obj | 搜索耗时详情 |
| top_tlist | obj | 各分类结果数目 |
| pageinfo | obj | 各分类分页信息 |
| show_module_list | array | 返回的结果类型列表 |
| result | array | 结果列表（按类型分组） |

**`top_tlist` 对象（各类结果数目）：**

| 字段 | 说明 |
|------|------|
| video | 视频数 |
| media_bangumi | 番剧数 |
| media_ft | 影视数 |
| bili_user | 用户数 |
| live_room | 直播间数 |
| live_user | 主播数 |
| article | 专栏数 |
| topic | 话题数 |
| photo | 相簿数 |

**`result` 数组（按类型分组）：**

每个元素包含：
| 字段 | 类型 | 说明 |
|------|------|------|
| result_type | str | 结果类型标识 |
| data | array | 该类型的搜索结果列表 |

### 真实返回示例

搜索关键词 `红警08`：

```json
{
    "code": 0,
    "message": "0",
    "ttl": 1,
    "data": {
        "seid": "488316204994737268",
        "page": 1,
        "pagesize": 20,
        "numResults": 1000,
        "numPages": 50,
        "top_tlist": {
            "video": 1000,
            "bili_user": 45,
            "live_room": 8,
            "article": 1000,
            "media_bangumi": 0,
            "media_ft": 0
        },
        "result": [
            {
                "result_type": "bili_user",
                "data": [
                    {
                        "type": "bili_user",
                        "mid": 1629347259,
                        "uname": "红警HBK08",
                        "fans": 2200872,
                        "videos": 3623,
                        "level": 6,
                        "official_verify": {
                            "type": 0,
                            "desc": "bilibili 2022百大UP主、知名游戏UP主"
                        }
                    }
                ]
            },
            {
                "result_type": "video",
                "data": [
                    {
                        "type": "video",
                        "aid": 113950849938652,
                        "bvid": "BV1YXZPB1Erc",
                        "title": "<em class=\"keyword\">红警</em><em class=\"keyword\">08</em>祝大家过大年发大财！给大家拜年，万事如意！",
                        "author": "红警HBK08",
                        "mid": 1629347259,
                        "typename": "单机游戏",
                        "play": 176032,
                        "video_review": 3694,
                        "favorites": 1017,
                        "review": 412,
                        "pubdate": 1739750400,
                        "duration": "8:43",
                        "tag": "红色警戒,红警,红警08,HBK08,红警HBK08,拜年"
                    }
                ]
            }
        ]
    }
}
```

搜索关键词 `教父`（包含影视结果）：

```json
{
    "result_type": "media_ft",
    "data": [
        {
            "type": "media_ft",
            "media_id": 28234452,
            "season_id": 26428,
            "title": "<em class=\"keyword\">教父</em>3",
            "cover": "//i0.hdslb.com/bfs/bangumi/image/xxx.jpg",
            "media_type": 2,
            "areas": "美国",
            "styles": "剧情/犯罪/小说改",
            "media_score": {
                "user_count": 4738,
                "score": 9.7
            },
            "season_type_name": "电影"
        },
        {
            "type": "media_ft",
            "media_id": 28234451,
            "season_id": 26427,
            "title": "<em class=\"keyword\">教父</em>2",
            "media_type": 2,
            "areas": "美国",
            "media_score": {
                "user_count": 5875,
                "score": 9.8
            },
            "season_type_name": "电影"
        }
    ]
}
```

搜索关键词 `猫和老鼠`（包含用户、番剧、影视结果）：

```json
{
    "top_tlist": {
        "video": 1000,
        "bili_user": 1000,
        "media_bangumi": 18,
        "media_ft": 2,
        "live_room": 9,
        "article": 1000
    }
}
```

---

## 分类搜索

**接口：** `GET https://api.bilibili.com/x/web-interface/wbi/search/type`

**鉴权：** WBI 签名 + Cookie 中含 `buvid3` + Referer 在 `.bilibili.com` 下

根据关键词和指定类型进行搜索，每页返回 20 条结果，支持分页。

### 请求参数

| 参数名 | 类型 | 必要性 | 说明 |
|--------|------|--------|------|
| keyword | str | 必要 | 搜索关键词 |
| search_type | str | 必要 | 搜索目标类型（见下表） |
| page | int | 非必要 | 页码，默认 1 |
| order | str | 非必要 | 排序方式 |
| duration | int | 非必要 | 视频时长筛选（仅视频） |
| tids | int | 非必要 | 视频分区筛选（仅视频） |
| order_sort | int | 非必要 | 排序方向（仅用户），0=降序，1=升序 |
| user_type | int | 非必要 | 用户分类筛选（仅用户） |
| category_id | int | 非必要 | 分区筛选（专栏/相簿） |

### search_type 取值

| 值 | 说明 |
|----|------|
| video | 视频 |
| media_bangumi | 番剧 |
| media_ft | 影视 |
| live | 直播间及主播 |
| live_room | 直播间 |
| live_user | 主播 |
| article | 专栏 |
| topic | 话题 |
| bili_user | 用户 |
| photo | 相簿 |

### order 排序方式

**视频/专栏/相簿：**

| 值 | 说明 |
|----|------|
| totalrank | 综合排序（默认） |
| click | 最多点击 |
| pubdate | 最新发布 |
| dm | 最多弹幕 |
| stow | 最多收藏 |
| scores | 最多评论 |
| attention | 最多喜欢（仅专栏） |

**直播间：**

| 值 | 说明 |
|----|------|
| online | 人气直播（默认） |
| live_time | 最新开播 |

**用户：**

| 值 | 说明 |
|----|------|
| 0 | 默认排序 |
| fans | 粉丝数 |
| level | 用户等级 |

### duration 视频时长筛选

| 值 | 说明 |
|----|------|
| 0 | 全部时长（默认） |
| 1 | 10分钟以下 |
| 2 | 10-30分钟 |
| 3 | 30-60分钟 |
| 4 | 60分钟以上 |

### user_type 用户分类筛选

| 值 | 说明 |
|----|------|
| 0 | 全部用户（默认） |
| 1 | UP主 |
| 2 | 普通用户 |
| 3 | 认证用户 |

### 返回结构

**`data` 对象：**

| 字段 | 类型 | 说明 |
|------|------|------|
| seid | str | 搜索 ID |
| page | int | 当前页码 |
| pagesize | int | 每页条数（固定 20） |
| numResults | int | 总条数（最大 1000） |
| numPages | int | 总页数（最大 50） |
| cost_time | obj | 搜索耗时 |
| result | array/obj | 结果列表（直播搜索为 obj，其他为 array） |

> **注意：** 当 `search_type=live` 时，`result` 为对象，包含 `live_room` 和 `live_user` 两个数组。其他类型时 `result` 为数组。

### 真实返回示例

搜索关键词 `猫和老鼠`，类型 `media_bangumi`：

```json
{
    "code": 0,
    "data": {
        "numResults": 18,
        "numPages": 1,
        "result": [
            {
                "type": "media_bangumi",
                "media_id": 29232116,
                "season_id": 123730,
                "title": "新<em class=\"keyword\">猫和老鼠</em> 第五季 中文配音",
                "areas": "美国",
                "styles": "原创/日常/搞笑/智斗",
                "ep_size": 13,
                "season_type_name": "番剧"
            },
            {
                "type": "media_bangumi",
                "media_id": 29232115,
                "season_id": 123729,
                "title": "新<em class=\"keyword\">猫和老鼠</em> 第五季",
                "areas": "美国",
                "styles": "搞笑/日常/智斗",
                "ep_size": 13
            }
        ]
    }
}
```

搜索关键词 `猫和老鼠`，类型 `media_ft`：

```json
{
    "code": 0,
    "data": {
        "numResults": 2,
        "numPages": 1,
        "result": [
            {
                "type": "media_ft",
                "season_id": 39348,
                "title": "<em class=\"keyword\">猫和老鼠</em>：大电影",
                "areas": "美国",
                "styles": "动画/家庭",
                "media_score": {
                    "user_count": 1798,
                    "score": 9.5
                },
                "season_type_name": "电影"
            },
            {
                "type": "media_ft",
                "season_id": 105348,
                "title": "<em class=\"keyword\">猫和老鼠</em>：星盘奇缘",
                "areas": "中国大陆/美国",
                "media_score": {
                    "user_count": 224,
                    "score": 5.5
                }
            }
        ]
    }
}
```

---

## 搜索结果类型

### 视频 (video)

| 字段 | 类型 | 说明 |
|------|------|------|
| type | str | 固定为 `video`（也可能有 `ketang` 等特殊类型） |
| aid | int | 稿件 avid |
| bvid | str | 稿件 bvid |
| title | str | 视频标题（关键字用 `<em class="keyword">` 标注） |
| description | str | 视频简介 |
| author | str | UP 主昵称 |
| mid | int | UP 主 mid |
| typeid | str | 视频分区 tid |
| typename | str | 视频子分区名 |
| arcurl | str | 视频 URL |
| pic | str | 封面图 URL |
| play | int | 播放量 |
| video_review | int | 弹幕数 |
| favorites | int | 收藏数 |
| tag | str | 视频 TAG（逗号分隔） |
| review | int | 评论数 |
| pubdate | int | 投稿时间（时间戳） |
| senddate | int | 发布时间（时间戳） |
| duration | str | 时长（MM:SS） |
| hit_columns | array | 关键字匹配类型（title/description/author/tag） |
| rank_score | int | 排序量化值 |
| is_union_video | int | 是否合作视频（0/1） |

### 番剧/影视 (media_bangumi / media_ft)

| 字段 | 类型 | 说明 |
|------|------|------|
| type | str | `media_bangumi` 或 `media_ft` |
| media_id | int | 剧集 mdid |
| season_id | int | 剧集 ssid |
| title | str | 标题（含 HTML 标记） |
| org_title | str | 原名 |
| cover | str | 封面 URL |
| media_type | int | 类型：1=番剧, 2=电影, 3=纪录片, 4=国创, 5=电视剧, 7=综艺 |
| areas | str | 地区 |
| styles | str | 风格 |
| cv | str | 声优 |
| staff | str | 制作组 |
| desc | str | 简介 |
| pubtime | int | 开播时间（时间戳） |
| media_score | obj\|null | 评分信息：`{"user_count": int, "score": float}` |
| season_type_name | str | 类型文字 |
| ep_size | int | 匹配分集数 |
| eps | array | 分集信息列表 |
| url | str | 剧集 URL |
| badges | array | 标志信息（会员专享等） |
| hit_columns | array | 匹配类型 |

### 直播间 (live_room)

| 字段 | 类型 | 说明 |
|------|------|------|
| type | str | 固定为 `live_room` |
| roomid | int | 直播间 ID |
| uid | int | 主播 mid |
| title | str | 直播间标题（含 HTML 标记） |
| uname | str | 主播昵称 |
| uface | str | 头像 URL |
| cover | str | 关键帧截图 URL |
| user_cover | str | 封面 URL |
| online | int | 在线人数 |
| attentions | int | 粉丝数 |
| cate_name | str | 分区名 |
| live_time | str | 开播时间 |
| tags | str | TAG |

### 主播 (live_user)

| 字段 | 类型 | 说明 |
|------|------|------|
| type | str | 固定为 `live_user` |
| uid | int | 主播 mid |
| uname | str | 主播昵称（含 HTML 标记） |
| uface | str | 头像 URL |
| is_live | bool | 是否开播 |
| roomid | int | 直播间 ID |
| attentions | int | 粉丝数 |

### 专栏 (article)

| 字段 | 类型 | 说明 |
|------|------|------|
| type | str | 固定为 `article` |
| id | int | 专栏 cvid |
| title | str | 标题 |
| mid | int | UP 主 mid |
| desc | str | 文章预览 |
| image_urls | array | 封面图组 |
| view | int | 阅读数 |
| like | int | 点赞数 |
| reply | int | 评论数 |
| pub_time | int | 投稿时间 |
| category_name | str | 分区名 |

### 话题 (topic)

| 字段 | 类型 | 说明 |
|------|------|------|
| type | str | 固定为 `topic` |
| tp_id | int | 话题 ID |
| title | str | 标题 |
| description | str | 简介 |
| author | str | 作者昵称 |
| cover | str | 封面 URL |
| arcurl | str | 话题页 URL |
| click | int | 点击数 |

### 用户 (bili_user)

| 字段 | 类型 | 说明 |
|------|------|------|
| type | str | 固定为 `bili_user` |
| mid | int | 用户 mid |
| uname | str | 昵称 |
| usign | str | 签名 |
| fans | int | 粉丝数 |
| videos | int | 稿件数 |
| upic | str | 头像 URL |
| level | int | 等级 |
| gender | int | 性别：1=男, 2=女, 3=私密 |
| is_upuser | int | 是否 UP 主 |
| is_live | int | 是否直播中 |
| room_id | int | 直播间 ID |
| official_verify | obj | 认证信息：`{"type": int, "desc": str}` |
| res | array | 近期投稿（最多 3 个） |
| hit_columns | array | 匹配类型 |

### 相簿 (photo)

| 字段 | 类型 | 说明 |
|------|------|------|
| type | str | 固定为 `photo` |
| id | int | 相簿 ID |
| title | str | 标题 |
| cover | str | 封面 URL |
| count | int | 图片数 |
| mid | int | UP 主 mid |
| uname | str | UP 主昵称 |
| view | int | 浏览数 |
| like | int | 收藏数 |

---

## 错误码

| code | 说明 |
|------|------|
| 0 | 成功 |
| -400 | 请求错误（参数有误） |
| -412 | 请求被拦截（Cookie 不足或频率过高） |
| -1200 | 搜索目标类型不存在（被降级过滤的请求） |

### 常见问题

1. **返回 -412**：确保先访问 `https://www.bilibili.com` 获取 Cookie（至少需要 `buvid3`）。频繁请求也可能触发此错误。
2. **标题中包含 HTML 标签**：搜索结果中的标题字段使用 `<em class="keyword">关键词</em>` 标记匹配到的关键字，需用正则去除：`re.sub(r"<[^>]+>", "", text)`
3. **特殊类型**：视频搜索结果中可能混入 `ketang`（课堂）类型的条目，这类条目没有 `bvid`，需要特殊处理。
