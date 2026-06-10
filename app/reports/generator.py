from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from loguru import logger

from app.config import settings


class ReportGenerator:
    """Generates visual HTML processing reports summarizing the standardization results."""

    def __init__(self) -> None:
        self.report_dir = settings.report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, run_results: list[dict[str, Any]]) -> Path:
        """
        Generates a visually stunning HTML report summarizing the results.
        run_results is a list of dictionaries, each containing:
            - file_name: str
            - success: bool
            - error_message: str | None
            - mappings: dict of canonical_section -> list of (heading, score, status)
            - unmatched_sections: list of (heading, score, status)
            - llm_fallback_triggered: bool
            - timestamp: str
        """
        logger.info("Generating standardization report...")
        
        # Calculate summary statistics
        total_files = len(run_results)
        successful_files = sum(1 for r in run_results if r.get("success", False))
        failed_files = total_files - successful_files
        
        total_auto = 0
        total_review = 0
        total_unmatched = 0

        for res in run_results:
            if not res.get("success", False):
                continue
            
            # Count statuses in mappings
            for section_matches in res.get("mappings", {}).values():
                for _, _, status in section_matches:
                    if status == "auto_accepted":
                        total_auto += 1
                    elif status == "needs_review":
                        total_review += 1
            
            # Count unmatched source sections
            total_unmatched += len(res.get("unmatched_sections", []))

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # HTML content
        html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Báo cáo Chuẩn hóa Tài liệu AI</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0f172a;
            --panel-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --primary: #38bdf8;
            --primary-glow: rgba(56, 189, 248, 0.15);
            --success: #34d399;
            --success-glow: rgba(52, 211, 153, 0.15);
            --warning: #fbbf24;
            --warning-glow: rgba(251, 191, 36, 0.15);
            --danger: #f87171;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 2rem;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            margin-bottom: 2.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}

        h1 {{
            font-size: 2.25rem;
            font-weight: 700;
            color: var(--primary);
            text-shadow: 0 0 20px var(--primary-glow);
        }}

        .timestamp {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}

        /* Dashboard grid */
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }}

        .card {{
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(12px);
            border-radius: 16px;
            padding: 1.5rem;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
        }}

        .card-title {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}

        .card-value {{
            font-size: 2.25rem;
            font-weight: 700;
        }}

        .value-primary {{ color: var(--primary); }}
        .value-success {{ color: var(--success); }}
        .value-warning {{ color: var(--warning); }}
        .value-danger {{ color: var(--danger); }}

        /* Detailed Results */
        .results-section {{
            margin-top: 2rem;
        }}

        .results-title {{
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .doc-entry {{
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            margin-bottom: 2rem;
            overflow: hidden;
        }}

        .doc-header {{
            background: rgba(15, 23, 42, 0.6);
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .doc-name {{
            font-size: 1.125rem;
            font-weight: 600;
            color: var(--primary);
        }}

        .badge {{
            padding: 0.35rem 0.75rem;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .badge-success {{
            background: var(--success-glow);
            color: var(--success);
            border: 1px solid rgba(52, 211, 153, 0.3);
        }}

        .badge-warning {{
            background: var(--warning-glow);
            color: var(--warning);
            border: 1px solid rgba(251, 191, 36, 0.3);
        }}

        .badge-danger {{
            background: rgba(248, 113, 113, 0.15);
            color: var(--danger);
            border: 1px solid rgba(248, 113, 113, 0.3);
        }}

        .doc-body {{
            padding: 1.5rem;
        }}

        .error-box {{
            background: rgba(248, 113, 113, 0.08);
            border: 1px solid rgba(248, 113, 113, 0.2);
            border-radius: 8px;
            padding: 1rem;
            color: var(--danger);
            font-size: 0.9375rem;
        }}

        /* Table styles */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}

        th {{
            text-align: left;
            padding: 0.75rem 1rem;
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.875rem;
            border-bottom: 1px solid var(--border-color);
        }}

        td {{
            padding: 1rem;
            font-size: 0.9375rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        .score-val {{
            font-family: monospace;
            font-weight: 600;
        }}

        .status-cell {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}

        .dot-auto {{ background-color: var(--success); }}
        .dot-review {{ background-color: var(--warning); }}
        .dot-unmatched {{ background-color: var(--text-secondary); }}

        /* Unmatched section box */
        .unmatched-box {{
            margin-top: 1.5rem;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
        }}

        .unmatched-title {{
            font-size: 0.9375rem;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 0.75rem;
        }}

        .unmatched-list {{
            list-style: none;
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}

        .unmatched-item {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            padding: 0.35rem 0.75rem;
            border-radius: 8px;
            font-size: 0.8125rem;
            color: var(--text-secondary);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Báo cáo Chuẩn hóa Tài liệu AI</h1>
                <p style="color: var(--text-secondary); margin-top: 0.25rem;">Hệ thống trích xuất và ánh xạ cấu trúc tài liệu Word</p>
            </div>
            <div class="timestamp">
                Thời gian quét: {timestamp_str}
            </div>
        </header>

        <!-- Summary Statistics -->
        <div class="dashboard-grid">
            <div class="card">
                <div class="card-title">Tổng số tài liệu</div>
                <div class="card-value value-primary">{total_files}</div>
            </div>
            <div class="card">
                <div class="card-title">Thành công</div>
                <div class="card-value value-success">{successful_files}</div>
            </div>
            <div class="card">
                <div class="card-title">Thất bại</div>
                <div class="card-value value-danger">{failed_files}</div>
            </div>
            <div class="card">
                <div class="card-title">Tự động duyệt</div>
                <div class="card-value value-success">{total_auto}</div>
            </div>
            <div class="card">
                <div class="card-title">Cần xem xét</div>
                <div class="card-value value-warning">{total_review}</div>
            </div>
        </div>

        <!-- Detailed Results -->
        <div class="results-section">
            <h2 class="results-title">Chi tiết xử lý tài liệu</h2>
"""

        for res in run_results:
            file_name = res["file_name"]
            success = res["success"]
            
            badge_class = "badge-success" if success else "badge-danger"
            badge_text = "Thành công" if success else "Lỗi"
            
            html_content += f"""
            <div class="doc-entry">
                <div class="doc-header">
                    <div class="doc-name">{file_name}</div>
                    <span class="badge {badge_class}">{badge_text}</span>
                </div>
                <div class="doc-body">
            """
            
            if not success:
                html_content += f"""
                    <div class="error-box">
                        <strong>Mô tả lỗi:</strong> {res.get('error_message', 'Không rõ nguyên nhân')}
                    </div>
                """
            else:
                html_content += """
                    <table>
                        <thead>
                            <tr>
                                <th>Tiêu đề chuẩn (Canonical)</th>
                                <th>Tiêu đề nguồn ánh xạ</th>
                                <th>Độ tương đồng</th>
                                <th>Trạng thái</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                
                # Sort sections by mapping keys
                mappings = res.get("mappings", {})
                for canonical, matches in sorted(mappings.items()):
                    if not matches:
                        html_content += f"""
                            <tr>
                                <td><strong>{canonical}</strong></td>
                                <td style="color: var(--danger); font-style: italic;">Không tìm thấy nội dung phù hợp</td>
                                <td class="score-val value-danger">0.0000</td>
                                <td class="status-cell">
                                    <span class="status-dot dot-unmatched"></span>
                                    <span style="color: var(--text-secondary);">unmatched</span>
                                </td>
                            </tr>
                        """
                    else:
                        for section, score, status in matches:
                            heading = section.heading_text
                            
                            if status == "auto_accepted":
                                dot_class = "dot-auto"
                                score_class = "value-success"
                                status_text = "Tự động duyệt"
                            else:
                                dot_class = "dot-review"
                                score_class = "value-warning"
                                status_text = "Cần xem xét"

                            html_content += f"""
                                <tr>
                                    <td><strong>{canonical}</strong></td>
                                    <td>{heading}</td>
                                    <td class="score-val {score_class}">{score:.4f}</td>
                                    <td class="status-cell">
                                        <span class="status-dot {dot_class}"></span>
                                        <span>{status_text}</span>
                                    </td>
                                </tr>
                            """
                
                html_content += """
                        </tbody>
                    </table>
                """
                
                # Unmatched source sections list
                unmatched = res.get("unmatched_sections", [])
                if unmatched:
                    html_content += """
                    <div class="unmatched-box">
                        <div class="unmatched-title">Các phần không được ánh xạ từ tài liệu gốc:</div>
                        <ul class="unmatched-list">
                    """
                    for section, score, status in unmatched:
                        html_content += f"""
                            <li class="unmatched-item">
                                <strong>{section.heading_text}</strong> (Độ khớp tối đa: {score:.2f})
                            </li>
                        """
                    html_content += """
                        </ul>
                    </div>
                    """
                    
                if res.get("llm_fallback_triggered", False):
                    html_content += """
                    <div style="margin-top: 1rem; font-size: 0.8125rem; color: var(--primary); display: flex; align-items: center; gap: 0.25rem;">
                        <span class="status-dot dot-auto" style="width: 6px; height: 6px;"></span>
                        <em>Đã kích hoạt AI Fallback để hỗ trợ trích xuất / phân loại các phần thiếu.</em>
                    </div>
                    """
            
            html_content += """
                </div>
            </div>
            """

        html_content += """
        </div>
    </div>
</body>
</html>
"""

        report_path = self.report_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        logger.info(f"Writing report to: {report_path}")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Also maintain a latest.html copy for easy previewing
        latest_path = self.report_dir / "latest.html"
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return report_path
