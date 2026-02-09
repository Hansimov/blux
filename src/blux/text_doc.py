from dataclasses import dataclass
from hashlib import md5
from tclogger import logstr, dict_get


def build_sentence(
    title: str = "",
    tags: str = "",
    desc: str = "",
    owner_name: str = "",
    max_len: int = None,
) -> str:
    """Build text sentence from document fields for embedding or text processing.

    Combines owner_name, title, tags, desc into a single sentence.

    Field formats:
        - owner_name: wrapped in 【】brackets
        - title: as-is
        - tags: wrapped in parentheses ()
        - desc: as-is (skipped if just "-")

    Args:
        title: Video title
        tags: Video tags (comma-separated string)
        desc: Video description
        owner_name: Video owner/UP主 name
        max_len: Maximum sentence length (truncated if exceeded)

    Returns:
        Combined text string
    """
    sentence = ""

    owner_name_strip = (owner_name or "").strip()
    if owner_name_strip:
        sentence += f"【{owner_name_strip}】"

    title_strip = (title or "").strip()
    if title_strip:
        if sentence:
            sentence += " "
        sentence += title_strip

    tags_strip = (tags or "").strip()
    if tags_strip:
        if sentence:
            sentence += " "
        sentence += f"({tags_strip})"

    desc_strip = (desc or "").strip()
    if desc_strip and desc_strip != "-":
        if sentence:
            sentence += " "
        sentence += desc_strip

    if max_len and len(sentence) > max_len:
        sentence = sentence[:max_len]

    return sentence


def build_sentence_for_md5(
    title: str = "",
    tags: str = "",
    desc: str = "",
    owner_name: str = "",
) -> str:
    """Build text sentence for md5 calculation.

    This function is kept stable and separate from build_sentence(),
    because build_sentence() may evolve over time for display/embedding
    purposes, while md5 hashing requires a fixed text format to ensure
    consistent hash values.

    Args:
        title: Video title
        tags: Video tags (comma-separated string)
        desc: Video description
        owner_name: Video owner/UP主 name

    Returns:
        Combined text string for md5 hashing
    """
    sentence = ""

    owner_name_strip = (owner_name or "").strip()
    if owner_name_strip:
        sentence += f"【{owner_name_strip}】"

    title_strip = (title or "").strip()
    if title_strip:
        if sentence:
            sentence += " "
        sentence += title_strip

    tags_strip = (tags or "").strip()
    if tags_strip:
        if sentence:
            sentence += " "
        sentence += f"({tags_strip})"

    desc_strip = (desc or "").strip()
    if desc_strip and desc_strip != "-":
        if sentence:
            sentence += " "
        sentence += desc_strip

    return sentence


def calc_md5(
    title: str = "",
    tags: str = "",
    desc: str = "",
    owner_name: str = "",
    chars_length: int = 4,
) -> str:
    """Calculate md5 hash from text fields.

    Uses build_sentence_for_md5() to construct the text content for hashing.

    Args:
        title: Video title
        tags: Video tags (comma-separated string)
        desc: Video description
        owner_name: Video owner/UP主 name
        chars_length: Number of characters to use from the md5 hash (default 4)
    Returns:
        4-character hex string (first 4 chars of md5 hexdigest)
    """
    text = build_sentence_for_md5(
        title=title, tags=tags, desc=desc, owner_name=owner_name
    )
    return md5(text.encode("utf-8")).hexdigest()[:chars_length]


@dataclass
class TextDocItem:
    bvid: str
    title: str
    tags: str
    owner_name: str
    desc: str
    # built from above fields
    sentence: str = ""
    md5_hash: str = ""

    @staticmethod
    def from_doc(doc: dict) -> "TextDocItem":
        return TextDocItem(
            bvid=doc.get("bvid", ""),
            title=dict_get(doc, "title", ""),
            tags=dict_get(doc, "tags", ""),
            owner_name=dict_get(doc, "owner.name", ""),
            desc=dict_get(doc, "desc", ""),
        )

    def calc_md5_hash(self) -> str:
        self.md5_hash = calc_md5(
            title=self.title,
            tags=self.tags,
            desc=self.desc,
            owner_name=self.owner_name,
        )
        return self.md5_hash

    def build_sentence(self, max_len: int = None) -> str:
        self.sentence = build_sentence(
            title=self.title,
            tags=self.tags,
            desc=self.desc,
            owner_name=self.owner_name,
            max_len=max_len,
        )
        return self.sentence

    def log_sentence(self):
        print(f"{logstr.note(self.bvid)}: {logstr.mesg(self.sentence)}")
