from __future__ import annotations

from typing import Final


# =========================
# Default canonical sections
# =========================
DEFAULT_CANONICAL_SECTIONS: Final[list[str]] = [
    "Thông tin doanh nghiệp",
    "Mục tiêu dự án",
    "Phạm vi công việc",
    "Kế hoạch triển khai",
    "Rủi ro",
    "Kết luận",
]


# =========================
# Heading regex patterns
# =========================
HEADING_NUMBER_PATTERNS: Final[list[str]] = [
    r"^\d+\.\s+.+",                # 1. Heading
    r"^\d+\.\d+\s+.+",             # 1.1 Heading
    r"^\d+\.\d+\.\d+\s+.+",        # 1.1.1 Heading
    r"^[IVXLC]+\.\s+.+",           # I. Heading
    r"^[A-Z]\.\s+.+",              # A. Heading
    r"^(CHƯƠNG|Chương)\s+\d+.*",   # Chương 1
    r"^(PHẦN|Phần)\s+\d+.*",       # Phần 1
    r"^(SECTION|Section)\s+\d+.*", # Section 1
]


# =========================
# Common heading styles in Word
# =========================
COMMON_HEADING_STYLES: Final[set[str]] = {
    "Heading 1",
    "Heading 2",
    "Heading 3",
    "Title",
    "Subtitle",
}


# =========================
# Matching score weights
# =========================
SYNONYM_WEIGHT: Final[float] = 0.25
FUZZY_WEIGHT: Final[float] = 0.35
EMBEDDING_WEIGHT: Final[float] = 0.40


# =========================
# Content / heading heuristics
# =========================
MAX_HEADING_TEXT_LENGTH: Final[int] = 120
MIN_HEADING_TEXT_LENGTH: Final[int] = 2

MAX_HEADING_WORD_COUNT: Final[int] = 15
MIN_SECTION_CONTENT_LENGTH: Final[int] = 10


# =========================
# Report status labels
# =========================
MATCH_STATUS_AUTO: Final[str] = "auto_accepted"
MATCH_STATUS_REVIEW: Final[str] = "needs_review"
MATCH_STATUS_UNMATCHED: Final[str] = "unmatched"


# =========================
# Supported file suffixes
# =========================
SUPPORTED_WORD_SUFFIXES: Final[set[str]] = {
    ".docx",
}


# =========================
# Placeholder mapping suggestion
# Dùng cho template Word nếu muốn map cố định section -> placeholder
# =========================
DEFAULT_SECTION_PLACEHOLDERS: Final[dict[str, str]] = {
    "Thông tin doanh nghiệp": "company_info",
    "Mục tiêu dự án": "project_objective",
    "Phạm vi công việc": "scope_of_work",
    "Kế hoạch triển khai": "implementation_plan",
    "Rủi ro": "risks",
    "Kết luận": "conclusion",
}