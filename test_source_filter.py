#!/usr/bin/env python3
"""
测试来源过滤功能
验证后端source_filter参数是否正常工作
"""
import requests
import json
import time

API_BASE = "http://localhost:8000"

def test_search(query: str, source_filter=None, limit=5):
    """测试搜索"""
    print(f"\n{'='*60}")
    print(f"测试搜索: {query}")
    if source_filter:
        print(f"来源过滤: {source_filter}")
    else:
        print(f"来源过滤: 无（全部）")
    print(f"{'='*60}")

    payload = {
        "query": query,
        "limit": limit
    }

    if source_filter:
        payload["source_filter"] = source_filter

    try:
        start_time = time.time()
        response = requests.post(
            f"{API_BASE}/search",
            json=payload,
            timeout=10
        )
        elapsed = (time.time() - start_time) * 1000  # 转换为毫秒

        if response.status_code == 200:
            result = response.json()
            sources_count = len(result.get('sources', []))
            print(f"\n✅ 搜索成功")
            print(f"  • 耗时: {elapsed:.0f} ms")
            print(f"  • 返回结果: {sources_count} 条")

            # 显示前2个结果
            if sources_count > 0:
                print(f"\n前2个结果:")
                for i, source in enumerate(result['sources'][:2], 1):
                    source_type = "📄 PDF" if 'filename' in source else "💬 论坛"
                    print(f"  {i}. [{source_type}] {source['title']}")
                    if 'filename' in source:
                        print(f"     文档: {source['filename']}")
                    print(f"     摘要: {source['snippet'][:80]}...")

            return elapsed, sources_count
        else:
            print(f"\n✗ 搜索失败: {response.status_code}")
            print(f"  错误: {response.text}")
            return None, None

    except Exception as e:
        print(f"\n✗ 请求异常: {e}")
        return None, None


def main():
    print(f"\n{'='*70}")
    print(f"来源过滤功能测试")
    print(f"{'='*70}")

    # 检查后端是否运行
    try:
        response = requests.get(f"{API_BASE}/pdf/list", timeout=5)
        if response.status_code != 200:
            print("\n❌ 后端服务未运行")
            print("请先启动后端: python3 backend/api/main.py")
            return
    except:
        print("\n❌ 无法连接后端服务")
        print("请先启动后端: python3 backend/api/main.py")
        return

    print("\n✅ 后端服务正常运行\n")

    # 测试用例
    test_cases = [
        {
            "query": "如何加速视频",
            "filters": [None, "pdf", "forum"],
            "description": "软件操作问题"
        },
        {
            "query": "渲染崩溃",
            "filters": [None, "forum", "pdf"],
            "description": "故障排查"
        }
    ]

    for test in test_cases:
        print(f"\n{'='*70}")
        print(f"测试场景: {test['description']}")
        print(f"查询: {test['query']}")
        print(f"{'='*70}")

        results = []

        for filter_type in test['filters']:
            elapsed, count = test_search(test['query'], filter_type)
            if elapsed is not None:
                continue
            results.append({
                'filter': filter_type or 'all',
                'time': elapsed,
                'count': count
            })

        # 性能对比
        if len(results) >= 2:
            print(f"\n📊 性能对比:")
            for r in results:
                filter_name = {
                    'all': '全部',
                    'pdf': '📄 仅PDF',
                    'forum': '💬 仅论坛'
                }.get(r['filter'], r['filter'])

                speedup = ""
                if r['filter'] != 'all':
                    baseline = next(item['time'] for item in results if item['filter'] == 'all')
                    if baseline and r['time'] < baseline:
                        speedup = f"（快{baseline/r['time']:.1f}倍）⚡"
                    elif r['time'] > baseline:
                        speedup = f"（慢{r['time']/baseline:.1f}倍）"

                print(f"  • {filter_name}: {r['time']:.0f} ms {speedup}")

    print(f"\n{'='*70}")
    print(f"✓ 测试完成")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
