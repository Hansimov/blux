TABLE = "fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF"
INDEX = {ch: i for i, ch in enumerate(TABLE)}
S = [11, 10, 3, 8, 4, 6]
XOR = 177451812
ADD = 8728348608


def bv_to_av(bv: str) -> int:
    r = 0
    for i, pos in enumerate(S):
        r += INDEX[bv[pos]] * (58**i)
    return (r - ADD) ^ XOR


def av_to_bv(aid: int) -> str:
    x = (aid ^ XOR) + ADD
    tpl = list("BV1  4 1 7  ")
    for i, pos in enumerate(S):
        tpl[pos] = TABLE[(x // (58**i)) % 58]
    return "".join(tpl)


def test_bv_to_av():
    from tclogger import logger, logstr

    test_cases = [
        ("BV1xx411c7mW", 100),
        ("BV1bx411c7ux", 10000),
        ("BV1Ex411U7PA", 10000000),
        ("BV1MKk9BTE1E", 115519722102585),
        ("BV1QMSjBREzr", 115626945283535),
    ]
    for bv, av in test_cases:
        logger.note(f"* bv={bv}, av={av}")
        bv_res = av_to_bv(av)
        av_res = bv_to_av(bv)

        if bv_res == bv:
            logger.okay(f"  ✓ av_to_bv")
        else:
            logger.file(f"  × av_to_bv: {logstr.warn(bv_res)} != {logstr.okay(bv)}")

        if av_res == av:
            logger.okay(f"  ✓ bv_to_av")
        else:
            logger.file(f"  × bv_to_av: {logstr.warn(av_res)} != {logstr.okay(av)}")


if __name__ == "__main__":
    test_bv_to_av()

    # python -m blux.bvs
