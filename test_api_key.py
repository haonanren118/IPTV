#!/usr/bin/env python3
"""测试 API_KEY 认证是否正常工作"""

import urllib.request
import json
import os

API_URL = "https://iptv-bfo.pages.dev/api/upload"
# 从环境变量读取 API_KEY，避免硬编码
API_KEY = os.environ.get("API_KEY", "")

def test_upload_without_token():
    """测试1: 不带Token访问上传端点（应该失败）"""
    print("测试1: 不带Token访问上传端点...")
    req = urllib.request.Request(
        API_URL,
        data=b'{"test":true}',
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        },
        method='POST'
    )
    try:
        response = urllib.request.urlopen(req)
        print('❌ 测试1失败: 未授权请求应该被拒绝')
        return False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print('✅ 测试1通过: 未授权请求被拒绝 (401)')
            return True
        else:
            print(f'⚠️ 测试1异常: HTTP {e.code}')
            print(e.read().decode())
            return False

def test_upload_with_wrong_token():
    """测试2: 带错误的Token访问（应该失败）"""
    print("\n测试2: 带错误的Token访问上传端点...")
    req = urllib.request.Request(
        API_URL,
        data=b'{"test":true}',
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0',
            'Authorization': 'Bearer wrong-token'
        },
        method='POST'
    )
    try:
        response = urllib.request.urlopen(req)
        print('❌ 测试2失败: 错误Token应该被拒绝')
        return False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print('✅ 测试2通过: 错误Token被拒绝 (401)')
            return True
        else:
            print(f'⚠️ 测试2异常: HTTP {e.code}')
            return False

def test_upload_with_correct_token():
    """测试3: 带正确的Token访问（应该成功）"""
    if not API_KEY:
        print("\n❌ 测试3跳过: 未设置 API_KEY 环境变量")
        return False
    
    print("\n测试3: 带正确的Token访问上传端点...")
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
        if result.get('status') == 'success':
            print('✅ 测试3通过: 正确Token上传成功')
            print(f"   消息: {result.get('message')}")
            print(f"   更新时间: {result.get('last_update')}")
            return True
        else:
            print(f'❌ 测试3失败: {result}')
            return False
    except urllib.error.HTTPError as e:
        print(f'❌ 测试3失败: HTTP {e.code}')
        print(e.read().decode())
        return False

def test_status_endpoint():
    """测试4: 状态端点（不需要认证）"""
    print("\n测试4: 访问状态端点...")
    req = urllib.request.Request(
        'https://iptv-bfo.pages.dev/api/status',
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode())
        print('✅ 测试4通过: 状态端点正常')
        print(f"   状态: {result.get('status')}")
        print(f"   版本: {result.get('version')}")
        print(f"   平台: {result.get('platform')}")
        print(f"   最后更新: {result.get('last_update')}")
        return True
    except Exception as e:
        print(f'❌ 测试4失败: {e}')
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("API_KEY 认证测试")
    print("=" * 50)
    print(f"API URL: {API_URL}")
    if API_KEY:
        print(f"API KEY: {API_KEY[:4]}...{API_KEY[-4:]}")
    else:
        print("API KEY: 未设置 (请设置 API_KEY 环境变量)")
    print("=" * 50)

    results = []
    results.append(test_upload_without_token())
    results.append(test_upload_with_wrong_token())
    results.append(test_upload_with_correct_token())
    results.append(test_status_endpoint())

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"测试结果: {passed}/{total} 通过")
    if passed == total:
        print("🎉 所有测试通过! API_KEY 认证工作正常")
    else:
        print("⚠️ 部分测试失败，请检查配置")
    print("=" * 50)
