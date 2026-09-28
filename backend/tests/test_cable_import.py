"""信号电缆台账导入导出回归测试：直接验证 service 层的全部口径。

运行：backend/.venv/bin/python -m tests.test_cable_import
不依赖 pytest / fastapi，克隆即用。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.cable import FIELD_ORDER, HeaderMismatchError, CableService  # noqa: E402
from app.store import Store  # noqa: E402

HEADER = ",".join(FIELD_ORDER)
service = CableService()

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {name}" + (f" -> {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def fresh_service() -> CableService:
    # 用空仓库替换单例 store，保证每个用例互不影响。
    import app.services.cable as cable_mod

    cable_mod.store = Store.__new__(Store)
    cable_mod.store._tables = {}  # type: ignore[attr-defined]
    return CableService()


def csv_text(*rows: str) -> str:
    return "\n".join([HEADER, *rows]) + "\n"


# 1. 正常导入：列按表头名对位，接头数量/敷设方式不得串位
svc = fresh_service()
report = svc.import_rows(csv_text("CABL-0001,甲站—乙站,24,500,2,直埋,2,绝缘良好"))
entry = svc.get_entry(1)
check("导入后接头数量取接头数量列", entry["接头数量"] == "2", str(entry))
check("导入后敷设方式取敷设方式列", entry["敷设方式"] == "直埋", str(entry))
check("导入后绝缘电阻原样保留", entry["绝缘电阻"] == "500", str(entry))
check("导入结果计数 created=1", report["created"] == 1 and report["updated"] == 0, str(report))

# 2. 绝缘电阻为空：保持 None，不得塞成 0
svc.import_rows(csv_text("CABL-0002,乙站—丙站,30,,18,电缆槽,5,绝缘下降"))
entry2 = svc.get_entry(2)
check("绝缘电阻为空时保持空值不补零", entry2["绝缘电阻"] is None, str(entry2))
check("对地电压正常入库", entry2["对地电压"] == "18", str(entry2))

# 3. 空值整行跳过 + 整行空白跳过，结果给出行号（含表头，数据行从 2 起）
svc = fresh_service()
report = svc.import_rows(csv_text(
    "CABL-0001,甲站—乙站,24,500,2,直埋,2,绝缘良好",
    "CABL-0002,,30,,18,电缆槽,5,绝缘下降",   # 第 3 行：起止站点空 -> 跳过
    ",,, ,,,",                                # 第 4 行：整行空白 -> 跳过
    "CABL-0003,丙站—丁站,16,,,管道,8,接地报警",
))
check("两空行被跳过且行号正确", report["skipped_rows"] == [3, 4], str(report["skipped_rows"]))
check("有效行照常入库", report["imported"] == 2, str(report))
check("跳过原因有说明", {item["row"] for item in report["skipped"]} == {3, 4}, str(report["skipped"]))

# 4. 按电缆编号合并：重复导入同编号只更新不新增
svc = fresh_service()
svc.import_rows(csv_text("CABL-0001,甲站—乙站,24,500,2,直埋,2,绝缘良好"))
report = svc.import_rows(csv_text("CABL-0001,甲站—乙站(改),24,320,3,直埋,4,绝缘下降"))
check("重复编号导入走更新而非新增", report["updated"] == 1 and report["created"] == 0, str(report))
items, total = svc.list_entries(page=1, size=100)
check("合并后总数仍为 1", total == 1, f"total={total}")
only = items[0]
check("合并后字段被更新", only["起止站点"] == "甲站—乙站(改)" and only["接头数量"] == "4", str(only))
check("合并后状态被更新", only["电缆状态"] == "绝缘下降", str(only))

# 4b. 状态列留空时保留原状态
svc.import_rows(csv_text("CABL-0001,甲站—乙站,24,320,3,直埋,4,"))
only = svc.get_entry(1)
check("更新行状态留空时保留原状态", only["电缆状态"] == "绝缘下降", str(only))

# 5. 列顺序/列名不符：整批退回，旧数据不变
svc = fresh_service()
svc.import_rows(csv_text("CABL-0001,甲站—乙站,24,500,2,直埋,2,绝缘良好"))
bad_header = ",".join(
    ["电缆编号", "起止站点", "电缆芯数", "绝缘电阻", "对地电压", "接头数量", "敷设方式", "电缆状态"]
)
rejected = False
try:
    svc.import_rows(bad_header + "\nCABL-0009,错位站,24,500,2,9,直埋,绝缘良好\n")
except HeaderMismatchError:
    rejected = True
check("接头/敷设列顺序对调时整批退回", rejected)
items, total = svc.list_entries(page=1, size=100)
check("整批退回后旧数据原样保留", total == 1 and items[0]["电缆编号"] == "CABL-0001", str(items))

# 列名缺失同样退回
rejected = False
try:
    svc.import_rows("电缆编号,起止站点,电缆芯数,绝缘电阻,对地电压,敷设方式,接头数量\nX,站,1,1,1,直埋,1\n")
except HeaderMismatchError:
    rejected = True
check("表头缺列时整批退回", rejected)

# 6. 原子性：校验失败（中途列数过多）时不留下半份数据
svc = fresh_service()
svc.import_rows(csv_text("CABL-0001,甲站—乙站,24,500,2,直埋,2,绝缘良好"))
try:
    svc.import_rows(csv_text(
        "CABL-0009,新站,24,500,2,直埋,2,绝缘良好",
        "CABL-0010,坏站,24,500,2,直埋,2,绝缘良好,多出来一列",
    ))
    check("列数过多时应抛错退回", False)
except HeaderMismatchError:
    check("列数过多时应抛错退回", True)
_, total = svc.list_entries(page=1, size=100)
check("中途失败后仓库无半份新增（仍只有旧 1 条）", total == 1, f"total={total}")

# 7. 导出：含起止站点、对地电压、电缆状态；列顺序固定；按筛选条件
svc = fresh_service()
svc.import_rows(csv_text(
    "CABL-0001,甲站—乙站,24,500,2,直埋,2,绝缘良好",
    "CABL-0002,乙站—丙站,30,,18,电缆槽,5,绝缘下降",
))
all_rows = svc.export_rows()
check("导出列顺序即模板顺序", list(all_rows[0].keys()) == FIELD_ORDER, str(list(all_rows[0].keys())))
check("导出含起止站点", all_rows[0]["起止站点"] == "甲站—乙站")
check("导出含对地电压", all_rows[0]["对地电压"] == "2")
check("导出含电缆状态", all_rows[0]["电缆状态"] == "绝缘良好")
check("导出空绝缘电阻为空字符串而非 0", all_rows[1]["绝缘电阻"] == "", str(all_rows[1]))
filtered = svc.export_rows(status="绝缘下降")
check("导出按状态筛选", len(filtered) == 1 and filtered[0]["电缆编号"] == "CABL-0002", str(filtered))
keyworded = svc.export_rows(keyword="0001")
check("导出按编号关键字筛选", len(keyworded) == 1 and keyworded[0]["电缆编号"] == "CABL-0001")

# 8. 列表与详情状态口径一致（历史数据里只有 status 键时也能对上）
import app.services.cable as cable_mod
cable_mod.store._tables["cable"] = [{
    "id": 7,
    "status": "接地报警",
    "电缆编号": "CABL-0007",
    "起止站点": "旧站",
    "电缆芯数": "12",
    # 故意不写 电缆状态，模拟历史记录
}]
svc = CableService()
lst, _ = svc.list_entries(page=1, size=100)
detail = svc.get_entry(7)
list_row = next(row for row in lst if row["id"] == 7)
check("列表与详情的电缆状态一致（兼容旧 status 键）",
      list_row["电缆状态"] == detail["电缆状态"] == "接地报警",
      f"{list_row['电缆状态']} vs {detail['电缆状态']}")

# 9. 再导一次逐条一致：导出 -> 导入到空库 -> 再导出，两行文本除换行外完全一致
svc_a = fresh_service()
svc_a.import_rows(csv_text(
    "CABL-0001,甲站—乙站,24,500,2,直埋,2,绝缘良好",
    "CABL-0002,乙站—丙站,30,,18,电缆槽,5,绝缘下降",
    "CABL-0003,丙站—丁站,16,9,,管道,8,接地报警",
))
round1 = svc_a.export_rows()

svc_b = fresh_service()
import io
import csv as csv_mod
buf = io.StringIO()
writer = csv_mod.DictWriter(buf, fieldnames=FIELD_ORDER, lineterminator="\n")
writer.writeheader()
for row in round1:
    writer.writerow(row)
svc_b.import_rows(buf.getvalue())
round2 = svc_b.export_rows()
check("导出再导入后再次导出，逐条逐字段一致", round1 == round2,
      f"{round1} != {round2}")
# 且绝缘电阻的空值往返后仍是空
check("往返后空绝缘电阻依旧为空", round2[1]["绝缘电阻"] == "", str(round2[1]))

print()
if failures:
    print(f"{len(failures)} 项失败：{failures}")
    sys.exit(1)
print("全部用例通过")
