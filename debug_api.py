#!/usr/bin/env python3
"""调试 API 认证问题"""

import urllib.request
import json
import os

API_URL = "https://iptv-bfo.pages.dev/api/upload"
# 从环境变量读取 API_KEY，避免硬编码
API_KEY = os.environ.get("API_KEY", "")

def test_with_debug():
    """测试并显示详细响应"""
    if not API_KEY:
        print("❌ 错误: 未设置 API_KEY 环境变量")
        print("请设置: export API_KEY=your-api-key")
        return
    
    print("测试带正确 Token 的请求...")
    print(f"URL: {API_URL}")
    print(f"Authorization: Bearer {API_KEY[:4]}...{API_KEY[-4:]}")
    print()
    
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({
            "m3u8": "#EXTM3U\n#EXTINF:-1,Test\nhttp://test.com/stream.m3u8",
            "txt": "测试频道,http://test.com/stream.m3u8",
            "last_update": "2026/05/25 12:00:00"
        }).encode(),
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0',
            'Authorization': f'Bearer {API_KEY}'
        },
        method='POST'
    )
    
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode())
        print(f"✅ 成功! 状态码: {response.status}")
        print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    except urllib.error.HTTPError as e:
        print(f"❌ 失败! 状态码: {e.code}")
        try:
            error_body = e.read().decode()
            print(f"错误响应: {error_body}")
        except:
            print(f"错误: {e}")

if __name__ == "__main__":
    test_with_debug()
