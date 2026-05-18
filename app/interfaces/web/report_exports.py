from __future__ import annotations

import csv
from io import StringIO


PAGE_WIDTH = 842
PAGE_HEIGHT = 595
MARGIN_X = 34
TOP_Y = PAGE_HEIGHT - 30
BOTTOM_LIMIT = 46
ROW_HEIGHT = 24
CELL_PADDING = 5

COLOR_BG = (0.043, 0.063, 0.094)
COLOR_TOPBAR = (0.063, 0.094, 0.153)
COLOR_CARD = (0.078, 0.114, 0.169)
COLOR_ACCENT = (0.306, 0.659, 0.961)
COLOR_ACCENT_SOFT = (0.184, 0.506, 0.816)
COLOR_TEXT = (0.902, 0.929, 0.969)
COLOR_MUTED = (0.604, 0.659, 0.737)
COLOR_BORDER = (0.157, 0.212, 0.302)


def build_csv_bytes(report: dict) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(report["columns"])
    for row in report["rows"]:
        writer.writerow([row.get(column, "") for column in report["columns"]])
    return buffer.getvalue().encode("utf-8-sig")


def build_pdf_bytes(report: dict) -> bytes:
    objects = []

    def add_object(content: str | bytes) -> int:
        objects.append(content)
        return len(objects)

    def escape_pdf_text(value: str) -> str:
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .replace("\r", " ")
            .replace("\n", " ")
        )

    def draw_rect(x, y, width, height, color, stroke_color=None) -> list[str]:
        commands = [f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg"]
        if stroke_color:
            commands.append(f"{stroke_color[0]:.3f} {stroke_color[1]:.3f} {stroke_color[2]:.3f} RG")
            commands.append(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re B")
        else:
            commands.append(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re f")
        return commands

    def draw_text(x, y, text, size=11, color=COLOR_TEXT, font="F1") -> str:
        return (
            "BT "
            f"/{font} {size} Tf "
            f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm "
            f"({escape_pdf_text(text)}) Tj ET"
        )

    def truncate_text(text: str, width: float, size: int) -> str:
        max_chars = max(int(width / max(size * 0.52, 1)), 1)
        text = str(text)
        if len(text) <= max_chars:
            return text
        return text[: max(max_chars - 1, 1)] + "..."

    def metric_value(metric) -> str:
        return str(metric.get("value", "-"))

    columns = report["columns"]
    rows = report["rows"]
    metrics = report.get("metrics", [])
    table_width = PAGE_WIDTH - (MARGIN_X * 2)
    col_width = table_width / max(len(columns), 1)
    rows_per_page = 14
    row_chunks = [rows[index : index + rows_per_page] for index in range(0, len(rows), rows_per_page)] or [[]]

    font_regular_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    page_ids = []

    for page_index, row_chunk in enumerate(row_chunks):
        commands = []
        commands.extend(draw_rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, COLOR_BG))
        commands.extend(draw_rect(0, PAGE_HEIGHT - 88, PAGE_WIDTH, 88, COLOR_TOPBAR))
        commands.extend(draw_rect(MARGIN_X, PAGE_HEIGHT - 84, 138, 30, COLOR_ACCENT))
        commands.append(draw_text(MARGIN_X + 16, PAGE_HEIGHT - 64, "FPS Arena", size=16, color=(1, 1, 1), font="F2"))
        commands.append(draw_text(MARGIN_X, PAGE_HEIGHT - 114, report["title"], size=22, color=COLOR_TEXT, font="F2"))
        commands.append(draw_text(MARGIN_X, PAGE_HEIGHT - 148, "Relatorio completo exportado do sistema", size=10, color=COLOR_MUTED))

        y = PAGE_HEIGHT - 220
        if page_index == 0 and metrics:
            metric_width = (table_width - 18) / min(len(metrics), 3)
            for metric_index, metric in enumerate(metrics[:3]):
                x = MARGIN_X + metric_index * (metric_width + 9)
                commands.extend(draw_rect(x, y, metric_width, 52, COLOR_CARD, stroke_color=COLOR_BORDER))
                commands.append(draw_text(x + 12, y + 33, metric.get("label", "-"), size=9, color=COLOR_MUTED))
                commands.append(draw_text(x + 12, y + 14, truncate_text(metric_value(metric), metric_width - 24, 15), size=15, color=COLOR_TEXT, font="F2"))
            y -= 72
        else:
            y -= 10

        commands.extend(draw_rect(MARGIN_X, y, table_width, ROW_HEIGHT, COLOR_ACCENT_SOFT))
        for index, column in enumerate(columns):
            x = MARGIN_X + index * col_width
            commands.append(draw_text(x + CELL_PADDING, y + 8, truncate_text(column, col_width - 10, 9), size=9, color=COLOR_TEXT, font="F2"))

        current_y = y - ROW_HEIGHT
        if row_chunk:
            for row_index, row in enumerate(row_chunk):
                fill = COLOR_CARD if row_index % 2 == 0 else COLOR_TOPBAR
                commands.extend(draw_rect(MARGIN_X, current_y, table_width, ROW_HEIGHT, fill, stroke_color=COLOR_BORDER))
                for col_index, column in enumerate(columns):
                    x = MARGIN_X + col_index * col_width
                    value = truncate_text(row.get(column, ""), col_width - 10, 8)
                    commands.append(draw_text(x + CELL_PADDING, current_y + 8, value, size=8, color=COLOR_TEXT))
                current_y -= ROW_HEIGHT
        else:
            commands.extend(draw_rect(MARGIN_X, current_y, table_width, 48, COLOR_CARD, stroke_color=COLOR_BORDER))
            commands.append(draw_text(MARGIN_X + 12, current_y + 18, "Nenhum dado encontrado para este relatorio.", size=10, color=COLOR_MUTED))
            current_y -= 48

        footer_y = max(current_y - 18, BOTTOM_LIMIT)
        commands.append(draw_text(MARGIN_X, footer_y, f"Pagina {page_index + 1} de {len(row_chunks)}", size=9, color=COLOR_MUTED))

        stream = "\n".join(commands).encode("latin-1", errors="replace")
        content_id = add_object(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
        page_ids.append(
            add_object(
                f"<< /Type /Page /Parent PAGES_ID 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            )
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_id = add_object(f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>")
    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    for page_id in page_ids:
        objects[page_id - 1] = str(objects[page_id - 1]).replace("PAGES_ID", str(pages_id))

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        if isinstance(obj, bytes):
            pdf.extend(obj)
        else:
            pdf.extend(obj.encode("latin-1", errors="replace"))
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("ascii")
    )
    return bytes(pdf)
