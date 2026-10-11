"""
=============================================================================
 ROS Attendance Bot — Attendance Manager
 Handles all attendance record logic: marking, saving, Excel export.
=============================================================================
"""

import os
import csv
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference

import config

log = logging.getLogger(__name__)


class AttendanceManager:
    """
    Thread-safe attendance tracking.  Stores records in-memory and
    persists to CSV + Excel after each session.
    """

    def __init__(self):
        Path(config.ATTENDANCE_DIR).mkdir(parents=True, exist_ok=True)
        self._records: dict[str, dict] = {}   # student_id → record dict
        self._session_date = date.today().isoformat()
        self._csv_path   = Path(config.ATTENDANCE_DIR) / f"attendance_{self._session_date}.csv"
        self._excel_path = Path(config.ATTENDANCE_DIR) / f"attendance_{self._session_date}.xlsx"

        # Load today's existing records (if app restarted)
        self._load_existing_csv()

    # ── Public API ────────────────────────────────────────────────────────────

    def mark(self, student_id: str, name: str) -> bool:
        """
        Mark a student as present.
        Returns True if this was a NEW mark (not a cooldown duplicate).
        """
        now = datetime.now()

        if student_id in self._records:
            last = self._records[student_id]["last_seen"]
            delta = (now - last).total_seconds()
            if delta < config.COOLDOWN_SECONDS:
                return False  # still in cooldown

        self._records[student_id] = {
            "id":        student_id,
            "name":      name,
            "date":      self._session_date,
            "time":      now.strftime("%H:%M:%S"),
            "status":    "Present",
            "last_seen": now,
        }

        log.info("✅ Marked present: %s (%s) at %s", name, student_id, now.strftime("%H:%M:%S"))
        self._save_csv()
        return True

    def get_records(self) -> list[dict]:
        """Return sorted list of attendance records (latest first)."""
        return sorted(
            self._records.values(),
            key=lambda r: r["time"],
            reverse=True
        )

    def get_count(self) -> int:
        return len(self._records)

    def export_excel(self, path: Optional[str] = None) -> str:
        """
        Export today's attendance to a styled Excel workbook.
        Returns the saved file path.
        """
        out_path = path or str(self._excel_path)
        records  = self.get_records()

        wb  = openpyxl.Workbook()
        ws  = wb.active
        ws.title = config.ATTENDANCE_SHEET_NAME

        # ── Colors ───────────────────────────────────────────────────────────
        C_HEADER   = "1A1F2E"
        C_ACCENT   = "3A86FF"
        C_PRESENT  = "1E6B4A"
        C_ALT_ROW  = "1E2433"
        C_BORDER   = "2E3446"
        C_TEXT_W   = "FFFFFF"
        C_TEXT_G   = "A0B0C8"

        thin  = Side(border_style="thin",  color=C_BORDER)
        thick = Side(border_style="medium", color=C_ACCENT)
        full_border  = Border(left=thin, right=thin, top=thin, bottom=thin)
        header_border = Border(bottom=Side(border_style="medium", color=C_ACCENT))

        # ── Title Row ─────────────────────────────────────────────────────────
        ws.merge_cells("A1:E1")
        title_cell = ws["A1"]
        title_cell.value = f"🤖  ROS Attendance Report — {self._session_date}"
        title_cell.font      = Font(bold=True, size=16, color=C_TEXT_W, name="Calibri")
        title_cell.fill      = PatternFill("solid", fgColor=C_HEADER)
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 36

        # ── Subtitle ─────────────────────────────────────────────────────────
        ws.merge_cells("A2:E2")
        sub = ws["A2"]
        sub.value      = f"Total Present: {len(records)}    |    Session: {self._session_date}"
        sub.font       = Font(size=11, color=C_TEXT_G, name="Calibri")
        sub.fill       = PatternFill("solid", fgColor=C_HEADER)
        sub.alignment  = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[2].height = 22

        # ── Column Headers ────────────────────────────────────────────────────
        headers = ["#", "Student ID", "Name", "Date", "Time", "Status"]
        col_widths = [5, 14, 26, 14, 12, 12]

        for col_idx, (h, w) in enumerate(zip(headers, col_widths), start=1):
            cell = ws.cell(row=3, column=col_idx, value=h)
            cell.font      = Font(bold=True, size=11, color=C_TEXT_W, name="Calibri")
            cell.fill      = PatternFill("solid", fgColor=C_ACCENT)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border    = header_border
            ws.column_dimensions[get_column_letter(col_idx)].width = w

        ws.row_dimensions[3].height = 22

        # ── Data Rows ─────────────────────────────────────────────────────────
        for row_num, rec in enumerate(records, start=1):
            excel_row = row_num + 3
            row_fill  = PatternFill("solid", fgColor=C_ALT_ROW if row_num % 2 == 0 else C_HEADER)

            values = [
                row_num,
                rec["id"],
                rec["name"],
                rec["date"],
                rec["time"],
                rec["status"],
            ]

            for col_idx, val in enumerate(values, start=1):
                cell = ws.cell(row=excel_row, column=col_idx, value=val)
                cell.fill      = row_fill
                cell.border    = full_border
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font      = Font(size=10, color=C_TEXT_W, name="Calibri")

                # Colour the Status column
                if col_idx == 6 and val == "Present":
                    cell.fill = PatternFill("solid", fgColor=C_PRESENT)
                    cell.font = Font(bold=True, size=10, color="A0FFC0", name="Calibri")

            ws.row_dimensions[excel_row].height = 20

        # ── Summary Sheet ─────────────────────────────────────────────────────
        ws2 = wb.create_sheet("Summary")
        ws2["A1"] = "Metric"
        ws2["B1"] = "Value"
        ws2["A2"] = "Total Present"
        ws2["B2"] = len(records)
        ws2["A3"] = "Session Date"
        ws2["B3"] = self._session_date
        ws2["A4"] = "Export Time"
        ws2["B4"] = datetime.now().strftime("%H:%M:%S")

        for cell in [ws2["A1"], ws2["B1"]]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=C_ACCENT)

        # ── Freeze panes & zoom ───────────────────────────────────────────────
        ws.freeze_panes = "A4"
        ws.sheet_view.zoomScale = 110

        wb.save(out_path)
        log.info("📊 Excel saved → %s", out_path)
        return out_path

    # ── Internal ──────────────────────────────────────────────────────────────

    def _save_csv(self):
        """Persist current records to CSV (incremental backup)."""
        with open(self._csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "name", "date", "time", "status"])
            writer.writeheader()
            for rec in self.get_records():
                writer.writerow({k: rec[k] for k in ["id", "name", "date", "time", "status"]})

    def _load_existing_csv(self):
        """Load today's records from CSV if they exist (restart resilience)."""
        if not self._csv_path.exists():
            return
        with open(self._csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row["id"]
                self._records[sid] = {
                    **row,
                    "last_seen": datetime.strptime(
                        f"{row['date']} {row['time']}", "%Y-%m-%d %H:%M:%S"
                    ),
                }
        log.info("Loaded %d existing records from %s", len(self._records), self._csv_path)
