"""信号电缆业务规则：状态流转、字段校验、表格导入合并与筛选口径都收在这里。"""
from __future__ import annotations

import csv
import io
from typing import Any

from app.store import store

MODULE = "cable"
# 表格列顺序即台账口径：表头必须与它逐列一致，顺序不符整批退回。
COLUMNS = ["电缆编号", "起止站点", "电缆芯数", "绝缘电阻", "对地电压", "敷设方式", "接头数量", "电缆状态"]
REQUIRED_FIELDS = ["电缆编号", "起止站点", "电缆芯数"]
# 这四列是数值口径：导入时解析成数字，保证导出再导入逐值类型一致（不会把 10 变成 "10"）。
NUMERIC_FIELDS = ["电缆芯数", "绝缘电阻", "对地电压", "接头数量"]
STATUS_ORDER = ["绝缘良好", "绝缘下降", "接地报警", "已更换"]
ACTION_RULES = {"登记报警": "绝缘下降", "查找接地点": "接地报警", "办理更换": "已更换"}
NEGATIVE_ACTIONS = []


class BatchRejected(Exception):
    """整批导入被退回时抛出：携带给用户看的原因，此时一条数据都不能落库。"""


def _parse_number(value: str) -> int | float | None:
    """解析表格里的数值单元格：整数优先，解析不了返回 None（绝不拿 0 顶替）。"""
    text = value.replace(",", "").strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return None


def _sync_status(row: dict[str, Any], status: str) -> None:
    """把内部 status 与台账列「电缆状态」同步，保证列表页和详情页口径一致。"""
    row["status"] = status
    row["电缆状态"] = status
    row["pending"] = status != STATUS_ORDER[-1]
    row["abnormal"] = status in ("绝缘下降", "接地报警")


def _present(row: dict[str, Any]) -> dict[str, Any]:
    """对外展示口径：补齐全部台账列，并让「电缆状态」始终跟随内部 status。"""
    status = row.get("status")
    if status not in STATUS_ORDER:
        status = row.get("电缆状态") if row.get("电缆状态") in STATUS_ORDER else STATUS_ORDER[0]
    if row.get("status") != status or row.get("电缆状态") != status:
        _sync_status(row, status)
    item: dict[str, Any] = {"id": row.get("id")}
    for column in COLUMNS:
        item[column] = row.get(column)
    return item


class CableService:
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
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [_present(row) for row in rows[start:start + size]], total

    def export_entries(
        self, *, keyword: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        """按当前筛选条件导出全量；分页对导出无意义，一次取完。"""
        rows, _ = self.list_entries(keyword=keyword, status=status, page=1, size=10**9)
        return rows

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return _present(row) if row is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for column in COLUMNS:
            entry[column] = values.get(column)
        _sync_status(entry, STATUS_ORDER[0])
        rows.append(entry)
        return _present(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"信号电缆 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于信号电缆可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        _sync_status(entry, target)
        return _present(entry), f"信号电缆已{action}"

    # ------------------------------------------------------------------
    # 表格导入
    # ------------------------------------------------------------------
    def import_rows(self, text: str) -> dict[str, Any]:
        """按电缆编号合并导入整份表格。

        规则：
        - 表头必须与 COLUMNS 逐列同名同序，否则整批退回，一条不写；
        - 整行为空、电缆编号为空，或必填列（电缆编号/起止站点/电缆芯数）有空值的行
          整行跳过，行号在结果里列出；
        - 可空列（如绝缘电阻）留空时保留为空（None），绝不用 0 之类的默认值顶替；
        - 同一文件内或库中已存在相同电缆编号时合并更新而不是新增；
        - 先在副本上完成全部解析与合并，最后一次性替换，中途出错不留半份数据。
        """
        reader = csv.reader(io.StringIO(text, newline=""))
        table = list(reader)
        if not table or not any(str(cell).strip() for cell in table[0]):
            raise BatchRejected("文件为空或缺少表头，整批未导入，请补充表头行后重试")

        headers = [str(cell).strip() for cell in table[0]]
        if headers != COLUMNS:
            raise BatchRejected(
                "表头列顺序与台账字段不符，整批退回。"
                f"标准列顺序：{'、'.join(COLUMNS)}"
            )

        parsed: list[tuple[int, dict[str, Any]]] = []
        skipped_rows: list[int] = []
        for offset, raw in enumerate(table[1:], start=2):
            values = [str(cell).strip() for cell in raw]
            if not any(values):
                # 空行：表格里常见的分隔空行，不参与导入
                skipped_rows.append(offset)
                continue
            if len(values) != len(COLUMNS):
                raise BatchRejected(f"第 {offset} 行列数与表头不一致（应为 {len(COLUMNS)} 列），整批退回")
            record: dict[str, Any] = {}
            for column, value in zip(COLUMNS, values):
                if value == "":
                    record[column] = None
                elif column in NUMERIC_FIELDS:
                    number = _parse_number(value)
                    if number is None:
                        raise BatchRejected(f"第 {offset} 行「{column}」的值「{value}」不是数字，整批退回")
                    record[column] = number
                else:
                    record[column] = value
            if not record["电缆编号"]:
                # 合并键为空无法归属，整行跳过
                skipped_rows.append(offset)
                continue
            cable_status = record["电缆状态"]
            if cable_status is not None and cable_status not in STATUS_ORDER:
                raise BatchRejected(
                    f"第 {offset} 行电缆状态「{cable_status}」不在允许范围"
                    f"（{'、'.join(STATUS_ORDER)}），整批退回"
                )
            if any(record[field] is None for field in REQUIRED_FIELDS):
                # 必填列（电缆编号/起止站点/电缆芯数）有空值：整行跳过，不塞默认值
                skipped_rows.append(offset)
                continue
            parsed.append((offset, record))

        # 以下在副本上完成合并，全部成功后才替换仓库，保证原子性
        current = store.rows(MODULE)
        merged = [dict(row) for row in current]
        index_by_code = {
            str(row.get("电缆编号") or "").strip(): index
            for index, row in enumerate(merged)
            if str(row.get("电缆编号") or "").strip()
        }
        next_id = max((int(row.get("id", 0)) for row in merged), default=0) + 1
        created = 0
        updated = 0

        for _row_no, record in parsed:
            code = record["电缆编号"]
            if code in index_by_code:
                target = merged[index_by_code[code]]
                for column in COLUMNS:
                    target[column] = record[column]
                # 状态是流程字段：表格留空时保留既有状态，不让导入把它打回初始值
                status = record["电缆状态"] or target.get("status")
                if status not in STATUS_ORDER:
                    status = STATUS_ORDER[0]
                _sync_status(target, status)
                updated += 1
            else:
                entry: dict[str, Any] = {"id": next_id}
                next_id += 1
                entry.update(record)
                _sync_status(entry, record["电缆状态"] or STATUS_ORDER[0])
                index_by_code[code] = len(merged)
                merged.append(entry)
                created += 1

        store.replace(MODULE, merged)
        return {
            "total": len(parsed),
            "created": created,
            "updated": updated,
            "skipped_rows": skipped_rows,
        }
