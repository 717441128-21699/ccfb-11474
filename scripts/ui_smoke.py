"""Playwright 前端端到端冒烟:五个模块渲染、原文高亮、审核、导出。

前置:服务已在本机 8000 端口运行(py -I scripts/run_server.py)
运行: py -I scripts/ui_smoke.py
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
buf = io.StringIO()
def log(msg):
    print(msg)
    buf.write(msg + "\n")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto(BASE, wait_until="networkidle")
    log(f"页面标题: {page.title()}")

    # 1. 说明书库
    page.wait_for_selector("#doc-tbody tr")
    doc_rows = page.locator("#doc-tbody tr").count()
    log(f"[说明书库] 表格行数: {doc_rows}")
    page.locator("#doc-tbody button").first.click()
    page.wait_for_selector("#drawer:not(.hidden)")
    drawer_text = page.locator("#drawer-body").inner_text()
    log(f"[说明书库] 原文抽屉打开,正文长度: {len(drawer_text)}")
    page.click("#drawer-close")

    # 2. 抽取明细
    page.click('.tab[data-view="items"]')
    page.wait_for_selector("#item-list .card")
    cards = page.locator("#item-list .card").count()
    log(f"[抽取明细] 卡片数: {cards}")
    # 打开高亮抽屉
    page.locator("#item-list .quote").first.click()
    page.wait_for_selector("#drawer-body .hl")
    hl = page.locator("#drawer-body .hl").first.inner_text()
    log(f"[抽取明细] 高亮原句: {hl[:40]}...")
    page.click("#drawer-close")

    # 3. 知识图谱
    page.click('.tab[data-view="graph"]')
    page.wait_for_selector("#graph-svg circle")
    node_n = page.locator("#graph-svg circle").count()
    edge_n = page.locator("#graph-svg line").count()
    log(f"[知识图谱] 节点 {node_n} 个,边 {edge_n} 条")

    # 4. 审核台
    page.click('.tab[data-view="review"]')
    page.wait_for_selector("#review-stats-box .stat-box")
    stats = page.locator("#review-stats-box .stat-box").count()
    log(f"[审核台] 统计卡片 {stats} 个")
    page.wait_for_selector("#review-list .card")
    before = page.locator("#review-list .card").count()
    with page.expect_response(lambda r: "/review/batch" in r.url) as resp_info:
        page.click("#approve-page")
    assert resp_info.value.ok
    page.wait_for_load_state("networkidle")
    log(f"[审核台] 本页批量通过完成(本页 {before} 条)")
    # 导出
    page.click("#export-btn")
    page.wait_for_selector("#export-result:not(.hidden)")
    export_txt = page.locator("#export-result").inner_text()
    log(f"[审核台] 导出结果: {export_txt.splitlines()[0]}")

    # 5. 冲突检查
    page.click('.tab[data-view="conflicts"]')
    page.wait_for_selector("#conflict-tbody tr")
    conf_rows = page.locator("#conflict-tbody tr").count()
    log(f"[冲突检查] 矛盾行数: {conf_rows}")
    badge = page.locator("#conflict-badge").inner_text()
    log(f"[冲突检查] 角标待处理数: {badge}")

    log(f"\n前端 JS 错误数: {len(errors)}")
    for e in errors[:5]:
        log("  JS ERROR: " + e)
    browser.close()

Path("data/processed/ui_smoke.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written")
