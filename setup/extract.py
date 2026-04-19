#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trích xuất nội dung luận văn từ PDF (chương 1-5, tóm tắt) và xuất ra file Markdown.
Tích hợp: Dọn rác, nối dòng đứt đoạn, chém đứt đuôi TLTK/Phụ lục, GẮN THẺ HEADING CHUẨN VÀ THỐNG KÊ NGÀNH.
"""

import fitz  # pip install pymupdf
import re
import pathlib
import sys
import argparse
from collections import defaultdict

# =======================================================
# 🔥 NEW: HÀM TRÍCH XUẤT TÊN CHUYÊN NGÀNH
# =======================================================
def extract_major_from_text(text: str) -> str:
    """
    Trích xuất tên chuyên ngành từ văn bản thô của trang bìa.
    """
    lines = text.split('\n')
    for line in lines:
        line_lower = line.lower()
        if "ngành" in line_lower and "mã" not in line_lower:
            match = re.search(r"ngành\s*[:\-]?\s*(.+)", line, re.IGNORECASE)
            if match:
                major = match.group(1).strip()
                # Làm sạch các ký tự điều khiển ẩn và ký tự lạ
                major_clean = re.sub(r'[\x00-\x1f\x7f]', ' ', major)
                major_clean = re.sub(r'[\\/*?:"<>|\n\r]', '', major_clean)
                major_clean = re.sub(r'\s+', ' ', major_clean).strip()
                return major_clean.title()
    return "Khác (Không xác định)"


def clean_noise(text: str) -> str:
    if not text:
        return ""
    
    # ===== XÓA ký tự rác =====
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)

    # ===== XÓA header trường =====
    text = re.sub(r'(?i)BỘ GIÁO DỤC VÀ ĐÀO TẠO\s*TRƯỜNG ĐẠI HỌC CẦN THƠ', '', text)
    text = re.sub(r'(?i)LUẬN VĂN THẠC SĨ NGÀNH.*', '', text)

    # ===== XÓA số trang =====
    text = re.sub(r'(?m)^\s*\d+\s*$', '', text)

    # =========================
    # 🔥 XÓA TÊN BẢNG / HÌNH (caption)
    # =========================
    text = re.sub(
        r'(?mi)^\s*(Bảng|Hình|Biểu đồ|Sơ đồ)\s+\d+[\.\d]*\s*[:\-\.]?.*$',
        '',
        text
    )

    # =========================
    # 🔥 XÓA DỮ LIỆU BẢNG
    # =========================
    lines = text.splitlines()
    clean_lines = []

    for line in lines:
        line_strip = line.strip()

        if not line_strip:
            clean_lines.append("")
            continue

        num_count = len(re.findall(r'\d', line_strip))
        char_count = len(re.findall(r'[a-zA-ZÀ-ỹ]', line_strip))

        # nếu dòng có nhiều số hơn chữ → bỏ
        if num_count > char_count * 2:
            continue

        # dòng toàn số/ký tự bảng → bỏ
        if re.match(r'^[\s\d\.,%-]+$', line_strip):
            continue

        clean_lines.append(line)

    text = "\n".join(clean_lines)

    # =========================
    # 🔥 XÓA block bảng nhiều dòng liên tiếp
    # =========================
    text = re.sub(r'(\n[\s\d\.,%-]+\n){2,}', '\n', text)

    # ===== Chuẩn hóa =====
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def fix_broken_lines(text: str) -> str:
    if not text:
        return ""
    
    lines = [line.strip() for line in text.splitlines()]
    result = []
    
    def is_heading(line: str) -> bool:
        if re.match(r'(?i)^\s*(\d+(\.\d+)*\.?\s+|(CHƯƠNG|PHẦN|BẢNG|HÌNH)\s+[IVX\d]+)', line):
            return True
        if re.search(r'(?i)^(DANH MỤC )?TÀI LIỆU THAM KHẢO', line.strip()):
            return True
        if re.search(r'(?i)^PHỤ LỤC', line.strip()):
            return True
        return False
    
    def is_sentence_end(line: str) -> bool:
        return bool(re.search(r'[.!?:;]\s*$', line))
        
    def is_list_item(line: str) -> bool:
        return bool(re.match(r'^\s*([\-\+\*]|\[\d+\]|\d+\.)\s+', line))
    
    for line in lines:
        if not line:
            result.append("") 
            continue
            
        first_char_match = re.search(r'[a-zA-ZÀ-ỹ]', line)
        is_lower = first_char_match and first_char_match.group(0).islower()
        
        prev_idx = len(result) - 1
        while prev_idx >= 0 and result[prev_idx] == "":
            prev_idx -= 1
        
        prev_line = result[prev_idx] if prev_idx >= 0 else ""
        
        if is_lower and prev_idx >= 0:
            result = result[:prev_idx + 1] 
            result[-1] = result[-1] + " " + line
        elif (is_heading(line) or 
              is_list_item(line) or
              (is_sentence_end(prev_line) and line and line[0].isupper()) or
              is_heading(prev_line)):
            result.append(line)
        else:
            if prev_idx >= 0:
                result = result[:prev_idx + 1]
                result[-1] = result[-1] + " " + line
            else:
                result.append(line)
                
    final_text = "\n".join(result)
    return re.sub(r'\n{3,}', '\n\n', final_text)

def format_markdown_headings(text: str) -> str:
    lines = text.splitlines()
    formatted_lines = []
    
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            formatted_lines.append(line)
            continue
            
        # 1. Nhận diện Header 1 (CHƯƠNG 1, PHẦN 1)
        if re.match(r'(?i)^(CHƯƠNG|PHẦN)\s+[IVX\d]+\b', line_strip):
            clean_line = re.sub(r'^#+\s*', '', line_strip)
            formatted_lines.append(f"# {clean_line}")
            continue
            
        # 2. Nhận diện Header 2, 3, 4...
        match = re.match(r'^(\d+(?:\.\d+)+)\.?\s+(.+)$', line_strip)
        if match:
            number_part = match.group(1)
            level = len(number_part.split('.'))
            
            if 1 < level <= 4:
                prefix = "#" * level
                clean_line = re.sub(r'^#+\s*', '', line_strip)
                formatted_lines.append(f"{prefix} {clean_line}")
                continue
                
        formatted_lines.append(line)
        
    return "\n".join(formatted_lines)


def extract_core_sections(text: str) -> tuple:
    tom_tat, noi_dung = "", ""
    
    # ===== FIX TÓM TẮT =====
    match_tt = re.search(r'(?i)\bTÓM\s*TẮT\b', text)
    
    if match_tt:
        start_tt = match_tt.end()
        end_pattern = r'(?i)\b(ABSTRACT|ASBTRACT|CHƯƠNG\s+[1I]|MỤC LỤC)\b'
        match_end_tt = re.search(end_pattern, text[start_tt:])

        if match_end_tt:
            tom_tat = text[start_tt : start_tt + match_end_tt.start()]
        else:
            tom_tat = text[start_tt:start_tt + 3000]
    
    # ===== GIỮ NGUYÊN LOGIC NỘI DUNG =====
    start_pattern = r'(?mi)^\s*(CHƯƠNG\s+[1I]|1\.\s*MỞ ĐẦU|MỞ ĐẦU|INTRODUCTION)\s*$'
    match_nd = re.search(start_pattern, text)
    
    if match_nd:
        start_nd = match_nd.start()
        
        strict_end_pattern = r'(?im)^\s*(?:[\dIVX]+\.?\s*|CHƯƠNG\s+[IVX\d]+\.?\s*)?(?:DANH\s+MỤC\s+)?(TÀI\s+LIỆU\s+THAM\s+KHẢO|PHỤ\s+LỤC)'
        match_end = re.search(strict_end_pattern, text[start_nd:])
        
        if not match_end:
            loose_end_pattern = r'(TÀI\s+LIỆU\s+THAM\s+KHẢO|PHỤ\s+LỤC\s+[1IVX])'
            match_end = re.search(loose_end_pattern, text[start_nd:])
        
        if match_end:
            noi_dung = text[start_nd : start_nd + match_end.start()]
        else:
            noi_dung = text[start_nd:]
            
    return tom_tat.strip(), noi_dung.strip()

def process_thesis_batch(input_folder: pathlib.Path, output_folder: pathlib.Path, no_overwrite: bool = False):
    output_folder.mkdir(parents=True, exist_ok=True)
    pdf_files = list(input_folder.glob("*.pdf"))
    total_files = len(pdf_files)
    
    if total_files == 0:
        print(f"⚠️ Thư mục '{input_folder}' không có file PDF nào.")
        return
        
    print(f"🚀 Bắt đầu xử lý {total_files} file PDF...\n" + "="*50)
    success_count = 0
    
    # Dictionary dùng để đếm số lượng file thành công theo tên chuyên ngành
    major_counts = defaultdict(int)
    
    for idx, pdf_path in enumerate(pdf_files, 1):
        out_file = output_folder / f"{pdf_path.stem}.md"

        if no_overwrite and out_file.exists():
            print(f"[{idx}/{total_files}] ⏭️ Bỏ qua (đã tồn tại): {pdf_path.name}")
            continue

        try:
            with fitz.open(pdf_path) as doc:
                # Đọc text thô từ trang bìa (2 trang đầu)
                cover_pages = [doc[i].get_text("text", sort=True) for i in range(min(2, len(doc)))]
                raw_cover_text = "\n".join(cover_pages)
                
                # Trích xuất chuyên ngành TRƯỚC KHI dọn dẹp bằng clean_noise
                major_name = extract_major_from_text(raw_cover_text)
                
                # Tiến hành dọn dẹp bìa
                cover_text = clean_noise(raw_cover_text)
                cover_text = fix_broken_lines(cover_text)

                # Xử lý nội dung chính
                body_pages = [doc[i].get_text("text", sort=True) for i in range(2, len(doc))]
                body_text = "\n".join(body_pages)

                body_text = clean_noise(body_text)
                body_text = fix_broken_lines(body_text)
                tom_tat, noi_dung = extract_core_sections(body_text)
                
                # Chạy hàm format heading
                noi_dung = format_markdown_headings(noi_dung)

            if not noi_dung:
                if out_file.exists():
                    out_file.unlink()
                print(f"[{idx}/{total_files}] ❌ Lỗi (không tìm thấy Chương 1): {pdf_path.name}")
                continue

            final_markdown = f"# THÔNG TIN BÌA\n- **Chuyên ngành:** {major_name}\n\n{cover_text}\n\n"

            if tom_tat:
                final_markdown += f"# TÓM TẮT\n{tom_tat}\n\n"

            final_markdown += f"# NỘI DUNG CHÍNH\n{noi_dung}\n"

            out_file.write_text(final_markdown, encoding="utf-8")
            
            # Chỉ cộng biến đếm khi xuất file thành công
            success_count += 1
            major_counts[major_name] += 1

            print(f"[{idx}/{total_files}] ✅ Thành công: {pdf_path.name} | Ngành: {major_name}")

        except Exception as e:
            print(f"[{idx}/{total_files}] ❌ Lỗi {pdf_path.name}: {e}")
            
    # =======================================================
    # IN THỐNG KÊ KẾT QUẢ KHI KẾT THÚC VÒNG LẶP
    # =======================================================
    print("="*50)
    print(f"🎉 Hoàn tất! Đã xử lý thành công {success_count}/{total_files} file.")
    print("\n📊 THỐNG KÊ SỐ LƯỢNG LUẬN VĂN THEO CHUYÊN NGÀNH:")
    
    # Sắp xếp theo số lượng file giảm dần
    sorted_majors = sorted(major_counts.items(), key=lambda item: item[1], reverse=True)
    
    for major, count in sorted_majors:
        print(f" 🔹 {major}: {count} file")
    print("\n")

def main():
    parser = argparse.ArgumentParser(
        description="Trích xuất luận văn từ PDF sang Markdown chuẩn hóa Header và Thống kê ngành."
    )
    parser.add_argument("-i", "--input", default="input_folder", help="Thư mục chứa PDF")
    parser.add_argument("-o", "--output", default="output_md", help="Thư mục xuất Markdown")
    parser.add_argument("--no-overwrite", action="store_true", help="Không ghi đè file đã có")
    
    args = parser.parse_args()
    input_dir = pathlib.Path(args.input)
    output_dir = pathlib.Path(args.output)
    
    if not input_dir.exists():
        input_dir.mkdir(parents=True)
        print(f"⚠️ Đã tạo thư mục '{input_dir}'. Vui lòng copy PDF vào và chạy lại lệnh.")
        sys.exit(0)
        
    process_thesis_batch(input_dir, output_dir, args.no_overwrite)

if __name__ == "__main__":
    main()