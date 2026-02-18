"""搜索模块测试。

使用 `红警08`, `教父`, `猫和老鼠` 三个关键词测试搜索功能。
验证：
  1. WBI 签名流程正常
  2. 综合搜索能返回多种类型结果
  3. 分类搜索（视频、影视）正常工作
  4. 各类数据结构正确解析
  5. HTML 标签正确去除
"""

import sys
import time

from tclogger import logger, logstr, Runtimer

from blux.wbi import WbiSigner
from blux.search import (
    BiliSearcher,
    SearchType,
    SearchOrder,
    VideoDuration,
    SearchAllResult,
    SearchTypeResult,
    VideoItem,
    MediaItem,
    UserItem,
    strip_html_tags,
)

KEYWORDS = ["红警08", "教父", "猫和老鼠"]


def test_wbi_signer():
    """测试 WBI 签名器。"""
    logger.note("=" * 60)
    logger.note("测试 WBI 签名器")
    logger.note("=" * 60)

    signer = WbiSigner()
    img_key, sub_key = signer.fetch_wbi_keys()

    assert img_key, "img_key 不应为空"
    assert sub_key, "sub_key 不应为空"
    logger.success(f"  img_key: {logstr.mesg(img_key)}")
    logger.success(f"  sub_key: {logstr.mesg(sub_key)}")

    # 测试签名
    params = {"keyword": "test", "page": 1}
    signed = signer.sign(params)
    assert "w_rid" in signed, "签名结果应包含 w_rid"
    assert "wts" in signed, "签名结果应包含 wts"
    logger.success(f"  w_rid: {logstr.mesg(signed['w_rid'])}")
    logger.success(f"  wts: {logstr.mesg(signed['wts'])}")

    # 测试固定 wts 的签名可复现
    signed1 = signer.sign(params, wts=1234567890)
    signed2 = signer.sign(params, wts=1234567890)
    assert signed1["w_rid"] == signed2["w_rid"], "相同参数和 wts 应产生相同签名"
    logger.success("  签名可复现性验证通过")

    logger.success("WBI 签名器测试通过 ✓\n")


def test_strip_html_tags():
    """测试 HTML 标签去除。"""
    logger.note("测试 HTML 标签去除")

    cases = [
        (
            '【<em class="keyword">红警</em>08】测试',
            "【红警08】测试",
        ),
        (
            '<em class="keyword">教父</em> The Godfather',
            "教父 The Godfather",
        ),
        ("纯文本无标签", "纯文本无标签"),
        ("", ""),
        (None, None),
    ]
    for raw, expected in cases:
        result = strip_html_tags(raw)
        assert result == expected, f"strip_html_tags({raw!r}) = {result!r}, expected {expected!r}"

    logger.success("HTML 标签去除测试通过 ✓\n")


def test_search_all(searcher: BiliSearcher, keyword: str):
    """测试综合搜索。"""
    logger.note("-" * 60)
    logger.note(f"综合搜索: {logstr.mesg(keyword)}")
    logger.note("-" * 60)

    result = searcher.search_all(keyword)

    assert result.ok, f"搜索应返回 code=0, got code={result.code}, msg={result.message}"
    assert result.num_results > 0, "搜索结果数应大于 0"

    print(result.summary())

    # 验证视频结果
    if result.videos:
        logger.note(f"\n  视频结果 ({len(result.videos)} 条):")
        for v in result.videos[:3]:
            assert isinstance(v, VideoItem), f"应为 VideoItem, got {type(v)}"
            assert v.bvid, "视频应有 bvid"
            assert v.title, "视频应有标题"
            assert "<em" not in v.title, f"标题不应包含 HTML 标签: {v.title}"
            logger.mesg(f"    {v.summary()}")
    else:
        logger.warn("  无视频结果")

    # 验证用户结果
    if result.users:
        logger.note(f"\n  用户结果 ({len(result.users)} 条):")
        for u in result.users[:2]:
            assert isinstance(u, UserItem), f"应为 UserItem, got {type(u)}"
            assert u.mid > 0, "用户应有 mid"
            logger.mesg(f"    {u.summary()}")

    # 验证番剧/影视结果
    for label, items in [("番剧", result.media_bangumi), ("影视", result.media_ft)]:
        if items:
            logger.note(f"\n  {label}结果 ({len(items)} 条):")
            for m in items[:2]:
                assert isinstance(m, MediaItem), f"应为 MediaItem, got {type(m)}"
                logger.mesg(f"    {m.summary()}")

    logger.success(f"综合搜索 [{keyword}] 验证通过 ✓\n")
    return result


def test_search_videos(searcher: BiliSearcher, keyword: str):
    """测试视频分类搜索。"""
    logger.note("-" * 60)
    logger.note(f"视频搜索: {logstr.mesg(keyword)}")
    logger.note("-" * 60)

    result = searcher.search_videos(keyword, order=SearchOrder.TOTALRANK, page=1)

    assert result.ok, f"搜索应返回 code=0, got code={result.code}, msg={result.message}"

    print(result.summary())

    if result.items:
        logger.note(f"\n  视频结果 ({len(result.items)} 条):")
        for v in result.items[:5]:
            assert isinstance(v, VideoItem), f"应为 VideoItem, got {type(v)}"
            # 部分特殊类型（如 ketang/课堂）可能没有 bvid
            if v.type == "video":
                assert v.bvid, f"视频应有 bvid: {v}"
            assert v.title, f"视频应有标题"
            assert v.play >= 0, f"播放量应非负"
            logger.mesg(f"    {v.summary()}")

    logger.success(f"视频搜索 [{keyword}] 验证通过 ✓\n")
    return result


def test_search_media(searcher: BiliSearcher, keyword: str):
    """测试影视分类搜索。"""
    logger.note("-" * 60)
    logger.note(f"影视搜索: {logstr.mesg(keyword)}")
    logger.note("-" * 60)

    result = searcher.search_media_ft(keyword)

    if result.ok:
        print(result.summary())
        if result.items:
            logger.note(f"\n  影视结果 ({len(result.items)} 条):")
            for m in result.items[:3]:
                assert isinstance(m, MediaItem), f"应为 MediaItem, got {type(m)}"
                logger.mesg(f"    {m.summary()}")
        logger.success(f"影视搜索 [{keyword}] 验证通过 ✓\n")
    else:
        logger.warn(f"影视搜索 [{keyword}] code={result.code}: {result.message}\n")

    return result


def test_search_bangumi(searcher: BiliSearcher, keyword: str):
    """测试番剧分类搜索。"""
    logger.note("-" * 60)
    logger.note(f"番剧搜索: {logstr.mesg(keyword)}")
    logger.note("-" * 60)

    result = searcher.search_media_bangumi(keyword)

    if result.ok:
        print(result.summary())
        if result.items:
            logger.note(f"\n  番剧结果 ({len(result.items)} 条):")
            for m in result.items[:3]:
                assert isinstance(m, MediaItem), f"应为 MediaItem, got {type(m)}"
                logger.mesg(f"    {m.summary()}")
        logger.success(f"番剧搜索 [{keyword}] 验证通过 ✓\n")
    else:
        logger.warn(f"番剧搜索 [{keyword}] code={result.code}: {result.message}\n")

    return result


def main():
    timer = Runtimer()
    timer.start_time()

    test_wbi_signer()
    test_strip_html_tags()

    searcher = BiliSearcher()

    all_results = {}
    video_results = {}

    for kw in KEYWORDS:
        logger.note("=" * 60)
        logger.note(f"关键词: {logstr.file(kw)}")
        logger.note("=" * 60)

        # 综合搜索
        all_results[kw] = test_search_all(searcher, kw)
        time.sleep(0.5)

        # 视频搜索
        video_results[kw] = test_search_videos(searcher, kw)
        time.sleep(0.5)

        # 影视搜索（教父、猫和老鼠 可能有影视结果）
        if kw in ("教父", "猫和老鼠"):
            test_search_media(searcher, kw)
            time.sleep(0.5)
            test_search_bangumi(searcher, kw)
            time.sleep(0.5)

    # 最终汇总
    logger.note("=" * 60)
    logger.note("测试汇总")
    logger.note("=" * 60)

    for kw in KEYWORDS:
        r = all_results[kw]
        vr = video_results[kw]
        logger.success(
            f"  [{kw}] 综合: {r.num_results} 条 (视频={len(r.videos)}, "
            f"用户={len(r.users)}, 番剧={len(r.media_bangumi)}, "
            f"影视={len(r.media_ft)}) | "
            f"视频搜索: {vr.num_results} 条, 本页 {len(vr.items)} 条"
        )

    timer.end_time()
    logger.success("\n所有测试通过 ✓")


if __name__ == "__main__":
    main()

    # python -m blux.test_search
