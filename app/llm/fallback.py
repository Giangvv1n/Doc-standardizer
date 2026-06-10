from __future__ import annotations

from loguru import logger
import openai

from app.config import settings


class LLMFallback:
    """Uses LLM (OpenAI) to resolve ambiguous section headings or extract content from text."""

    def __init__(self) -> None:
        self.enabled = settings.use_llm_fallback and bool(settings.openai_api_key)
        self.client = None

        if self.enabled:
            logger.info("OpenAI LLM Fallback is enabled.")
            self.client = openai.OpenAI(api_key=settings.openai_api_key)
        else:
            logger.info("OpenAI LLM Fallback is disabled (missing key or USE_LLM_FALLBACK is false).")

    def classify_heading(self, heading_text: str, canonical_sections: list[str]) -> str | None:
        """Asks LLM to classify an ambiguous heading text into one of the canonical sections."""
        if not self.enabled or not self.client:
            return None

        prompt = (
            f"Bạn là một chuyên gia phân tích cấu trúc tài liệu.\n"
            f"Hãy phân loại tiêu đề sau đây từ một tài liệu dự án vào một trong các tiêu đề chuẩn.\n\n"
            f"Tiêu đề cần phân loại: \"{heading_text}\"\n\n"
            f"Danh sách tiêu đề chuẩn:\n"
            + "\n".join(f"- {s}" for s in canonical_sections)
            + "\n- Không thuộc tiêu đề nào ở trên (Trả về: None)\n\n"
            f"Chỉ trả về chính xác tên tiêu đề chuẩn được chọn (hoặc trả về từ 'None' nếu không khớp). "
            f"Không thêm bất kỳ giải thích nào khác."
        )

        try:
            logger.info(f"Querying LLM to classify heading: '{heading_text}'")
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful document parsing assistant. Output only the final answer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=50
            )
            result = response.choices[0].message.content.strip()
            
            if result in canonical_sections:
                logger.info(f"LLM successfully classified '{heading_text}' -> '{result}'")
                return result
            else:
                logger.info(f"LLM classified '{heading_text}' as unmatched/None")
                return None
        except Exception as e:
            logger.error(f"OpenAI API error during heading classification: {e}")
            return None

    def extract_section_content(self, document_text: str, section_name: str, section_description: str = "") -> str | None:
        """Asks LLM to extract text content for a canonical section from the raw document text."""
        if not self.enabled or not self.client:
            return None

        desc_part = f" (Mô tả: {section_description})" if section_description else ""
        prompt = (
            f"Dưới đây là nội dung thô của một tài liệu dự án:\n"
            f"===================================\n"
            f"{document_text[:12000]}\n"  # Truncate to stay safe with token limits
            f"===================================\n\n"
            f"Hãy trích xuất hoặc tổng hợp thông tin liên quan đến mục tiêu/nội dung \"{section_name}\"{desc_part} từ tài liệu trên.\n"
            f"Yêu cầu:\n"
            f"1. Chỉ trích xuất thông tin có thực trong tài liệu, không tự ý bịa đặt thông tin.\n"
            f"2. Giữ nguyên tính chính xác của thông tin.\n"
            f"3. Nếu tài liệu hoàn toàn không đề cập đến nội dung này, chỉ trả về chuỗi rỗng: \"\"\n"
            f"4. Trả về câu văn/đoạn văn trực tiếp dạng văn bản thô tiếng Việt, không kèm theo tiêu đề lớn hay giải thích ngoài lề."
        )

        try:
            logger.info(f"Querying LLM to extract content for canonical section: '{section_name}'")
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert document extraction assistant. Output only the extracted content or empty string."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            extracted_text = response.choices[0].message.content.strip()
            if extracted_text:
                logger.info(f"LLM successfully extracted content for '{section_name}' ({len(extracted_text)} chars)")
                return extracted_text
            else:
                logger.info(f"LLM found no content for '{section_name}'")
                return None
        except Exception as e:
            logger.error(f"OpenAI API error during content extraction for {section_name}: {e}")
            return None
