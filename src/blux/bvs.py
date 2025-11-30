"""
References:
- https://github.com/Colerar/abv/blob/main/src/lib.rs
"""

from tclogger import logger, logstr
from typing import Union

XOR_CODE = 23442827791579
MASK_CODE = 2251799813685247

MIN_AID = 1
MAX_AID = 1 << 51

BASE = 58
BV_LEN = 12
PREFIX = "BV1"

ALPHABET = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"
REV = {ch: i for i, ch in enumerate(ALPHABET)}


def check_aid_range(aid: int) -> None:
    if aid < MIN_AID or aid >= MAX_AID:
        raise ValueError(f"Invalid aid: {aid}, must be in range [{MIN_AID}, {MAX_AID})")


def check_bv_format(bv: str) -> None:
    if not bv:
        raise ValueError(f"Invalid bv: got empty")
    if len(bv) != BV_LEN:
        raise ValueError(f"Invalid bv: got str length {len(bv)}, must be {BV_LEN}")
    if not bv[:3].upper() == PREFIX:
        raise ValueError(f"Invalid bv: got prefix '{bv[:3]}', must be '{PREFIX}'")


def check_bv_chars(bv: str) -> None:
    for ch in bv:
        if ch not in REV:
            raise ValueError(f"Invalid bv: got char {ch}")


def check_bv_int_len(bv_int: int) -> None:
    """bv in binary should be 52 bits"""
    bin_len = bv_int.bit_length()
    if bin_len != 52:
        raise ValueError(f"Invalid bv: got bits in binary: {bin_len}, must be 52")


def swap_bv_chars(bv: list[str]) -> None:
    """swap positions of bv chars: 3 <-> 9, 4 <-> 7"""
    bv[3], bv[9] = bv[9], bv[3]
    bv[4], bv[7] = bv[7], bv[4]


def av_to_bv(aid: int) -> str:
    check_aid_range(aid)
    bv = list("BV1000000000")
    bv_idx = BV_LEN - 1
    tmp = (MAX_AID | aid) ^ XOR_CODE
    while tmp != 0:
        table_idx = tmp % BASE
        bv[bv_idx] = ALPHABET[table_idx]
        tmp //= BASE
        bv_idx -= 1
    swap_bv_chars(bv)
    return "".join(bv)


def bv_to_av(bv: str) -> int:
    check_bv_format(bv)
    check_bv_chars(bv)
    bv = list(bv)
    swap_bv_chars(bv)
    bv_int = 0
    for ch in bv[3:]:
        bv_int = bv_int * BASE + REV[ch]
    check_bv_int_len(bv_int)
    aid = (bv_int & MASK_CODE) ^ XOR_CODE
    check_aid_range(aid)
    return aid


def log_vres(abv: Union[int, str], res: Union[int, str], func_name: str):
    if abv == res:
        logger.okay(f"  √ {func_name}")
    else:
        logger.file(f"  × {func_name}: {logstr.warn(res)} != {logstr.okay(abv)}")


def log_res(av: int, bv: str, av_res: int, bv_res: str):
    log_vres(bv, bv_res, "av_to_bv")
    log_vres(av, av_res, "bv_to_av")


def test_bv_to_av():
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
        log_res(av, bv, av_res, bv_res)


if __name__ == "__main__":
    test_bv_to_av()

    # python -m blux.bvs
