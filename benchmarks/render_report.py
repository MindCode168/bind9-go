#!/usr/bin/env python3
"""Render a truthful, offline BIND baseline and Go comparability report.

Usage: python3 benchmarks/render_report.py benchmark.json report.html
Only measured input is accepted. The report does not invent a Go DNS server.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import io
import itertools
import json
import math
import os
from pathlib import Path
import statistics
import tempfile
from collections import defaultdict

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "bind-go-matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


METRICS = [
    ("sent_qps", "实际发送 QPS", "queries/s", 0),
    ("qps", "完成 QPS", "queries/s", 0),
    ("latency_avg_ms", "平均延迟", "ms", 3),
    ("loss_percent", "未完成比例", "%", 3),
    ("server_cpu_percent", "服务进程 CPU", "%", 2),
    ("server_rss_peak_mib", "服务进程峰值 RSS", "MiB", 2),
]
WORKLOAD_NAMES = {"positive_a": "A 记录命中", "nxdomain": "NXDOMAIN"}
LABELS = {
    "tool": "负载工具", "tool_version": "工具版本", "duration_seconds": "单次正式压测时长（秒）",
    "warmup_seconds": "预热时长（秒）", "repetitions": "每组重复次数", "rates_qps": "目标速率（QPS）",
    "zone_records": "区域记录总数", "queried_a_records": "被查询的 A 记录数", "transports": "传输协议", "workloads": "工作负载",
    "client_threads": "客户端线程数", "client_sockets": "客户端连接数", "max_outstanding": "最大在途查询数",
    "server_cpus": "服务器 CPU 亲和性", "client_cpus": "客户端 CPU 亲和性",
    "timeout_seconds": "查询超时（秒）", "cpu_measurement": "CPU 测量方法", "rss_measurement": "RSS 测量方法",
    "os": "操作系统", "kernel": "内核", "architecture": "架构", "cpu": "CPU", "cpu_model": "CPU 型号",
    "logical_cpus": "逻辑 CPU 数", "memory": "内存", "memory_gib": "内存（GiB）", "hostname": "主机名",
    "container": "容器", "go_version": "Go 版本", "bind_version": "BIND 版本", "platform": "平台",
    "network": "网络路径", "cpu_definition": "CPU 指标定义", "rss_definition": "RSS 指标定义",
    "cpu_count_visible": "容器可见 CPU 数", "named_version_output": "BIND 构建信息",
    "dnsperf_version_output": "dnsperf 工具信息", "server_cpu_affinity": "服务器 CPU 亲和性",
    "client_cpu_affinity": "客户端 CPU 亲和性", "cpu_normalization": "CPU 计量口径",
    "rss_sampling_seconds": "RSS 采样间隔（秒）", "named_command": "服务启动命令",
    "actual_server_affinity": "实测服务 CPU 亲和性", "warmup_policy": "预热方式",
    "tcp_queries_per_connection": "TCP 单连接查询上限", "edns": "启用 EDNS", "dnssec": "启用 DNSSEC",
    "schedule_seed": "执行顺序随机种子", "latency_population": "延迟统计样本",
    "host": "宿主机", "host_os": "宿主机系统", "host_cpu": "宿主机 CPU", "host_memory_gib": "宿主机内存（GiB）",
    "host_logical_cpus": "宿主机逻辑 CPU 数", "host_memory_bytes": "宿主机内存（字节）",
    "docker_vcpus": "Docker 虚拟 CPU 数", "docker_memory_bytes": "Docker 内存（字节）",
    "docker_memory_gib": "Docker 内存（GiB）", "docker_kernel": "Docker 内核",
    "docker_version": "Docker 版本", "docker_architecture": "Docker 架构",
    "benchmark_image_id": "压测镜像 ID", "other_running_containers": "其他运行中容器数",
    "isolation_note": "环境隔离说明", "configuration": "服务配置", "zone": "区域文件",
    "tool_help": "压测工具帮助", "raw_data": "完整实测数据", "host_environment": "宿主机环境记录",
    "go_package_inventory": "Go 包清单", "executed_runner": "实际执行的压测脚本",
    "build_version": "构建与版本信息", "extended_tool_options": "工具扩展参数",
    "packages": "容器依赖包清单", "runner_log": "压测执行日志", "configuration_sha256": "配置与查询集 SHA-256",
    "run_complete": "正式测量是否完成", "all_measurements_valid": "正式记录是否全部有效",
}


def esc(value):
    return html.escape(str(value), quote=True)


def format_value(value):
    if value is None:
        return "未提供"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def number(value, digits=0):
    if value is None:
        return "—"
    return f"{value:,.{digits}f}"


def validate(data):
    if data.get("schema_version") != 1:
        raise ValueError("不支持的 schema_version，必须为 1")
    if data.get("comparison_status") != "blocked_go_server_missing":
        raise ValueError("此生成器仅处理 Go DNS 服务器缺失时的基线与可比性报告")
    go = data.get("go_server", {})
    if go.get("metrics", "absent") is not None or go.get("status") != "unimplemented":
        raise ValueError("go_server 必须明确 status=unimplemented、metrics=null")
    try:
        dt.datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        raise ValueError("created_at 必须为实际运行的 ISO 8601 时间；不能使用 schema 示例") from error
    runs = data.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("输入缺少实际压测记录")
    measured = 0
    identities = set()
    for index, run in enumerate(runs, 1):
        for key in ("transport", "workload", "target_qps", "repeat", "valid"):
            if key not in run:
                raise ValueError(f"第 {index} 次记录缺少 {key}")
        if not isinstance(run["valid"], bool):
            raise ValueError(f"第 {index} 次记录的 valid 必须为布尔值")
        if not isinstance(run["target_qps"], (int, float)) or not math.isfinite(run["target_qps"]) or run["target_qps"] <= 0:
            raise ValueError(f"第 {index} 次记录的目标 QPS 必须为正有限值")
        identity = (run["transport"], run["workload"], run["target_qps"], run["repeat"])
        if identity in identities:
            raise ValueError(f"发现重复的协议 / 负载 / 速率 / 轮次记录：{identity}")
        identities.add(identity)
        if run["valid"]:
            for key in [item[0] for item in METRICS] + ["queries_sent", "queries_completed", "queries_lost"]:
                value = run.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"第 {index} 次有效记录的 {key} 不是非负有限实测值")
            if run["queries_sent"] <= 0:
                raise ValueError(f"第 {index} 次有效记录未发送查询；不能将 schema 示例当作实测")
            if run["queries_completed"] + run["queries_lost"] > run["queries_sent"]:
                raise ValueError(f"第 {index} 次记录的查询计数不一致")
            if run["loss_percent"] > 100:
                raise ValueError(f"第 {index} 次记录的未完成比例超出 100%")
            measured += 1
    if not measured:
        raise ValueError("没有可用于报告的有效实测记录")
    if data.get("run_complete") is True:
        method = data.get("methodology", {})
        repeat_count = method.get("repetitions")
        if isinstance(repeat_count, bool) or not isinstance(repeat_count, int) or repeat_count < 1:
            raise ValueError("完整运行必须提供正整数 methodology.repetitions")
        axes = []
        for name in ("transports", "workloads", "rates_qps"):
            axis = method.get(name)
            if not isinstance(axis, list) or not axis or len(set(axis)) != len(axis):
                raise ValueError(f"完整运行必须提供不为空且不重复的 methodology.{name}")
            axes.append(axis)
        expected = set(itertools.product(*axes, range(1, repeat_count + 1)))
        if identities != expected:
            raise ValueError(f"完整运行组合不齐：设计 {len(expected)} 次，实际 {len(identities)} 次，"
                             f"缺少 {len(expected - identities)} 次，多出 {len(identities - expected)} 次")
    if "all_measurements_valid" in data and data["all_measurements_valid"] != all(run["valid"] for run in runs):
        raise ValueError("all_measurements_valid 与原始测量 valid 标记不一致")


def aggregate(data):
    groups = defaultdict(list)
    for run in data["runs"]:
        groups[(run["transport"], run["workload"], run["target_qps"])].append(run)
    result = []
    for (transport, workload, target), runs in sorted(groups.items()):
        valid = [run for run in runs if run["valid"]]
        group = {"transport": transport, "workload": workload, "target_qps": target,
                 "count": len(valid), "attempts": len(runs), "metrics": {}}
        for metric, *_ in METRICS:
            values = [run[metric] for run in valid]
            group["metrics"][metric] = (
                {"median": statistics.median(values), "min": min(values), "max": max(values)} if values else None
            )
        result.append(group)
    return result


def figure_svg(groups, metric, ylabel, title):
    """Each point is a median, with the minimum/maximum across valid repeats."""
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none",
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(7.0, 3.65), layout="constrained")
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    series = sorted({(g["transport"], g["workload"]) for g in groups})
    colors = ["#186b61", "#db7e34", "#3368ae", "#8a639a", "#a84647", "#6b7450"]
    targets = sorted({g["target_qps"] for g in groups})
    for i, (transport, workload) in enumerate(series):
        selected = sorted([g for g in groups if (g["transport"], g["workload"]) == (transport, workload)
                           and g["metrics"][metric] is not None], key=lambda g: g["target_qps"])
        if not selected:
            continue
        x = [g["target_qps"] for g in selected]
        y = [g["metrics"][metric]["median"] for g in selected]
        low = [g["metrics"][metric]["median"] - g["metrics"][metric]["min"] for g in selected]
        high = [g["metrics"][metric]["max"] - g["metrics"][metric]["median"] for g in selected]
        label = f"{transport.upper()} / {'A hit' if workload == 'positive_a' else workload.upper()}"
        ax.errorbar(x, y, yerr=[low, high], label=label, color=colors[i % len(colors)],
                    linewidth=1.8, marker="o" if transport == "udp" else "s", markersize=5,
                    linestyle="-" if transport == "udp" else "--", capsize=4, alpha=0.95)
    if metric == "qps" and targets:
        ax.plot(targets, targets, color="#a7b2b0", linewidth=1, linestyle=":", label="Target rate")
    ax.set_title(title, loc="left", pad=14, fontweight="bold", color="#163833", fontsize=12)
    ax.set_xlabel("Target offered rate (queries/s)")
    ax.set_ylabel(ylabel)
    ax.set_xticks(targets)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1000:g}k" if abs(value) >= 1000 else f"{value:g}"))
    if metric == "qps":
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1000:g}k" if abs(value) >= 1000 else f"{value:g}"))
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color="#e5ece9", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.21), ncol=2, frameon=False, fontsize=8)
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", metadata={"Date": None})
    plt.close(fig)
    svg = buffer.getvalue()
    return svg[svg.index("<svg"):].replace("<svg ", f'<svg role="img" aria-label="{esc(title)}" ', 1)


def facts_table(values):
    if not values:
        return '<p class="muted">输入文件未提供该信息。</p>'
    rows = []
    for key, value in values.items():
        content = format_value(value)
        rendered = f'<pre>{esc(content)}</pre>'
        if len(content) > 800 or content.count("\n") > 10:
            rendered = f'<details class="metadata-detail"><summary>展开完整记录</summary>{rendered}</details>'
        rows.append(f'<tr><th scope="row">{esc(LABELS.get(key, key))}</th><td>{rendered}</td></tr>')
    return f'<table class="facts"><tbody>{"".join(rows)}</tbody></table>'


def range_cell(stats, digits):
    if stats is None:
        return '<td class="numeric">无有效样本</td>'
    return f'<td class="numeric"><strong>{number(stats["median"], digits)}</strong><small>{number(stats["min"], digits)} – {number(stats["max"], digits)}</small></td>'


def group_table(groups, repetitions):
    rows = []
    for group in groups:
        state = "完整" if group["count"] == repetitions and group["attempts"] == repetitions else "样本不齐"
        rows.append(f'<tr data-transport="{esc(group["transport"])}" data-workload="{esc(group["workload"])}">'
                    f'<td><span class="protocol">{esc(group["transport"].upper())}</span></td>'
                    f'<td>{esc(WORKLOAD_NAMES.get(group["workload"], group["workload"]))}</td>'
                    f'<td class="numeric">{number(group["target_qps"])}</td>'
                    + "".join(range_cell(group["metrics"][key], digits).replace('</td>',
                        f'<small>达目标 {number(group["metrics"][key]["median"] / group["target_qps"] * 100, 1)}%</small></td>')
                        if key == "sent_qps" and group["metrics"][key] is not None and group["target_qps"] else
                        range_cell(group["metrics"][key], digits) for key, _, _, digits in METRICS)
                    + f'<td>{group["count"]}/{repetitions}<small>{state}</small></td></tr>')
    heads = "".join(f'<th scope="col">{esc(label)}<small>{esc(unit)}</small></th>' for _, label, unit, _ in METRICS)
    return '<div class="table-scroll"><table id="aggregate-table"><thead><tr><th>协议</th><th>工作负载</th><th>目标 QPS</th>' + heads + '<th>有效重复</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'


def raw_table(runs):
    rows = []
    for run in runs:
        cells = "".join(f'<td class="numeric">{number(run.get(key), digits)}</td>' for key, _, _, digits in METRICS)
        rows.append(f'<tr data-transport="{esc(run["transport"])}" data-workload="{esc(run["workload"])}">'
                    f'<td>{esc(run["transport"].upper())}</td><td>{esc(WORKLOAD_NAMES.get(run["workload"], run["workload"]))}</td>'
                    f'<td class="numeric">{number(run["target_qps"])}</td><td>{esc(run["repeat"])}</td>{cells}'
                    f'<td class="numeric">{number(run.get("queries_sent"))}</td><td class="numeric">{number(run.get("queries_completed"))}</td>'
                    f'<td class="numeric">{number(run.get("queries_lost"))}</td><td class="codes">{esc(format_value(run.get("response_codes", {})))}</td>'
                    f'<td>{"有效" if run["valid"] else "无效 / 排除"}</td><td class="log">{esc(run.get("log", "未提供"))}</td></tr>')
    heads = "".join(f'<th>{esc(label)}<small>{esc(unit)}</small></th>' for _, label, unit, _ in METRICS)
    return '<div class="table-scroll"><table id="raw-table" class="raw"><thead><tr><th>协议</th><th>工作负载</th><th>目标 QPS</th><th>轮次</th>' + heads + '<th>发送</th><th>完成</th><th>未完成</th><th>响应码</th><th>状态</th><th>原始日志路径</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'


CSS = """
:root{--ink:#193b35;--text:#304842;--muted:#61756f;--line:#d9e4de;--green:#1c7062;--paper:#f3f6f1;--amber:#97521d}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:var(--text);background:var(--paper);font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
button,select{font:inherit}a{color:var(--green)}.wrap{width:min(1400px,94%);margin:auto}header{background:#173e36;color:white;padding:54px 0 38px;border-bottom:5px solid #c1d5a7}
.eyebrow{font-size:12px;letter-spacing:2.2px;color:#c0d8c7;text-transform:uppercase;font-weight:700}.hero-row{display:flex;justify-content:space-between;align-items:start;gap:30px}h1{font-size:clamp(27px,3.4vw,44px);letter-spacing:-1px;line-height:1.3;margin:14px 0 12px;font-weight:720}header p{max-width:820px;color:#d4e2d9;margin:0}.badge{white-space:nowrap;border:1px solid #779a87;padding:7px 14px;border-radius:30px;font-size:13px;margin-top:18px;background:#ffffff08}.meta{font-size:12px;color:#b9d1c1;margin-top:24px}.toolbar{display:flex;gap:10px;align-items:center;padding:16px 0;justify-content:space-between;color:var(--muted);font-size:13px}.toolbar nav{display:flex;gap:19px;flex-wrap:wrap}.toolbar nav a{text-decoration:none}.actions{display:flex;gap:8px}.button{border:1px solid #b9cfc0;background:#fff;border-radius:8px;padding:7px 13px;cursor:pointer;color:var(--ink)}.button:hover{background:#e8f0e8}
main{padding:4px 0 48px}.callout{border:1px solid #e5c5a1;border-left:5px solid #bb7635;background:#fff6e9;border-radius:9px;padding:21px 25px;margin:12px 0 22px;color:#704521}.callout h2{color:#704521;font-size:20px;margin:0 0 6px}.callout p{margin:0}.callout strong{font-weight:750}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:0 0 28px}.kpi{background:#fff;border:1px solid var(--line);border-radius:11px;padding:20px 22px}.kpi .label{font-size:13px;color:var(--muted)}.kpi .value{font-size:31px;font-weight:750;letter-spacing:-.7px;line-height:1.4;color:var(--ink);margin:5px 0}.kpi .value.unavailable{font-size:24px;color:var(--amber)}.kpi .note{font-size:12px;color:var(--muted)}section{margin-top:28px;scroll-margin-top:15px}section h2{font-size:24px;color:var(--ink);margin:0 0 8px;letter-spacing:-.3px}.section-top{display:flex;gap:20px;justify-content:space-between;align-items:end}.section-top p,section>p{margin:0 0 15px}.muted{color:var(--muted)}.caption{font-size:13px;color:var(--muted)}.panel{background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden}.compare-table th{width:29%}.unavailable-text{color:var(--amber);font-weight:650}.chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.chart{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px 18px 12px;overflow:hidden}.chart svg{display:block;width:100%;height:auto}.chart p{margin:6px 7px;font-size:13px;color:var(--muted)}.filter{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:14px 0}.filter label{font-size:13px;color:var(--muted)}select{background:white;border:1px solid #bfd0c5;border-radius:7px;color:var(--ink);padding:7px 30px 7px 10px}.filter-count{margin-left:auto;font-size:13px;color:var(--muted)}table{width:100%;border-collapse:collapse;background:white;font-size:13px}th,td{text-align:left;padding:12px 14px;border-bottom:1px solid #e6ece7;vertical-align:middle}thead th{color:#496459;background:#eaf1eb;font-weight:650;white-space:nowrap}tbody tr:last-child>*{border-bottom:0}tbody tr:hover{background:#f7faf6}td.numeric,th.numeric{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}td strong{font-weight:700}small{display:block;font-size:11px;color:var(--muted);font-weight:400;white-space:nowrap}td small{margin-top:2px}.protocol{font-size:11px;font-weight:750;background:#ebf2ed;padding:3px 6px;border-radius:4px;color:var(--green)}.table-scroll{overflow-x:auto}.raw{font-size:11px;min-width:1600px}.raw td,.raw th{padding:10px 9px}.raw .log{min-width:150px;max-width:260px;overflow-wrap:anywhere;font-size:10px}.codes{font-family:ui-monospace,SFMono-Regular,monospace;font-size:10px;min-width:100px}details>summary{cursor:pointer;padding:18px 21px;font-weight:650;color:var(--ink);background:#f9fbf8}details[open]>summary{border-bottom:1px solid var(--line)}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px}.facts th{width:34%;font-weight:500;color:var(--muted);vertical-align:top}.facts td{overflow-wrap:anywhere}.facts pre{font:inherit;white-space:pre-wrap;margin:0}.panel-title{font-size:16px;font-weight:700;color:var(--ink);padding:16px 19px;border-bottom:1px solid var(--line);margin:0}.notes{padding:19px 24px}.notes ol,.notes ul{margin:0;padding-left:22px}.notes li+li{margin-top:9px}.inline-code,code{font-family:ui-monospace,SFMono-Regular,monospace;font-size:12px;overflow-wrap:anywhere}footer{padding:25px 0 35px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}footer .hash{overflow-wrap:anywhere;font-family:ui-monospace,SFMono-Regular,monospace;font-size:11px}.print-only{display:none}[hidden]{display:none!important}noscript{display:block;margin:8px 0;color:var(--amber)}
@media(max-width:850px){.kpis{grid-template-columns:repeat(2,1fr)}.chart-grid,.two-col{grid-template-columns:1fr}.hero-row,.section-top{display:block}.badge{display:inline-block}.toolbar{align-items:start}.toolbar nav{gap:12px}.toolbar .actions{flex-direction:column}.wrap{width:92%}.chart{padding:12px}.filter-count{width:100%;margin-left:0}.compare-table{min-width:630px}}
@page{size:A4 landscape;margin:13mm}@media print{body{background:white;font-size:10px}.wrap{width:100%}header{padding:15px 0;background:white;color:var(--ink);border-bottom:2px solid var(--green)}header p,.meta,.eyebrow{color:var(--muted)}h1{font-size:27px}.badge{border-color:var(--line)}.toolbar,.filter,.no-print{display:none}.print-only{display:block}.callout{padding:12px 15px;margin:15px 0}.callout h2{font-size:16px}.kpis{gap:10px;margin-bottom:15px}.kpi{padding:10px 14px}.kpi .value{font-size:25px}.kpi .value.unavailable{font-size:20px}section{margin-top:18px}section h2{font-size:20px}.chart-grid{gap:10px}.chart{padding:5px;break-inside:avoid}.chart p{font-size:10px}.panel{overflow:visible}.table-scroll{overflow:visible}table{font-size:10px}th,td{padding:7px 8px}small{font-size:9px}thead{display:table-header-group}tr{break-inside:avoid}.raw{min-width:0;font-size:7px;table-layout:fixed}.raw td,.raw th{padding:4px 3px;white-space:normal;overflow-wrap:anywhere}.raw small{font-size:7px;white-space:normal}.raw .log{min-width:0;max-width:none;font-size:6px}.raw .codes{min-width:0;font-size:6px}.raw th:last-child,.raw td:last-child{width:13%}.facts{font-size:10px}.two-col{gap:12px}.notes{padding:12px 16px}.caption{font-size:10px}details>summary{padding:10px}footer{font-size:9px}.kpi,.callout,.two-col,.notes{break-inside:avoid}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""


JS = """
const transport=document.getElementById('transport-filter');
const workload=document.getElementById('workload-filter');
function filterRows(){
  let counts=[];
  for(const id of ['aggregate-table','raw-table']){
    let visible=0;
    document.querySelectorAll('#'+id+' tbody tr').forEach(row=>{
      row.hidden=(transport.value!=='all'&&row.dataset.transport!==transport.value)||(workload.value!=='all'&&row.dataset.workload!==workload.value);
      if(!row.hidden)visible++;
    });counts.push(visible);
  }
  document.getElementById('filter-count').textContent=`显示 ${counts[0]} 组汇总 / ${counts[1]} 次原始测量；图表始终显示完整数据`;
}
transport.addEventListener('change',filterRows);workload.addEventListener('change',filterRows);filterRows();
let detailsBeforePrint, rowsBeforePrint;
window.addEventListener('beforeprint',()=>{
 detailsBeforePrint=[...document.querySelectorAll('details')].map(d=>[d,d.open]);
 rowsBeforePrint=[...document.querySelectorAll('tr[hidden]')];
 document.querySelectorAll('details').forEach(d=>d.open=true);rowsBeforePrint.forEach(r=>r.hidden=false);
});
window.addEventListener('afterprint',()=>{
 (detailsBeforePrint||[]).forEach(([d,open])=>d.open=open);filterRows();
});
document.getElementById('print-button').addEventListener('click',()=>window.print());
document.getElementById('download-button').addEventListener('click',()=>{
 const data=document.getElementById('benchmark-data').textContent;
 const url=URL.createObjectURL(new Blob([data],{type:'application/json;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download='benchmark.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
"""


def render(data, source, source_hash):
    validate(data)
    groups = aggregate(data)
    runs = data["runs"]
    valid_runs = [run for run in runs if run["valid"]]
    method = data.get("methodology", {})
    repetitions = method.get("repetitions", 3)
    duration = method.get("duration_seconds", "未提供")
    baseline = data.get("baseline", {})
    baseline_label = f'{baseline.get("name", "ISC BIND")} {baseline.get("version", "版本未提供")}'
    total_sent = sum(run["queries_sent"] for run in valid_runs)
    total_completed = sum(run["queries_completed"] for run in valid_runs)
    total_lost = sum(run["queries_lost"] for run in valid_runs)
    loss_percent = 100 * total_lost / total_sent
    windows = [run["resource_window_seconds"] for run in valid_runs if "resource_window_seconds" in run]
    resource_note = (f'资源计量窗口的实际范围为 {number(min(windows), 3)}–{number(max(windows), 3)} 秒，'
                     '包含客户端启动与退出轮询，可能长于 dnsperf 的统计时长；CPU 分母使用该资源窗口。'
                     if windows else '输入未提供资源计量窗口时长。')
    charts = []
    for metric, ylabel, title, note in [
        ("qps", "Completed queries/s", "BIND · completed throughput", "完成 QPS 按 dnsperf 的查询完成数与运行时长统计；虚线为配置的目标速率。"),
        ("latency_avg_ms", "Mean latency (ms)", "BIND · mean response latency", "展示每次压测平均延迟的中位数与范围；不表示单个请求的 p95 或 p99。"),
        ("server_cpu_percent", "Server CPU (%)", "BIND · server CPU usage", "100% 表示一个逻辑 CPU 核；CPU 为测量区间进程时间差除以墙钟时长。"),
        ("server_rss_peak_mib", "Peak RSS (MiB)", "BIND · sampled peak RSS", "每次压测期间采样得到的服务进程峰值 RSS；不同于堆内存或整个容器内存。"),
    ]:
        charts.append(f'<figure class="chart" style="margin:0">{figure_svg(groups, metric, ylabel, title)}<p>{note}</p></figure>')
    options = lambda field, label: '<option value="all">全部' + label + '</option>' + "".join(
        f'<option value="{esc(value)}">{esc(value.upper() if field == "transport" else WORKLOAD_NAMES.get(value, value))}</option>'
        for value in sorted({run[field] for run in runs}))
    go_rows = "".join(f'<tr><th scope="row">{esc(label)}</th><td>见下方实测分组</td><td class="unavailable-text">不可测 / 未实现</td></tr>' for _, label, _, _ in METRICS)
    limitations = [
        "Go 工程尚未实现 DNS 服务器，缺少可运行的 DNS 监听器和服务入口。没有 Go 服务端压测数据，无法判断两种实现的速度、资源效率或性能提升百分比。",
        "本报告是 ISC BIND 基线压测与可比性说明，仅覆盖输入中列明的协议、区域数据、查询类型和速率，不等同于完整 BIND 功能测试。",
        "配置的目标 QPS 是提供给负载工具的发送速率上限；实际发送、实际完成和目标值可能不同。这些有限速率测试不构成服务器最大 QPS 或容量上限测定。",
        "平均延迟只统计负载工具成功完成的查询，超时或未完成查询不进入该平均数；必须同时阅读未完成比例。dnsperf 的平均值、最小值、最大值与标准差不能替代 p95 / p99，本报告未测量百分位。",
        f"每组以 {repetitions} 次有效重复为设计目标，表格主值为中位数，小字为最小值–最大值。图中误差线使用相同范围，不是置信区间；不足设计重复数的组会明确标注。",
        "这里的“未完成”对应 dnsperf 的 queries_lost，可能包含超时等情况，不能单凭该值断言网络层丢包。预热数据不并入正式测量的汇总。",
    ] + data.get("limitations", [])
    limitations_html = "".join(f'<li>{esc(format_value(item))}</li>' for item in limitations)
    payload = json.dumps(data, ensure_ascii=False, indent=2).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    full_groups = sum(g["count"] == repetitions and g["attempts"] == repetitions for g in groups)
    partial_notice = ('<p style="margin-top:9px"><strong>运行尚未标记完成：</strong>此文件是进行中测量的快照，'
                      '请以所有正式测量结束后的报告为准。</p>' if not data.get("run_complete", False) else "")
    artifact_table = facts_table({**data.get("artifacts", {}),
                                  "configuration_sha256": data.get("configuration_sha256", "未提供"),
                                  "run_complete": data.get("run_complete", "未提供"),
                                  "all_measurements_valid": data.get("all_measurements_valid", "未提供")})
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="真实 ISC BIND 基线压测数据与 Go DNS 服务器可比性报告。Go 服务器未实现，无 Go 性能数据。">
<title>BIND 与 Go DNS 服务器性能测试报告</title><style>{CSS}</style></head><body>
<header><div class="wrap"><div class="eyebrow">DNS PERFORMANCE · MEASUREMENT REPORT</div><div class="hero-row"><div>
<h1>BIND 与 Go DNS 服务器<br>性能测试报告</h1><p>基于真实压测的 BIND 性能基线，以及 Go 移植版本的可比性检查。</p></div><span class="badge">BIND 已测 · Go 尚不可测</span></div>
<div class="meta">测试记录时间：{esc(data["created_at"])} &nbsp; / &nbsp; 基线：{esc(baseline_label)} &nbsp; / &nbsp; 数据格式：v{esc(data["schema_version"])}</div></div></header>
<div class="wrap toolbar"><nav aria-label="报告导航"><a href="#comparison">可比性</a><a href="#charts">性能图表</a><a href="#results">结果汇总</a><a href="#method">测试方法</a><a href="#raw">原始测量</a></nav><div class="actions"><button class="button" id="download-button">下载原始 JSON</button><button class="button" id="print-button">打印 / 保存 PDF</button></div></div>
<main class="wrap"><aside class="callout" role="note"><h2>当前只能建立 BIND 基线，尚不能完成双实现性能比较</h2><p>Go 工程<strong>未实现可运行的 DNS 服务器</strong>，因此 Go 的 QPS、延迟、未完成比例、CPU 和 RSS 均为<strong>不可测 / 未实现</strong>。本报告不提供速度胜负、性能提升百分比或替代 BIND 的结论。</p>{partial_notice}</aside>
<div class="kpis"><div class="kpi"><div class="label">有效正式压测</div><div class="value">{len(valid_runs)} <span style="font-size:16px;font-weight:500">次</span></div><div class="note">总记录 {len(runs)} 次 · 无效 {len(runs) - len(valid_runs)} 次</div></div>
<div class="kpi"><div class="label">测试条件组合</div><div class="value">{len(groups)} <span style="font-size:16px;font-weight:500">组</span></div><div class="note">完整重复 {full_groups}/{len(groups)} 组 · 每组设计 {esc(repetitions)} 次</div></div>
<div class="kpi"><div class="label">单次配置时长</div><div class="value">{esc(duration)} <span style="font-size:16px;font-weight:500">秒</span></div><div class="note">正式测量 · 预热另计</div></div>
<div class="kpi"><div class="label">Go DNS 服务器</div><div class="value unavailable">不可测 / 未实现</div><div class="note">metrics = null · 无服务端性能数据</div></div></div>
<section id="comparison"><h2>01 / 版本与可比性</h2><p class="muted">完成 Go DNS 服务端实现，并使用相同区域数据、查询集、机器与参数后，才能加入对应实测列。</p>
<div class="panel table-scroll"><table class="compare-table"><thead><tr><th>检查项 / 指标</th><th>{esc(baseline_label)}</th><th>Go 移植版本</th></tr></thead><tbody><tr><th scope="row">DNS 服务状态</th><td>已启动并接受正式压测</td><td class="unavailable-text">未实现</td></tr>{go_rows}</tbody></table></div>
<p class="caption" style="margin-top:10px">Go 缺失证据：{esc(data["go_server"].get("reason", "未提供更多说明"))}</p></section>
<section id="charts"><h2>02 / BIND 性能图表</h2><p class="muted">每个点为同一条件下有效重复的中位数，误差线为最小值–最大值。图表仅展示 BIND 实测。</p><div class="chart-grid">{"".join(charts)}</div></section>
<section id="results"><h2>03 / 分组测试结果</h2><p class="muted">每个指标上方为中位数，下方为重复范围；单次峰值 RSS 再按重复进行汇总。实际发送 QPS 单独列出，“达目标”是实际发送中位数除以配置目标值，不是版本间性能提升。</p>
<div class="filter"><label for="transport-filter">协议</label><select id="transport-filter">{options("transport", "协议")}</select><label for="workload-filter">工作负载</label><select id="workload-filter">{options("workload", "负载")}</select><span id="filter-count" class="filter-count" aria-live="polite"></span></div>
<noscript>JavaScript 已停用。完整数据仍可阅读；筛选、下载和打印按钮不可用。</noscript><p class="print-only caption">打印包含全部分组与原始记录，忽略屏幕筛选。</p>
<div class="panel">{group_table(groups, repetitions)}</div><p class="caption" style="margin-top:11px">所有有效正式测量合计：发送 {number(total_sent)} 次，完成 {number(total_completed)} 次，未完成 {number(total_lost)} 次，按查询数加权的未完成比例 {number(loss_percent, 4)}%。该总计混合不同负载，仅用于核对记录。</p></section>
<section id="method"><h2>04 / 测试环境与方法</h2><p class="muted">以下内容直接取自输入记录；未记录的信息不作推断。{resource_note}</p><div class="two-col"><div class="panel"><h3 class="panel-title">运行环境</h3>{facts_table(data.get("environment", {}))}</div><div class="panel"><h3 class="panel-title">负载与测量参数</h3>{facts_table(method)}</div></div></section>
<section id="limits"><h2>05 / 结论边界与后续对比条件</h2><div class="panel notes"><ol>{limitations_html}</ol></div></section>
<section id="raw"><h2>06 / 原始测量与追溯</h2><p class="muted">保留全部 {len(runs)} 次正式记录。可下载页内嵌入的完整 JSON；其中还包含 dnsperf 延迟最小值、最大值、标准差及原始日志路径。</p>
<details class="panel" open><summary>展开 / 折叠 {len(runs)} 次原始测量详情</summary>{raw_table(runs)}</details>
<details class="panel" style="margin-top:15px"><summary>运行产物与复现入口</summary>{artifact_table}</details></section>
</main><footer><div class="wrap">本报告离线可用，所有图表与原始输入均已内嵌。图表由 Matplotlib 生成，数值仅来自实际输入文件。<br>输入文件：<code>{esc(source.name)}</code><br><span class="hash">输入文件 SHA-256：{source_hash}</span></div></footer>
<script type="application/json" id="benchmark-data">{payload}</script><script>{JS}</script></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    data = json.loads(raw)
    output = render(data, args.input, hashlib.sha256(raw).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print(f"已生成：{args.output.resolve()}（{len(data['runs'])} 次记录；Go 性能不可测）")


if __name__ == "__main__":
    main()
