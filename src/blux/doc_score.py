"""文档评分模块。

根据互动统计数据和新鲜度对文档进行评分。

评分特性：
  - 恒为正数（> 0）
  - 互动权重：投币 ≈ 收藏 > 评论 ≈ 弹幕 ≈ 点赞 > 播放
  - 边际递减：每个字段使用对数饱和函数，值越大增长越慢
  - 异常检测：通过字段间一致性识别任意异常偏高的字段，施加惩罚
  - 新鲜度加成：越新的内容分数越高
  - 有界性：即使极端输入也不会导致分数膨胀

评分流程：
  1. 每个字段独立通过饱和函数映射到 [0, 1)
  2. 加权平均得到统计分 stat_score ∈ [0, 1)
  3. 异常因子惩罚分布不均匀的字段 ∈ [ANOMALY_MIN_FACTOR, 1.0]
  4. 时间因子根据新鲜度调整 ∈ [TIME_FACTOR_MIN, TIME_FACTOR_MAX]
  5. 最终分 = (BASE_SCORE + stat_score × anomaly_factor) × time_factor
"""

import math


class DocScorer:
    """文档评分器。

    根据互动统计数据和新鲜度对文档进行评分。
    所有评分配置以类属性形式定义，可通过子类化进行定制。
    """

    # 字段评分配置
    #
    # 每个字段包含：
    #   weight : 权重（越高对最终分影响越大）
    #   alpha  : 对数饱和函数的半饱和常数，半饱和点 x_half = e^alpha - 1
    #
    # 权重层级：投币 ≈ 收藏 > 评论 ≈ 弹幕 ≈ 点赞 > 播放

    STAT_CONFIGS = {
        "view": {"weight": 1.0, "alpha": 8.0},  # x_half ≈ 2980
        "like": {"weight": 2.0, "alpha": 5.5},  # x_half ≈ 244
        "coin": {"weight": 3.0, "alpha": 4.5},  # x_half ≈ 89
        "favorite": {"weight": 3.0, "alpha": 4.5},  # x_half ≈ 89
        "danmaku": {"weight": 2.0, "alpha": 5.5},  # x_half ≈ 244
        "reply": {"weight": 2.0, "alpha": 5.0},  # x_half ≈ 147
    }

    STAT_FIELDS = list(STAT_CONFIGS.keys())
    TOTAL_WEIGHT = sum(cfg["weight"] for cfg in STAT_CONFIGS.values())  # 13.0

    # 时间评分配置

    SECONDS_1H = 3600
    SECONDS_1D = 86400
    SECONDS_3D = 259200
    SECONDS_7D = 604800
    SECONDS_15D = 1296000
    SECONDS_30D = 2592000

    # 对数时间空间中的分段线性锚点
    # 格式：(秒数, 时间因子)
    # - 因子 > 1.0 → 新鲜度加成
    # - 因子 < 1.0 → 过时惩罚

    TIME_ANCHORS = [
        (SECONDS_1H, 1.30),  # ≤ 1小时  ：最大新鲜度
        (SECONDS_1D, 1.10),  # 1天      ：仍然新鲜
        (SECONDS_3D, 0.90),  # 3天      ：轻微惩罚
        (SECONDS_7D, 0.70),  # 7天      ：中等惩罚
        (SECONDS_15D, 0.55),  # 15天     ：较强惩罚
        (SECONDS_30D, 0.45),  # ≥ 30天   ：下限
    ]

    TIME_FACTOR_MAX = TIME_ANCHORS[0][1]  # 1.30
    TIME_FACTOR_MIN = TIME_ANCHORS[-1][1]  # 0.45

    # 异常检测配置
    #
    # 用每个字段值相对其半饱和点的对数归一化尺度来衡量字段间的一致性。
    # 若某 1-2 个字段远高于其他字段，均值/最大值的比率会显著降低，触发惩罚。
    # 本方法不局限于播放量异常，能识别任意字段的异常偏高情况。

    ANOMALY_MIN_LOG_SCALE = 0.5  # 最大对数尺度低于此值时跳过异常检测
    ANOMALY_CONSISTENCY_THRESHOLD = 0.5  # 一致性比率低于此值时触发惩罚
    ANOMALY_MIN_FACTOR = 0.3  # 异常惩罚的下限

    # 基础分，保证总分恒为正
    BASE_SCORE = 0.01

    @staticmethod
    def _saturate(x: float, alpha: float) -> float:
        """对数饱和函数，将 [0, ∞) 映射到 [0, 1)，具有边际递减特性。

            f(x) = ln(1 + x) / (ln(1 + x) + α)

        当 ln(1 + x) = α 时，f(x) = 0.5（半饱和点 x = e^α − 1）。
        """
        if x <= 0:
            return 0.0
        log_val = math.log1p(x)
        return log_val / (log_val + alpha)

    def _calc_stat_score(self, stats: dict) -> float:
        """计算各字段饱和分的加权平均值。

        每个字段独立通过 _saturate 计算分数，再用配置的权重合成
        为一个 ∈ [0, 1) 的综合统计分。
        """
        weighted_sum = 0.0
        for field, cfg in self.STAT_CONFIGS.items():
            value = max(0, stats.get(field, 0) or 0)
            weighted_sum += cfg["weight"] * self._saturate(value, cfg["alpha"])
        return weighted_sum / self.TOTAL_WEIGHT

    def _calc_anomaly_factor(self, stats: dict) -> float:
        """基于字段间一致性的通用异常检测。

        将每个字段的原始值除以其半饱和点进行归一化，再取对数得到
        对数归一化尺度（log_scale）。通过比较所有字段 log_scale 的
        均值与最大值的比率来衡量一致性：

          - 比率接近 1.0 → 各字段量级均衡，无异常
          - 比率很低 → 某 1-2 个字段远高于其他字段，存在异常

        本方法不局限于播放量异常，能识别任意字段的异常偏高情况。
        使用 sqrt 曲线平滑过渡，返回 ∈ [ANOMALY_MIN_FACTOR, 1.0]。
        """
        log_scales = []
        for field, cfg in self.STAT_CONFIGS.items():
            value = max(0, stats.get(field, 0) or 0)
            half_sat = math.expm1(cfg["alpha"])  # e^alpha - 1
            relative = value / half_sat
            log_scales.append(math.log1p(relative))

        max_log = max(log_scales)
        if max_log < self.ANOMALY_MIN_LOG_SCALE:
            return 1.0  # 数据量太少，不做异常判断

        mean_log = sum(log_scales) / len(log_scales)
        consistency = mean_log / max_log  # ∈ [0, 1]

        if consistency >= self.ANOMALY_CONSISTENCY_THRESHOLD:
            return 1.0

        # sqrt 曲线平滑惩罚
        t = consistency / self.ANOMALY_CONSISTENCY_THRESHOLD
        return self.ANOMALY_MIN_FACTOR + (1.0 - self.ANOMALY_MIN_FACTOR) * math.sqrt(t)

    def _calc_time_factor(self, pub_to_insert: int) -> float:
        """通过分段对数线性插值计算新鲜度因子。

        各时间段的行为：
          - t ≤ 1小时   → 常数 TIME_FACTOR_MAX (1.30)
          - 1小时–1天   → 缓慢衰减
          - 1天–3天     → 中等衰减
          - 3天–7天     → 较快衰减
          - 7天–15天    → 持续衰减
          - 15天–30天   → 最后衰减
          - t ≥ 30天    → 常数 TIME_FACTOR_MIN (0.45)
        """
        t = max(0, pub_to_insert)

        if t <= self.TIME_ANCHORS[0][0]:
            return self.TIME_ANCHORS[0][1]
        if t >= self.TIME_ANCHORS[-1][0]:
            return self.TIME_ANCHORS[-1][1]

        log_t = math.log(t)
        for i in range(len(self.TIME_ANCHORS) - 1):
            t0, f0 = self.TIME_ANCHORS[i]
            t1, f1 = self.TIME_ANCHORS[i + 1]
            if t <= t1:
                log_t0 = math.log(t0)
                log_t1 = math.log(t1)
                frac = (log_t - log_t0) / (log_t1 - log_t0)
                return f0 + frac * (f1 - f0)

        return self.TIME_ANCHORS[-1][1]

    def calc_score(self, doc: dict) -> float:
        """计算文档的质量/相关性分数。

        参数：
            doc: 包含以下字段的字典：
                pubdate (int): 发布时间戳
                insert_at (int): 插入时间戳
                stats (dict): {view, like, coin, favorite, danmaku, reply, share}
                pub_to_insert (int, 可选): 发布到插入的时间差（秒）
                    若缺失则用 insert_at − pubdate 计算

        返回：
            正浮点数分数。越高代表质量越好 + 越新鲜。
        """
        stats = doc.get("stats", {}) or {}
        stat_score = self._calc_stat_score(stats)
        anomaly_factor = self._calc_anomaly_factor(stats)

        pub_to_insert = doc.get("pub_to_insert")
        if pub_to_insert is None:
            pub_to_insert = (doc.get("insert_at", 0) or 0) - (
                doc.get("pubdate", 0) or 0
            )
        time_factor = self._calc_time_factor(pub_to_insert)

        return (self.BASE_SCORE + stat_score * anomaly_factor) * time_factor

    def calc_score_detail(self, doc: dict) -> dict:
        """返回详细的评分分解，用于调试和分析。

        返回：
            包含以下键的字典：score, stat_score, anomaly_factor, time_factor,
            field_scores（各字段的饱和分数）, pub_to_insert。
        """
        stats = doc.get("stats", {}) or {}

        field_scores = {}
        for field, cfg in self.STAT_CONFIGS.items():
            value = max(0, stats.get(field, 0) or 0)
            field_scores[field] = self._saturate(value, cfg["alpha"])

        stat_score = self._calc_stat_score(stats)
        anomaly_factor = self._calc_anomaly_factor(stats)

        pub_to_insert = doc.get("pub_to_insert")
        if pub_to_insert is None:
            pub_to_insert = (doc.get("insert_at", 0) or 0) - (
                doc.get("pubdate", 0) or 0
            )
        time_factor = self._calc_time_factor(pub_to_insert)

        score = (self.BASE_SCORE + stat_score * anomaly_factor) * time_factor

        return {
            "score": score,
            "stat_score": stat_score,
            "anomaly_factor": anomaly_factor,
            "time_factor": time_factor,
            "field_scores": field_scores,
            "pub_to_insert": pub_to_insert,
        }


# 默认评分器实例
doc_scorer = DocScorer()

# 便捷函数（保持向后兼容的模块级接口）
calc_doc_score = doc_scorer.calc_score
calc_doc_score_detail = doc_scorer.calc_score_detail
