"""信号电缆接口：维护信号电缆，覆盖登记报警、查找接地点、办理更换、表格导入导出。"""
from __future__ import annotations

import csv
import io
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.cable import COLUMNS, BatchRejected, CableService

router = APIRouter(prefix="/api/cable", tags=["信号电缆"])

service = CableService()

STATUSES = ["绝缘良好", "绝缘下降", "接地报警", "已更换"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按电缆编号检索"),
    status: str | None = Query(default=None, description="绝缘良好、绝缘下降、接地报警、已更换"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按电缆编号与状态过滤信号电缆列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


# 注意：/import、/export 必须声明在 /{entry_id} 之前，否则会被当成 entry_id 截获。
@router.post("/import", response_model=ActionResult)
async def import_entries(request: Request) -> ActionResult:
    """按电缆编号合并导入 CSV 台账：表头顺序不符或内容非法时整批退回，一条不落库。"""
    text = (await request.body()).decode("utf-8-sig")
    try:
        result = service.import_rows(text)
    except BatchRejected as exc:
        # 整批退回属于可预期的业务失败，用 200 + ok=False 让页面直接展示原因
        return ActionResult(ok=False, message=str(exc))
    skipped = result["skipped_rows"]
    skipped_note = f"，跳过空行/无编号行：第 {'、'.join(str(n) for n in skipped)} 行" if skipped else ""
    message = (
        f"导入完成：新增 {result['created']} 条，按电缆编号合并更新 {result['updated']} 条"
        f"，共处理 {result['total']} 行{skipped_note}"
    )
    return ActionResult(ok=True, message=message, entry=result)


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按电缆编号检索，与列表页筛选一致"),
    status: str | None = Query(default=None, description="绝缘良好、绝缘下降、接地报警、已更换"),
) -> Response:
    """导出当前筛选条件下的信号电缆清单，字段与台账列一致（含对地电压、电缆状态）。"""
    items = service.export_entries(keyword=keyword, status=status)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    for item in items:
        writer.writerow(["" if item.get(column) is None else item.get(column) for column in COLUMNS])
    # utf-8-sig（BOM）保证 Excel 直接打开不乱码
    payload = "\ufeff" + buffer.getvalue()
    filename = quote("信号电缆清单.csv")
    return Response(
        content=payload.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条信号电缆明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"信号电缆 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条信号电缆，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="信号电缆已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条信号电缆执行登记报警、查找接地点、办理更换；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
