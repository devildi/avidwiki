#!/usr/bin/env python3
import requests
import json

# 测试流式端点
url = "http://localhost:8000/search/stream"
payload = {
    "query": "Avid Media Composer",
    "limit": 5,
    "llm_provider": "local"
}

print("测试 /search/stream 端点...")
try:
    response = requests.post(url, json=payload, stream=True, timeout=10)
    print(f"状态码: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print("\n响应内容（前500字符）:")

    count = 0
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            print(decoded_line)
            count += 1
            if count >= 10:  # 只打印前10行
                print("... (后续内容省略)")
                break

    if response.status_code != 200:
        print(f"\n错误响应: {response.text}")

except Exception as e:
    print(f"请求失败: {e}")
    import traceback
    traceback.print_exc()
