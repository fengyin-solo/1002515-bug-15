"""信号电缆业务规则：状态流转、字段校验、台账导入合并与导出口径都收在这里。"""
from __future__ import annotations

import csv
import io
from typing import Any

from app.store import store

MODULE = "cable"

# 台账列顺序即唯一约定：导入表头必须与之逐列一致，导出也按此顺序输出，
# 从根上避免“接头数量/敷设方式”这类按位置猜列导致的串位。
FIELD_ORDER = ["电缆编号", "起止站点", "电缆芯数", "绝缘电阻", "对地电压", "敷设方式", "接头数量", "电缆状态"]
REQUIRED_FIELDS = ["电缆编号", "起止站点", "电缆芯数"]
STATUS_ORDER = ["绝缘良好", "绝缘下降", "接地报警", "已更换"]
ACTION_RULES = {"登记报警": "绝缘下降", "查找接地点": "接地报警", "办理更换": "已更换"}
NEGATIVE_ACTIONS = []
DEFAULT_STATUS = STATUS_ORDER[0]


class HeaderMismatchError(ValueError):
    """表头列名或列顺序与台账模板不一致，整批退回时抛出。"""


class ImportResult:
    """一次导入的汇总结果；skipped 记录被跳过的表格行号（含表头，从 1 起）。"""

    def __init__(self) -> None:
        self.created = 0
        self.updated = 0
        self.skipped: list[int] = []
        self.skip_reasons: list[dict[str, Any]] = []

    @property
    def imported(self) -> int:
        return self.created + self.updated

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "created": self.created,
            "updated": self.updated,
            "imported": self.imported,
            "skipped_rows": self.skipped,
            "skipped": self.skip_reasons,
        }


class CableService:
    # ---- 列表 / 明细 -------------------------------------------------
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("电缆编号") or "")]
        if status:
            rows = [row for row in rows if self._status_of(row) == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._serialize(row) for row in rows[start:start + size]], total

    def export_rows(self, *, keyword: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        """按当前筛选条件导出，列顺序固定为 FIELD_ORDER，并按 id 排序保证多次导出逐条一致。"""
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("电缆编号") or "")]
        if status:
            rows = [row for row in rows if self._status_of(row) == status]
        rows = sorted(rows, key=lambda row: int(row.get("id", 0)))
        return [
            {field: ("" if row.get(field) is None else str(row.get(field))) for field in FIELD_ORDER}
            for row in rows
        ]

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._serialize(row) if row is not None else None

    # ---- 登记 / 状态流转 ---------------------------------------------
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in FIELD_ORDER:
            value = values.get(field)
            entry[field] = None if str(value or "").strip() == "" else str(value).strip()
        entry["电缆状态"] = entry["电缆状态"] or DEFAULT_STATUS
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._serialize(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"信号电缆 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于信号电缆可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        self._set_status(entry, target)
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._serialize(entry), f"信号电缆已{action}"

    # ---- 台账导入 -----------------------------------------------------
    def import_rows(self, content: str) -> dict[str, Any]:
        """按电缆编号合并导入整份台账。

        - 表头列名/顺序与 FIELD_ORDER 不一致：抛 HeaderMismatchError，整批退回，不落任何数据；
        - 必填字段为空（含整行空白）的行整行跳过，行号记入结果；
        - 绝缘电阻等非必填列保持空值，绝不补零；
        - 同编号电缆执行更新而不是新增，整批校验通过后一次性提交（原子提交）。
        """
        reader = csv.reader(io.StringIO(content))
        try:
            header = next(reader)
        except StopIteration:
            raise HeaderMismatchError("导入文件为空，请使用标准台账模板")
        header = [cell.strip() for cell in header]
        if header != FIELD_ORDER:
            raise HeaderMismatchError(
                "表头列名或顺序与模板不一致，整批未导入。"
                f"应为：{','.join(FIELD_ORDER)}；实际为：{','.join(header) or '（空）'}"
            )

        result = ImportResult()
        # 先在暂存区完成全部校验与归一化，任何一行有问题都不会污染现有数据。
        staged: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for raw in reader:
            row_no = reader.line_num
            # 缺列按空值补齐、多列直接判整批格式错误，避免静默错位。
            if len(raw) > len(FIELD_ORDER):
                raise HeaderMismatchError(
                    f"第 {row_no} 行列数多于表头（{len(raw)}/{len(FIELD_ORDER)}），整批未导入"
                )
            cells = [cell.strip() for cell in raw] + [""] * (len(FIELD_ORDER) - len(raw))
            record = {field: (cells[i] or None) for i, field in enumerate(FIELD_ORDER)}

            blank_required = [field for field in REQUIRED_FIELDS if not record.get(field)]
            if not any(cells):
                result.skipped.append(row_no)
                result.skip_reasons.append({"row": row_no, "reason": "整行为空"})
                continue
            if blank_required:
                result.skipped.append(row_no)
                result.skip_reasons.append(
                    {"row": row_no, "reason": f"必填字段为空：{'、'.join(blank_required)}"}
                )
                continue
            status = record.get("电缆状态")
            if status is not None and status not in STATUS_ORDER:
                result.skipped.append(row_no)
                result.skip_reasons.append(
                    {"row": row_no, "reason": f"电缆状态「{status}」不在允许范围：{'、'.join(STATUS_ORDER)}"}
                )
                continue

            cable_no = record["电缆编号"]
            if cable_no not in staged:
                order.append(cable_no)
            staged[cable_no] = record  # 同文件内重复编号：后一行覆盖前一行

        # 全部校验通过后才与现有数据合并，单次整体替换保证“导入中断不留半份”。
        existing = {str(row.get("电缆编号")): dict(row) for row in store.rows(MODULE)}
        next_id = max((int(row.get("id", 0)) for row in existing.values()), default=0) + 1
        merged: list[dict[str, Any]] = []
        consumed: set[str] = set()

        # 先按原有 id 顺序保留未涉及的记录，再追加新电缆，保证导出顺序稳定。
        for old in sorted(store.rows(MODULE), key=lambda row: int(row.get("id", 0))):
            cable_no = str(old.get("电缆编号"))
            if cable_no in staged:
                consumed.add(cable_no)
                record = staged[cable_no]
                updated = self._merge_record(old, record)
                merged.append(updated)
                result.updated += 1
            else:
                merged.append(old)
        for cable_no in order:
            if cable_no in consumed:
                continue
            record = staged[cable_no]
            new_row: dict[str, Any] = {"id": next_id}
            next_id += 1
            new_row.update({field: record.get(field) for field in FIELD_ORDER})
            new_row["电缆状态"] = record.get("电缆状态") or DEFAULT_STATUS
            new_row["pending"] = new_row["电缆状态"] != STATUS_ORDER[-1]
            new_row["abnormal"] = False
            merged.append(new_row)
            result.created += 1

        store.replace_rows(MODULE, merged)
        return result.as_dict()

    # ---- 内部工具 -----------------------------------------------------
    def _merge_record(self, old: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
        """按编号命中已有电缆：覆盖台账字段，状态列为空时保留原状态，不新增记录。"""
        merged = dict(old)
        for field in FIELD_ORDER:
            merged[field] = record.get(field)
        # 状态列允许留空：留空表示维持原状态，而不是被清掉。
        if record.get("电缆状态") is None:
            merged["电缆状态"] = self._status_of(old) or DEFAULT_STATUS
        self._set_status(merged, merged["电缆状态"])
        merged["pending"] = merged["电缆状态"] != STATUS_ORDER[-1]
        merged["abnormal"] = bool(old.get("abnormal"))
        return merged

    def _serialize(self, row: dict[str, Any]) -> dict[str, Any]:
        """对外只暴露 id、台账列与流转标记；状态口径统一为「电缆状态」。"""
        item: dict[str, Any] = {"id": row.get("id")}
        for field in FIELD_ORDER:
            item[field] = row.get(field)
        item["电缆状态"] = self._status_of(row)
        item["pending"] = bool(row.get("pending"))
        item["abnormal"] = bool(row.get("abnormal"))
        return item

    @staticmethod
    def _status_of(row: dict[str, Any]) -> str:
        # 兼容历史数据里遗留的 status 键，但列表与详情读到的永远是同一个值。
        return str(row.get("电缆状态") or row.get("status") or "")

    def _set_status(self, row: dict[str, Any], status: str) -> None:
        row["电缆状态"] = status
        if "status" in row:
            row["status"] = status
