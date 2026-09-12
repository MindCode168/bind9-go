#!/usr/bin/env python3
"""Short dnsperf observations of the real upstream named, never a Go server proxy.

Run in bind9-go-benchmark with /bench read-only and /results writable.
"""
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import random
import re
import statistics
import subprocess
import time

OUT = Path('/results')
RATE = [10000, 50000, 100000]
DURATION, WARMUP, REPEATS, SAMPLE = 5, 2, 3, 0.1


def save_command(argv, name):
    completed = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    (OUT/name).write_bytes(completed.stdout)
    if completed.returncode:
        raise RuntimeError(f'{argv}: {completed.returncode}; see {name}')
    return completed.stdout.decode(errors='replace')


def process_stats(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        ticks = int(fields[11])+int(fields[12])
        status = Path(f'/proc/{pid}/status').read_text()
        rss = re.search(r'^VmRSS:\s+(\d+)', status, re.M)
        return ticks, int(rss.group(1))/1024 if rss else 0
    except FileNotFoundError:
        return None


def parse_stats(text):
    def number(label):
        match = re.search(r'^\s*'+re.escape(label)+r':\s+([\d.]+)',text,re.M)
        if not match:
            raise ValueError(f'dnsperf output missing {label}')
        return float(match.group(1))
    latency_range = re.search(r'Average Latency \(s\):\s+[\d.]+\s+\(min\s+([\d.]+),\s+max\s+([\d.]+)\)',text)
    if not latency_range:
        raise ValueError('No latency range')
    codes_line = re.search(r'Response codes:\s*(.*)',text)
    codes = {code:int(count) for code,count in re.findall(r'(\w+)\s+(\d+)\s*\(',codes_line.group(1))} if codes_line else {}
    sent, complete, lost = map(int,[number('Queries sent'),number('Queries completed'),number('Queries lost')])
    runtime = number('Run time (s)')
    return {'queries_sent':sent,'queries_completed':complete,'queries_lost':lost,
            'runtime_seconds':runtime,'sent_qps':sent/runtime,'qps':number('Queries per second'),
            'latency_avg_ms':number('Average Latency (s)')*1000,
            'latency_min_ms':float(latency_range.group(1))*1000,
            'latency_max_ms':float(latency_range.group(2))*1000,
            'latency_stddev_ms':number('Latency StdDev (s)')*1000,
            'loss_percent':lost/sent*100 if sent else None,'response_codes':codes}


def command(transport, workload, rate, duration):
    cmd = ['taskset','-c','2,3','dnsperf','-f','inet','-m',transport,
           '-s','127.0.0.1','-p','5300','-d',str(OUT/f'{workload}.txt'),
           '-T','2','-c','16','-q','256','-Q',str(rate),'-l',str(duration),'-t','1',
           '-O','suppress=timeouts']
    if transport == 'tcp':
        cmd += ['-O','num-queries-per-conn=1000000']
    return cmd


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'logs').mkdir(exist_ok=True)
    rng = random.Random(92027)
    names = list(range(10000))
    rng.shuffle(names)
    zone = ['$ORIGIN bench.test.', '$TTL 300',
            '@ IN SOA ns.bench.test. hostmaster.bench.test. (1 3600 600 86400 300)',
            '@ IN NS ns.bench.test.', 'ns IN A 192.0.2.53']
    zone += [f'w{i:05d} IN A 192.0.2.123' for i in range(10000)]
    (OUT/'bench.zone').write_text('\n'.join(zone)+'\n')
    for workload,prefix in [('positive_a','w'),('nxdomain','absent')]:
        (OUT/f'{workload}.txt').write_text(''.join(f'{prefix}{i:05d}.bench.test. A\n' for i in names))
    (OUT/'named.conf').write_text('''
options {
    directory "/results";
    listen-on port 5300 { 127.0.0.1; };
    listen-on-v6 { none; };
    recursion no;
    dnssec-validation no;
    allow-query { 127.0.0.1; };
    allow-transfer { none; };
    notify no;
    minimal-responses yes;
    querylog no;
    tcp-clients 1024;
    pid-file "/results/named.pid";
    session-keyfile "/results/session.key";
};
controls { };
zone "bench.test" { type primary; file "/results/bench.zone"; };
'''.strip()+'\n')
    version = save_command(['/src/bin/named/named','-V'],'named-version.txt')
    tool_version = save_command(['dnsperf','-h'],'dnsperf-help.txt')
    save_command(['dnsperf','-H'],'dnsperf-options.txt')
    save_command(['/src/bin/check/named-checkconf','-z',str(OUT/'named.conf')],'checkconf.log')
    save_command(['dpkg-query','-W'],'packages.txt')
    report = {'schema_version':1,'title':'BIND 与 Go DNS 服务器性能测试报告',
        'comparison_status':'blocked_go_server_missing','created_at':datetime.now(timezone.utc).isoformat(),
        'baseline':{'name':'ISC BIND','version':'9.20.27'},
        'go_server':{'status':'unimplemented','reason':'只有 internal/serial 和 internal/ttl，无 main、DNS listener 或服务可执行程序。','metrics':None},
        'environment':{'os':platform.platform(),'architecture':platform.machine(),
                       'cpu_count_visible':os.cpu_count(),'named_version_output':version,
                       'dnsperf_version_output':tool_version,'network':'single-container IPv4 loopback, no external network',
                       'server_cpu_affinity':'0,1','client_cpu_affinity':'2,3',
                       'cpu_normalization':'100% = one logical CPU; named limited to two logical CPUs',
                       'rss_sampling_seconds':SAMPLE},
        'methodology':{'tool':'dnsperf 2.14.0','duration_seconds':DURATION,'warmup_seconds':WARMUP,
                       'warmup_policy':'independent dnsperf warmup before every measured run; TCP reconnects for each run',
                       'repetitions':REPEATS,'rates_qps':RATE,'zone_records':10000,
                       'transports':['udp','tcp'],'workloads':['positive_a','nxdomain'],
                       'client_threads':2,'client_sockets':16,'max_outstanding':256,
                       'server_cpus':'0,1','client_cpus':'2,3','timeout_seconds':1,
                       'tcp_queries_per_connection':1000000,'edns':False,'dnssec':False,
                       'schedule_seed':92027,'latency_population':'received DNS responses only; lost queries excluded'},
        'runs':[],
        'limitations':[
            'Go 服务尚未实现，所有 Go DNS 性能指标不可测，无法计算快慢或提升比例。',
            '每次 5 秒、3 次重复，仅代表短时观测；不能推导最大 QPS、稳定容量或生产 SLA。',
            '同机 Docker VM 内回环，服务端与客户端各绑定 2 个逻辑 CPU；宿主机及其他容器仍可能造成干扰。',
            '目标发送速率不等于实际发送速率；dnsperf、CPU 和 256 个未完成请求的上限可能成为限制。',
            '仅测试单个 unsigned 权威区的 A 和 NXDOMAIN；未测递归、DNSSEC、TLS/HTTPS、更新及传送性能。',
            'dnsperf 仅报告平均、最小、最大和标准差延迟，本报告未测 p95/p99。丢失请求不进入已收到响应的延迟统计。',
            'TCP 为每轮新建客户端连接后复用，单连接上限 100 万查询，不是每查询建连性能。',
            'CPU 为区间进程时间差，100% 表示一个逻辑核；RSS 为每 100ms 采样所得峰值。',
            '使用已有源码测试构建，包括 --enable-fixed-rrset、dnstap 等选项，不代表发行包默认编译性能。',
            'dnsperf 统计预期响应码；完整报文内容仅在压测前的代表性查询中核对，不能据此声明全部DNS行为兼容。'
        ],'artifacts':{'configuration':'named.conf','zone':'bench.zone','tool_help':'dnsperf-help.txt'}}
    named_command=['taskset','-c','0,1','/src/bin/named/named','-g','-n','2','-U','2','-c',str(OUT/'named.conf')]
    report['environment']['named_command']=named_command
    with (OUT/'named.log').open('wb') as log:
        server = subprocess.Popen(named_command,stdout=log,stderr=subprocess.STDOUT)
        try:
            for attempt in range(50):
                if server.poll() is not None:
                    raise RuntimeError('named exited; inspect named.log')
                ready = subprocess.run(['/src/bin/dig/dig','@127.0.0.1','-p','5300','w00000.bench.test.','A',
                                         '+norecurse','+timeout=1','+tries=1'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                if b'192.0.2.123' in ready.stdout:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError('named not ready')
            report['environment']['actual_server_affinity']=sorted(os.sched_getaffinity(server.pid))
            for mode in ['udp','tcp']:
                for workload,name in [('positive_a','w00000'),('nxdomain','absent00000')]:
                    text=save_command(['/src/bin/dig/dig','@127.0.0.1','-p','5300',f'{name}.bench.test.','A',
                                       '+norecurse','+tcp' if mode=='tcp' else '+notcp'],f'preflight-{mode}-{workload}.txt')
                    expected='NOERROR' if workload=='positive_a' else 'NXDOMAIN'
                    assert f'status: {expected}' in text and re.search(r'flags:.*\baa\b',text),text
                    assert ('192.0.2.123' in text) if workload=='positive_a' else ('SOA' in text),text
            # A parser/option smoke run must succeed before the measurement series.
            smoke=save_command(command('udp','positive_a',1000,1),'smoke.log')
            assert parse_stats(smoke)['response_codes'].get('NOERROR',0)>0
            schedule=list(itertools.product(['udp','tcp'],['positive_a','nxdomain'],RATE,range(1,REPEATS+1)))
            rng.shuffle(schedule)
            for index,(mode,workload,rate,repeat) in enumerate(schedule,1):
                stem=f'{index:02d}-{mode}-{workload}-{rate}-r{repeat}'
                save_command(command(mode,workload,rate,WARMUP),f'logs/{stem}-warmup.log')
                before=process_stats(server.pid)
                started=time.monotonic()
                samples=[]
                argv=command(mode,workload,rate,DURATION)
                with (OUT/f'logs/{stem}.log').open('wb') as logfile:
                    client=subprocess.Popen(argv,stdout=logfile,stderr=subprocess.STDOUT)
                    while client.poll() is None:
                        sample=process_stats(server.pid)
                        if sample:
                            samples.append({'elapsed_seconds':time.monotonic()-started,'ticks':sample[0],'rss_mib':sample[1]})
                        if time.monotonic()-started > 20:
                            client.kill(); client.wait()
                            raise RuntimeError(f'dnsperf timeout: {stem}')
                        time.sleep(SAMPLE)
                elapsed=time.monotonic()-started
                after=process_stats(server.pid)
                measured=parse_stats((OUT/f'logs/{stem}.log').read_text())
                expected='NOERROR' if workload=='positive_a' else 'NXDOMAIN'
                measured.update(transport=mode,workload=workload,target_qps=rate,repeat=repeat,command=argv,
                                log=f'logs/{stem}.log',sample_log=f'logs/{stem}-resources.json',
                                server_cpu_percent=(after[0]-before[0])/os.sysconf('SC_CLK_TCK')/elapsed*100,
                                server_rss_peak_mib=max(s['rss_mib'] for s in samples),
                                resource_window_seconds=elapsed,resource_samples=len(samples),
                                valid=client.returncode==0 and measured['queries_completed']>0 and
                                    measured['response_codes']=={expected:measured['queries_completed']},
                                exit_code=client.returncode)
                (OUT/f'logs/{stem}-resources.json').write_text(json.dumps(samples)+'\n')
                report['runs'].append(measured)
                (OUT/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                print(f'{index}/{len(schedule)} {mode} {workload} target={rate} completed={measured["qps"]:.0f} qps latency={measured["latency_avg_ms"]:.3f} ms loss={measured["loss_percent"]:.3f}% valid={measured["valid"]}',flush=True)
            report['configuration_sha256']={f:hashlib.sha256((OUT/f).read_bytes()).hexdigest()
                                            for f in ['named.conf','bench.zone','positive_a.txt','nxdomain.txt']}
            report['run_complete']=True
            report['all_measurements_valid']=all(r['valid'] for r in report['runs'])
            (OUT/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        finally:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired: server.kill(); server.wait()


if __name__=='__main__':
    main()
