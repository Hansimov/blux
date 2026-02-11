"""doc_score 模块的全面测试。

覆盖范围：
  - 饱和函数的核心属性
  - 统计评分：权重、边界、单调性
  - 异常检测：通用字段一致性惩罚、各种异常模式
  - 时间因子：锚点、插值、单调性
  - 集成测试：完整文档、排序、边界情况
  - 评分详情一致性检验
"""

import math

from tclogger import logger, chars_len

from blux.doc_score import DocScorer, doc_scorer, calc_doc_score, calc_doc_score_detail

# 从评分器获取内部方法引用（用于单元测试）

_saturate = DocScorer._saturate
_calc_stat_score = doc_scorer._calc_stat_score
_calc_anomaly_factor = doc_scorer._calc_anomaly_factor
_calc_time_factor = doc_scorer._calc_time_factor

# 常用常量引用

STAT_CONFIGS = DocScorer.STAT_CONFIGS
STAT_FIELDS = DocScorer.STAT_FIELDS
TOTAL_WEIGHT = DocScorer.TOTAL_WEIGHT
BASE_SCORE = DocScorer.BASE_SCORE
SECONDS_1H = DocScorer.SECONDS_1H
SECONDS_1D = DocScorer.SECONDS_1D
SECONDS_3D = DocScorer.SECONDS_3D
SECONDS_7D = DocScorer.SECONDS_7D
SECONDS_15D = DocScorer.SECONDS_15D
SECONDS_30D = DocScorer.SECONDS_30D
TIME_ANCHORS = DocScorer.TIME_ANCHORS
TIME_FACTOR_MAX = DocScorer.TIME_FACTOR_MAX
TIME_FACTOR_MIN = DocScorer.TIME_FACTOR_MIN
ANOMALY_MIN_LOG_SCALE = DocScorer.ANOMALY_MIN_LOG_SCALE
ANOMALY_CONSISTENCY_THRESHOLD = DocScorer.ANOMALY_CONSISTENCY_THRESHOLD
ANOMALY_MIN_FACTOR = DocScorer.ANOMALY_MIN_FACTOR

# 测试基础设施

_passed = 0
_failed = 0
_errors = []


def _check(condition: bool, desc: str):
    """记录一条测试结果并输出日志。"""
    global _passed, _failed
    if condition:
        _passed += 1
        logger.okay(f"  ✓ {desc}")
    else:
        _failed += 1
        _errors.append(desc)
        logger.warn(f"  ✗ {desc}")


def _check_approx(actual: float, expected: float, desc: str, tol: float = 0.01):
    """检查近似相等（在容差范围内）。"""
    ok = abs(actual - expected) < tol
    _check(ok, f"{desc}: {actual:.4f} ≈ {expected:.4f}")


def _check_range(value: float, low: float, high: float, desc: str):
    """检查值是否在 [low, high] 范围内。"""
    _check(low <= value <= high, f"{desc}: {value:.4f} ∈ [{low}, {high}]")


# CJK 宽度感知的填充函数


def _ljust(s: str, width: int) -> str:
    """左对齐填充，正确处理中文字符的双倍宽度。"""
    return s + " " * max(0, width - chars_len(s))


def _rjust(s: str, width: int) -> str:
    """右对齐填充，正确处理中文字符的双倍宽度。"""
    return " " * max(0, width - chars_len(s)) + s


# 测试辅助函数


def _make_stats(
    view=0,
    like=0,
    coin=0,
    favorite=0,
    danmaku=0,
    reply=0,
    share=0,
):
    """构造一个 stats 字典。"""
    return {
        "view": view,
        "like": like,
        "coin": coin,
        "favorite": favorite,
        "danmaku": danmaku,
        "reply": reply,
        "share": share,
    }


def _make_doc(stats=None, pub_to_insert=None, pubdate=0, insert_at=None):
    """构造一个最小的文档字典。"""
    doc = {}
    if stats is not None:
        doc["stats"] = stats
    if pub_to_insert is not None:
        doc["pub_to_insert"] = pub_to_insert
    if pubdate:
        doc["pubdate"] = pubdate
    if insert_at is not None:
        doc["insert_at"] = insert_at
    return doc


def _default_stats():
    """一个中等水平的"正常"统计分布。"""
    return _make_stats(
        view=10000, like=500, coin=100, favorite=80, danmaku=200, reply=50
    )


# 1. 测试：_saturate 饱和函数


def test_saturate():
    logger.note("> test_saturate")

    # 零和负数输入
    _check(_saturate(0, 5.0) == 0.0, "f(0) = 0")
    _check(_saturate(-1, 5.0) == 0.0, "f(负数) = 0")
    _check(_saturate(-1e10, 5.0) == 0.0, "f(极大负数) = 0")

    # 正数输入产生正数输出
    _check(_saturate(1, 5.0) > 0, "f(1) > 0")
    _check(_saturate(0.001, 5.0) > 0, "f(0.001) > 0")

    # 单调递增
    values = [1, 10, 100, 1000, 10000, 100000, 1000000]
    scores = [_saturate(v, 5.0) for v in values]
    for i in range(len(scores) - 1):
        _check(
            scores[i] < scores[i + 1],
            f"单调: f({values[i]}) = {scores[i]:.4f} "
            f"< f({values[i+1]}) = {scores[i+1]:.4f}",
        )

    # 严格小于 1.0
    _check(_saturate(1e10, 5.0) < 1.0, "f(1e10) < 1.0")
    _check(_saturate(1e20, 5.0) < 1.0, "f(1e20) < 1.0")
    _check(_saturate(1e100, 3.0) < 1.0, "f(1e100) < 1.0")

    # 半饱和性质：f(e^α − 1) = 0.5
    for alpha in [3.0, 4.5, 5.0, 5.5, 8.0]:
        x_half = math.exp(alpha) - 1
        _check_approx(
            _saturate(x_half, alpha),
            0.5,
            f"半饱和 (α={alpha}, x={x_half:.1f})",
            tol=1e-6,
        )

    # 边际递减
    d1 = _saturate(100, 5.0) - _saturate(0, 5.0)
    d2 = _saturate(200, 5.0) - _saturate(100, 5.0)
    d3 = _saturate(300, 5.0) - _saturate(200, 5.0)
    _check(d2 < d1, f"递减: Δ(0→100)={d1:.4f} > Δ(100→200)={d2:.4f}")
    _check(d3 < d2, f"递减: Δ(100→200)={d2:.4f} > Δ(200→300)={d3:.4f}")

    # 不同 alpha 产生不同曲线
    _check(
        _saturate(100, 3.0) > _saturate(100, 8.0),
        "较小α饱和更快: f(100, α=3) > f(100, α=8)",
    )


# 2. 测试：_calc_stat_score 统计评分


def test_stat_score():
    logger.note("> test_stat_score")

    # 全零 → 0
    _check(_calc_stat_score(_make_stats()) == 0.0, "全零 → 0")

    # 单个字段设值 → 正数且有界
    for field in STAT_FIELDS:
        stats = _make_stats(**{field: 1000})
        score = _calc_stat_score(stats)
        _check(score > 0, f"仅 {field}=1000 → 正数 ({score:.4f})")
        _check(score < 1.0, f"仅 {field}=1000 → 有界 ({score:.4f})")

    # 权重排序（相同值，隔离权重影响）
    val = 1000
    field_scores = {}
    for field in STAT_FIELDS:
        field_scores[field] = _calc_stat_score(_make_stats(**{field: val}))

    # 投币 ≈ 收藏（权重=3.0, alpha=4.5）
    _check_approx(
        field_scores["coin"],
        field_scores["favorite"],
        "投币 ≈ 收藏",
        tol=1e-6,
    )

    # 投币 > 点赞（权重 3 vs 2，加上不同 alpha）
    _check(
        field_scores["coin"] > field_scores["like"],
        f"投币 ({field_scores['coin']:.4f}) > 点赞 ({field_scores['like']:.4f})",
    )

    # 点赞 > 播放（权重 2 vs 1）
    _check(
        field_scores["like"] > field_scores["view"],
        f"点赞 ({field_scores['like']:.4f}) > 播放 ({field_scores['view']:.4f})",
    )

    # 评论 > 播放
    _check(
        field_scores["reply"] > field_scores["view"],
        f"评论 ({field_scores['reply']:.4f}) > 播放 ({field_scores['view']:.4f})",
    )

    # 弹幕 > 播放
    _check(
        field_scores["danmaku"] > field_scores["view"],
        f"弹幕 ({field_scores['danmaku']:.4f}) > 播放 ({field_scores['view']:.4f})",
    )

    # 极端值仍有界
    extreme = _make_stats(
        view=1e9,
        like=1e8,
        coin=1e7,
        favorite=1e7,
        danmaku=1e8,
        reply=1e7,
    )
    s_extreme = _calc_stat_score(extreme)
    _check(s_extreme < 1.0, f"极端值 → 有界 ({s_extreme:.4f})")

    # 单调性：字段值越大 → 分数越高
    for field in STAT_FIELDS:
        s_low = _calc_stat_score(_make_stats(**{field: 100}))
        s_high = _calc_stat_score(_make_stats(**{field: 10000}))
        _check(
            s_high > s_low,
            f"单调: {field}=10000 ({s_high:.4f}) > {field}=100 ({s_low:.4f})",
        )

    # share 字段被忽略
    s_no = _calc_stat_score(_make_stats(view=5000, like=200))
    s_with = _calc_stat_score(_make_stats(view=5000, like=200, share=999999))
    _check(s_no == s_with, "share 字段被忽略")


# 3. 测试：_calc_anomaly_factor 异常检测


def test_anomaly_factor():
    logger.note("> test_anomaly_factor")

    # 全零 → 不做检测（max_log < 阈值）→ factor=1.0
    _check(
        _calc_anomaly_factor(_make_stats()) == 1.0,
        "全零 → factor=1.0",
    )

    # 小数据量 → 不做检测
    _check(
        _calc_anomaly_factor(_make_stats(view=100, like=5, coin=2)) == 1.0,
        "小数据量 → factor=1.0（所有字段对数尺度很小）",
    )

    # 均衡分布 → 无惩罚
    balanced = _make_stats(
        view=50000,
        like=2000,
        coin=500,
        favorite=300,
        danmaku=800,
        reply=200,
    )
    f_balanced = _calc_anomaly_factor(balanced)
    _check(f_balanced == 1.0, f"均衡分布 → factor=1.0 ({f_balanced:.4f})")

    # 高互动均衡分布 → 无惩罚
    high_balanced = _make_stats(
        view=10000000,
        like=500000,
        coin=100000,
        favorite=200000,
        danmaku=300000,
        reply=50000,
    )
    _check(
        _calc_anomaly_factor(high_balanced) == 1.0,
        "高互动均衡分布 → factor=1.0",
    )

    # --- 仅播放量异常高 → 惩罚
    view_only = _make_stats(view=1000000)
    f_view = _calc_anomaly_factor(view_only)
    _check(f_view < 1.0, f"仅播放量高 (100万) → 惩罚 ({f_view:.4f})")
    _check(
        f_view >= ANOMALY_MIN_FACTOR,
        f"惩罚不低于下限: {f_view:.4f} >= {ANOMALY_MIN_FACTOR}",
    )

    # --- 仅投币异常高 → 惩罚
    coin_only = _make_stats(coin=100000)
    f_coin = _calc_anomaly_factor(coin_only)
    _check(f_coin < 1.0, f"仅投币高 (10万) → 惩罚 ({f_coin:.4f})")

    # --- 仅点赞异常高 → 惩罚
    like_only = _make_stats(like=500000)
    f_like = _calc_anomaly_factor(like_only)
    _check(f_like < 1.0, f"仅点赞高 (50万) → 惩罚 ({f_like:.4f})")

    # --- 仅收藏异常高 → 惩罚
    fav_only = _make_stats(favorite=100000)
    f_fav = _calc_anomaly_factor(fav_only)
    _check(f_fav < 1.0, f"仅收藏高 (10万) → 惩罚 ({f_fav:.4f})")

    # --- 仅弹幕异常高 → 惩罚
    danmaku_only = _make_stats(danmaku=500000)
    f_danmaku = _calc_anomaly_factor(danmaku_only)
    _check(f_danmaku < 1.0, f"仅弹幕高 (50万) → 惩罚 ({f_danmaku:.4f})")

    # --- 两个字段异常高，其余低 → 惩罚
    two_high = _make_stats(view=1000000, like=500000)
    f_two = _calc_anomaly_factor(two_high)
    _check(f_two < 1.0, f"播放+点赞高，其余为零 → 惩罚 ({f_two:.4f})")

    # 两个字段异常比一个字段异常的惩罚更轻
    _check(
        f_two > f_view,
        f"两字段异常 ({f_two:.4f}) > 单字段异常 ({f_view:.4f})",
    )

    # --- 播放量高 + 少量互动 → 有惩罚但比零互动轻
    low_eng = _make_stats(
        view=1000000,
        like=100,
        coin=10,
        favorite=5,
        danmaku=50,
        reply=10,
    )
    f_low = _calc_anomaly_factor(low_eng)
    _check(f_low < 1.0, f"高播放低互动 → 惩罚 ({f_low:.4f})")
    _check(
        f_low > f_view,
        f"有少量互动 ({f_low:.4f}) > 零互动 ({f_view:.4f})",
    )

    # --- 因子在 [ANOMALY_MIN_FACTOR, 1.0] 范围内
    extreme_cases = [
        _make_stats(view=10000000),
        _make_stats(coin=1000000),
        _make_stats(view=5000000, like=10, coin=0),
        _make_stats(like=1000000, reply=1),
    ]
    for i, s in enumerate(extreme_cases):
        f = _calc_anomaly_factor(s)
        _check(
            ANOMALY_MIN_FACTOR <= f <= 1.0,
            f"极端案例#{i+1}: factor={f:.4f} ∈ [{ANOMALY_MIN_FACTOR}, 1.0]",
        )

    # --- 单调性：分布越均衡 → 因子越高
    # 从全部不均到逐步添加互动
    factors_mono = []
    engagements = [
        _make_stats(view=100000),
        _make_stats(view=100000, like=1000),
        _make_stats(view=100000, like=1000, coin=200),
        _make_stats(view=100000, like=1000, coin=200, favorite=150),
        _make_stats(view=100000, like=1000, coin=200, favorite=150, danmaku=500),
        _make_stats(
            view=100000, like=1000, coin=200, favorite=150, danmaku=500, reply=100
        ),
    ]
    for s in engagements:
        factors_mono.append(_calc_anomaly_factor(s))
    for i in range(len(factors_mono) - 1):
        _check(
            factors_mono[i] <= factors_mono[i + 1],
            f"均衡性单调: 添加第{i+2}个字段 → "
            f"{factors_mono[i]:.4f} ≤ {factors_mono[i+1]:.4f}",
        )


# 4. 测试：_calc_time_factor 时间因子


def test_time_factor():
    logger.note("> test_time_factor")

    # 边界值截断
    _check_approx(_calc_time_factor(0), TIME_FACTOR_MAX, "t=0 → 最大值")
    _check_approx(_calc_time_factor(100), TIME_FACTOR_MAX, "t=100秒 → 最大值")
    _check_approx(_calc_time_factor(SECONDS_1H), TIME_FACTOR_MAX, "t=1小时 → 最大值")
    _check_approx(_calc_time_factor(SECONDS_30D), TIME_FACTOR_MIN, "t=30天 → 最小值")
    _check_approx(
        _calc_time_factor(SECONDS_30D * 5), TIME_FACTOR_MIN, "t=150天 → 最小值"
    )
    _check_approx(_calc_time_factor(10**9), TIME_FACTOR_MIN, "t=1e9 → 最小值")

    # 精确锚点
    for t_anchor, expected in TIME_ANCHORS:
        actual = _calc_time_factor(t_anchor)
        _check_approx(actual, expected, f"锚点 t={t_anchor}秒", tol=1e-6)

    # 单调递减
    times = [
        0,
        1800,
        SECONDS_1H,
        43200,
        SECONDS_1D,
        172800,
        SECONDS_3D,
        432000,
        SECONDS_7D,
        950400,
        SECONDS_15D,
        1944000,
        SECONDS_30D,
        SECONDS_30D * 2,
    ]
    factors = [_calc_time_factor(t) for t in times]
    for i in range(len(factors) - 1):
        _check(
            factors[i] >= factors[i + 1],
            f"单调: t={times[i]}({factors[i]:.4f}) "
            f"≥ t={times[i+1]}({factors[i+1]:.4f})",
        )

    # 锚点间插值在邻居之间
    mid_1d_3d = (SECONDS_1D + SECONDS_3D) // 2
    f_mid = _calc_time_factor(mid_1d_3d)
    _check(
        0.90 < f_mid < 1.10,
        f"1天–3天之间: {f_mid:.4f} ∈ (0.90, 1.10)",
    )

    mid_7d_15d = (SECONDS_7D + SECONDS_15D) // 2
    f_mid2 = _calc_time_factor(mid_7d_15d)
    _check(
        0.55 < f_mid2 < 0.70,
        f"7天–15天之间: {f_mid2:.4f} ∈ (0.55, 0.70)",
    )

    # 负数输入 → 截断到最大值
    _check_approx(_calc_time_factor(-1000), TIME_FACTOR_MAX, "负数 → 最大值")
    _check_approx(_calc_time_factor(-(10**9)), TIME_FACTOR_MAX, "极大负数 → 最大值")

    # 不同时间段有不同衰减速率
    drop_1h_1d = _calc_time_factor(SECONDS_1H) - _calc_time_factor(SECONDS_1D)
    drop_15d_30d = _calc_time_factor(SECONDS_15D) - _calc_time_factor(SECONDS_30D)
    _check(
        drop_1h_1d > drop_15d_30d,
        f"早期衰减更快: Δ(1h→1d)={drop_1h_1d:.3f} > Δ(15d→30d)={drop_15d_30d:.3f}",
    )


# 5. 测试：calc_doc_score 集成测试


def test_score_integration():
    logger.note("> test_score_integration")

    # 空文档 → 仍为正
    s_empty = calc_doc_score({})
    _check(s_empty > 0, f"空文档 → 正数 ({s_empty:.6f})")

    # 典型热门视频，发布 1 天
    popular_1d = _make_doc(
        stats=_make_stats(
            view=50000,
            like=2000,
            coin=500,
            favorite=300,
            danmaku=800,
            reply=200,
        ),
        pub_to_insert=SECONDS_1D,
    )
    s_popular = calc_doc_score(popular_1d)
    _check(s_popular > 0.3, f"热门 1天: {s_popular:.4f} > 0.3")
    _check(s_popular < 1.0, f"热门 1天: {s_popular:.4f} < 1.0")

    # 一般视频，发布 1 周
    mediocre_7d = _make_doc(
        stats=_make_stats(
            view=500,
            like=20,
            coin=5,
            favorite=3,
            danmaku=10,
            reply=5,
        ),
        pub_to_insert=SECONDS_7D,
    )
    s_mediocre = calc_doc_score(mediocre_7d)
    _check(
        0 < s_mediocre < s_popular,
        f"一般 7天 ({s_mediocre:.4f}) < 热门 1天 ({s_popular:.4f})",
    )

    # 异常：高播放量，近零互动，新鲜
    anomalous = _make_doc(
        stats=_make_stats(
            view=1000000,
            like=10,
            coin=0,
            favorite=2,
            danmaku=5,
            reply=1,
        ),
        pub_to_insert=SECONDS_1H,
    )
    s_anom = calc_doc_score(anomalous)
    _check(
        s_anom < s_popular,
        f"播放异常 ({s_anom:.4f}) < 热门 1天 ({s_popular:.4f})",
    )

    # 异常：高投币，其余低，新鲜
    anomalous_coin = _make_doc(
        stats=_make_stats(
            view=200,
            like=10,
            coin=100000,
            favorite=5,
            danmaku=3,
            reply=1,
        ),
        pub_to_insert=SECONDS_1H,
    )
    s_anom_coin = calc_doc_score(anomalous_coin)
    _check(
        s_anom_coin < s_popular,
        f"投币异常 ({s_anom_coin:.4f}) < 热门 1天 ({s_popular:.4f})",
    )

    # 病毒式传播视频，新鲜
    viral_fresh = _make_doc(
        stats=_make_stats(
            view=10000000,
            like=500000,
            coin=100000,
            favorite=200000,
            danmaku=300000,
            reply=50000,
        ),
        pub_to_insert=SECONDS_1H,
    )
    s_viral = calc_doc_score(viral_fresh)
    _check(
        s_viral > s_popular,
        f"病毒式新鲜 ({s_viral:.4f}) > 热门 1天 ({s_popular:.4f})",
    )
    _check(s_viral < 2.0, f"病毒式新鲜 ({s_viral:.4f}) 有界 < 2.0")

    # 同样病毒式视频，很旧
    viral_old = _make_doc(
        stats=_make_stats(
            view=10000000,
            like=500000,
            coin=100000,
            favorite=200000,
            danmaku=300000,
            reply=50000,
        ),
        pub_to_insert=SECONDS_30D * 2,
    )
    s_viral_old = calc_doc_score(viral_old)
    _check(
        s_viral_old < s_viral,
        f"病毒式旧 ({s_viral_old:.4f}) < 病毒式新鲜 ({s_viral:.4f})",
    )

    # pub_to_insert 回退（使用 insert_at - pubdate 计算）
    stats = _make_stats(
        view=10000,
        like=500,
        coin=100,
        favorite=50,
        danmaku=200,
        reply=50,
    )
    explicit = calc_doc_score(_make_doc(stats=stats, pub_to_insert=SECONDS_1D))
    fallback = calc_doc_score(
        _make_doc(stats=stats, pubdate=1000000, insert_at=1000000 + SECONDS_1D),
    )
    _check_approx(fallback, explicit, "pub_to_insert 回退", tol=1e-10)

    # 分数恒为正的各种组合
    combos = [
        ({}, 0),
        ({}, SECONDS_30D * 10),
        (_make_stats(), SECONDS_1H),
        (_make_stats(view=1), SECONDS_30D),
        (_make_stats(coin=1), 0),
    ]
    for i, (st, t) in enumerate(combos):
        s = calc_doc_score(_make_doc(stats=st, pub_to_insert=t))
        _check(s > 0, f"恒为正组合 #{i+1}: {s:.6f}")


# 6. 测试：分数排序


def test_score_ordering():
    logger.note("> test_score_ordering")

    base = _default_stats()

    # 新鲜度排序：相同质量，时间递增
    time_points = [
        SECONDS_1H,
        SECONDS_1D,
        SECONDS_3D,
        SECONDS_7D,
        SECONDS_15D,
        SECONDS_30D,
    ]
    scores_t = [
        (t, calc_doc_score(_make_doc(stats=base, pub_to_insert=t))) for t in time_points
    ]
    for i in range(len(scores_t) - 1):
        t1, s1 = scores_t[i]
        t2, s2 = scores_t[i + 1]
        _check(
            s1 > s2,
            f"新鲜度: t={t1}({s1:.4f}) > t={t2}({s2:.4f})",
        )

    # 质量排序：相同时间，质量递增
    quality_tiers = [
        ("极低", _make_stats(view=100, like=5, coin=1, favorite=0, danmaku=2, reply=1)),
        (
            "低",
            _make_stats(view=1000, like=50, coin=10, favorite=5, danmaku=30, reply=10),
        ),
        (
            "中",
            _make_stats(
                view=10000, like=500, coin=100, favorite=80, danmaku=200, reply=50
            ),
        ),
        (
            "高",
            _make_stats(
                view=100000, like=5000, coin=1000, favorite=800, danmaku=2000, reply=500
            ),
        ),
        (
            "病毒式",
            _make_stats(
                view=5000000,
                like=200000,
                coin=50000,
                favorite=100000,
                danmaku=100000,
                reply=20000,
            ),
        ),
    ]
    scores_q = [
        (name, calc_doc_score(_make_doc(stats=s, pub_to_insert=SECONDS_1D)))
        for name, s in quality_tiers
    ]
    for i in range(len(scores_q) - 1):
        n1, s1 = scores_q[i]
        n2, s2 = scores_q[i + 1]
        _check(s1 < s2, f"质量: {n1}({s1:.4f}) < {n2}({s2:.4f})")

    # 投币加成的提升大于播放量加成
    # 使用较高的基础值，避免触发异常检测
    base_s = _make_stats(
        view=50000,
        like=2000,
        coin=500,
        favorite=300,
        danmaku=800,
        reply=200,
    )
    boosted_view = _make_stats(
        view=50000 + 20000,
        like=2000,
        coin=500,
        favorite=300,
        danmaku=800,
        reply=200,
    )
    boosted_coin = _make_stats(
        view=50000,
        like=2000,
        coin=500 + 200,
        favorite=300,
        danmaku=800,
        reply=200,
    )
    s_base = calc_doc_score(_make_doc(stats=base_s, pub_to_insert=SECONDS_1D))
    s_bv = calc_doc_score(_make_doc(stats=boosted_view, pub_to_insert=SECONDS_1D))
    s_bc = calc_doc_score(_make_doc(stats=boosted_coin, pub_to_insert=SECONDS_1D))
    _check(
        (s_bc - s_base) > (s_bv - s_base),
        f"投币加成 Δ{s_bc - s_base:.4f} > 播放加成 Δ{s_bv - s_base:.4f}",
    )

    # 收藏加成 ≈ 投币加成
    boosted_fav = _make_stats(
        view=50000,
        like=2000,
        coin=500,
        favorite=300 + 200,
        danmaku=800,
        reply=200,
    )
    s_bf = calc_doc_score(_make_doc(stats=boosted_fav, pub_to_insert=SECONDS_1D))
    _check_approx(
        s_bf - s_base,
        s_bc - s_base,
        "收藏加成 ≈ 投币加成",
        tol=0.01,
    )


# 7. 测试：calc_doc_score_detail 评分详情


def test_score_detail():
    logger.note("> test_score_detail")

    doc = _make_doc(
        stats=_make_stats(
            view=50000,
            like=2000,
            coin=500,
            favorite=300,
            danmaku=800,
            reply=200,
        ),
        pub_to_insert=SECONDS_1D,
    )
    detail = calc_doc_score_detail(doc)

    # 所有预期键都存在
    expected_keys = [
        "score",
        "stat_score",
        "anomaly_factor",
        "time_factor",
        "field_scores",
        "pub_to_insert",
    ]
    for key in expected_keys:
        _check(key in detail, f"详情包含键 '{key}'")

    # field_scores 包含所有统计字段
    for field in STAT_FIELDS:
        _check(
            field in detail["field_scores"],
            f"field_scores 包含 '{field}'",
        )

    # 详情分数与直接计算一致
    direct = calc_doc_score(doc)
    _check_approx(detail["score"], direct, "detail.score == calc_doc_score", tol=1e-12)

    # pub_to_insert 正确记录
    _check(detail["pub_to_insert"] == SECONDS_1D, "pub_to_insert 已记录")

    # 一致性：score = (BASE + stat * anomaly) * time
    reconstructed = (
        BASE_SCORE + detail["stat_score"] * detail["anomaly_factor"]
    ) * detail["time_factor"]
    _check_approx(
        detail["score"],
        reconstructed,
        "评分公式一致性",
        tol=1e-12,
    )

    # 各字段分数在 [0, 1) 范围内
    for field, fs in detail["field_scores"].items():
        _check(0 <= fs < 1.0, f"field_score[{field}] = {fs:.4f} ∈ [0, 1)")


# 8. 测试：边界情况


def test_edge_cases():
    logger.note("> test_edge_cases")

    # 完全没有 stats 字典
    s = calc_doc_score({"pubdate": 1000, "insert_at": 2000})
    _check(s > 0, f"缺少 stats → 正数 ({s:.6f})")

    # stats = None
    s = calc_doc_score({"stats": None, "pub_to_insert": SECONDS_1D})
    _check(s > 0, f"stats=None → 正数 ({s:.6f})")

    # stats 内部有 None 值
    stats_none = {"view": None, "like": None, "coin": 100}
    s = calc_doc_score(_make_doc(stats=stats_none, pub_to_insert=SECONDS_1D))
    _check(s > 0, f"stats 内含 None → 正数 ({s:.6f})")

    # 负数统计值 → 视为 0
    neg = _make_stats(view=-100, like=-50, coin=-10)
    s_neg = calc_doc_score(_make_doc(stats=neg, pub_to_insert=SECONDS_1D))
    s_zero = calc_doc_score(_make_doc(stats=_make_stats(), pub_to_insert=SECONDS_1D))
    _check_approx(s_neg, s_zero, "负数统计 ≡ 零统计", tol=1e-12)

    # pub_to_insert = 0 → 非常新鲜
    s0 = calc_doc_score(_make_doc(stats=_default_stats(), pub_to_insert=0))
    _check(s0 > 0, f"pub_to_insert=0 → 正数 ({s0:.6f})")

    # 负数 pub_to_insert → 截断到最大新鲜度
    s_neg_t = calc_doc_score(_make_doc(stats=_default_stats(), pub_to_insert=-5000))
    s_zero_t = calc_doc_score(_make_doc(stats=_default_stats(), pub_to_insert=0))
    _check_approx(s_neg_t, s_zero_t, "负数 pub_to_insert ≡ 0", tol=1e-12)

    # 极大统计值 → 无溢出，有界
    huge = _make_stats(
        view=1e15,
        like=1e14,
        coin=1e13,
        favorite=1e13,
        danmaku=1e14,
        reply=1e13,
    )
    s_huge = calc_doc_score(_make_doc(stats=huge, pub_to_insert=SECONDS_1D))
    _check(0 < s_huge < 2.0, f"极大统计值 → 有界 ({s_huge:.4f})")

    # 极大 pub_to_insert → 截断到最小因子
    s_old = calc_doc_score(_make_doc(stats=_default_stats(), pub_to_insert=10**9))
    s_30d = calc_doc_score(_make_doc(stats=_default_stats(), pub_to_insert=SECONDS_30D))
    _check_approx(s_old, s_30d, "极大 pub_to_insert ≡ 30天", tol=1e-12)

    # 只有 pubdate，没有 insert_at 或 pub_to_insert
    # pub_to_insert 回退为 0 - pubdate = 负数 → 截断到最大值
    s = calc_doc_score({"pubdate": 1000000, "stats": _default_stats()})
    _check(s > 0, f"仅 pubdate → 正数 ({s:.6f})")

    # 空字典
    s = calc_doc_score({})
    _check(s > 0, f"空字典 → 正数 ({s:.6f})")


# 9. 测试：评分总览表（可视化对比）


def test_score_summary():
    logger.note("> 评分总览表")

    cases = [
        ("零统计，新鲜(1h)", _make_doc(stats=_make_stats(), pub_to_insert=SECONDS_1H)),
        (
            "零统计，过时(60d)",
            _make_doc(stats=_make_stats(), pub_to_insert=SECONDS_30D * 2),
        ),
        (
            "低品质，新鲜(1h)",
            _make_doc(
                stats=_make_stats(
                    view=500, like=20, coin=5, favorite=3, danmaku=10, reply=5
                ),
                pub_to_insert=SECONDS_1H,
            ),
        ),
        (
            "低品质，1周",
            _make_doc(
                stats=_make_stats(
                    view=500, like=20, coin=5, favorite=3, danmaku=10, reply=5
                ),
                pub_to_insert=SECONDS_7D,
            ),
        ),
        ("中等，1天", _make_doc(stats=_default_stats(), pub_to_insert=SECONDS_1D)),
        ("中等，1周", _make_doc(stats=_default_stats(), pub_to_insert=SECONDS_7D)),
        (
            "热门，1天",
            _make_doc(
                stats=_make_stats(
                    view=50000,
                    like=2000,
                    coin=500,
                    favorite=300,
                    danmaku=800,
                    reply=200,
                ),
                pub_to_insert=SECONDS_1D,
            ),
        ),
        (
            "热门，2周",
            _make_doc(
                stats=_make_stats(
                    view=50000,
                    like=2000,
                    coin=500,
                    favorite=300,
                    danmaku=800,
                    reply=200,
                ),
                pub_to_insert=SECONDS_15D,
            ),
        ),
        (
            "病毒式，新鲜(1h)",
            _make_doc(
                stats=_make_stats(
                    view=10000000,
                    like=500000,
                    coin=100000,
                    favorite=200000,
                    danmaku=300000,
                    reply=50000,
                ),
                pub_to_insert=SECONDS_1H,
            ),
        ),
        (
            "病毒式，过时(60d)",
            _make_doc(
                stats=_make_stats(
                    view=10000000,
                    like=500000,
                    coin=100000,
                    favorite=200000,
                    danmaku=300000,
                    reply=50000,
                ),
                pub_to_insert=SECONDS_30D * 2,
            ),
        ),
        (
            "异常: 仅播放量高(1M)，新鲜",
            _make_doc(
                stats=_make_stats(
                    view=1000000, like=10, coin=0, favorite=2, danmaku=5, reply=1
                ),
                pub_to_insert=SECONDS_1H,
            ),
        ),
        (
            "异常: 仅播放量高(1M)，1周",
            _make_doc(
                stats=_make_stats(
                    view=1000000, like=10, coin=0, favorite=2, danmaku=5, reply=1
                ),
                pub_to_insert=SECONDS_7D,
            ),
        ),
        (
            "异常: 仅投币高(100K)，新鲜",
            _make_doc(
                stats=_make_stats(
                    view=200, like=10, coin=100000, favorite=5, danmaku=3, reply=1
                ),
                pub_to_insert=SECONDS_1H,
            ),
        ),
        (
            "异常: 仅收藏高(100K)，新鲜",
            _make_doc(
                stats=_make_stats(
                    view=300, like=15, coin=5, favorite=100000, danmaku=8, reply=2
                ),
                pub_to_insert=SECONDS_1H,
            ),
        ),
        (
            "异常: 播放+点赞高，新鲜",
            _make_doc(
                stats=_make_stats(
                    view=1000000, like=500000, coin=10, favorite=5, danmaku=20, reply=3
                ),
                pub_to_insert=SECONDS_1H,
            ),
        ),
    ]

    desc_width = 36
    header = (
        f"  {_ljust('描述', desc_width)} "
        f"{_rjust('总分', 8)} {_rjust('统计分', 8)} "
        f"{_rjust('异常', 6)} {_rjust('时间', 6)}"
    )
    logger.file(header)
    logger.file(
        f"  {'─' * desc_width} {'─' * 8} {'─' * 8} {'─' * 6} {'─' * 6}"
    )

    for desc, doc in cases:
        d = calc_doc_score_detail(doc)
        logger.file(
            f"  {_ljust(desc, desc_width)} {d['score']:8.4f} {d['stat_score']:8.4f} "
            f"{d['anomaly_factor']:6.3f} {d['time_factor']:6.3f}"
        )


# 运行器


def run_all_tests():
    global _passed, _failed, _errors
    _passed = 0
    _failed = 0
    _errors.clear()

    test_saturate()
    test_stat_score()
    test_anomaly_factor()
    test_time_factor()
    test_score_integration()
    test_score_ordering()
    test_score_detail()
    test_edge_cases()
    test_score_summary()

    logger.note(f"\n> 结果: {_passed} 通过, {_failed} 失败")
    if _errors:
        logger.warn(f"  失败的测试:")
        for e in _errors:
            logger.warn(f"    - {e}")
    else:
        logger.okay(f"  全部 {_passed} 个测试通过！")

    return _failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    if not success:
        raise SystemExit(1)
