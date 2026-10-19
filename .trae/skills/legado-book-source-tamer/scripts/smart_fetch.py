"""
智能请求工具
支持各种HTTP请求方法，确保用正确的方式获取真实内容
"""

import requests
import json
import re
import chardet
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urlencode


class SmartRequest:
    """智能请求工具"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def _detect_encoding(self, response: requests.Response, charset: Optional[str] = None) -> str:
        """
        智能检测响应编码
        
        优先级：
        1. 用户指定的 charset 参数
        2. HTTP Content-Type header 中的 charset
        3. HTML meta 标签中的 charset
        4. chardet 库检测
        5. 默认 utf-8
        """
        if charset:
            charset_lower = charset.lower()
            if charset_lower in ['gbk', 'gb2312', 'gb18030']:
                return 'gbk'
            elif charset_lower in ['utf-8', 'utf8']:
                return 'utf-8'
            else:
                return charset_lower
        
        content_type = response.headers.get('Content-Type', '')
        if 'charset=' in content_type:
            match = re.search(r'charset=([^\s;]+)', content_type, re.IGNORECASE)
            if match:
                detected = match.group(1).strip('"\'').lower()
                if detected in ['gbk', 'gb2312', 'gb18030']:
                    return 'gbk'
                elif detected in ['utf-8', 'utf8']:
                    return 'utf-8'
                return detected
        
        try:
            content_preview = response.content[:2048].decode('latin-1', errors='ignore')
            meta_patterns = [
                r'<meta\s+charset=["\']?([^"\'>\s]+)',
                r'<meta\s+http-equiv=["\']?content-type["\']?\s+content=["\']?[^"\']*charset=([^"\'>\s;]+)',
            ]
            for pattern in meta_patterns:
                match = re.search(pattern, content_preview, re.IGNORECASE)
                if match:
                    detected = match.group(1).lower()
                    if detected in ['gbk', 'gb2312', 'gb18030']:
                        return 'gbk'
                    elif detected in ['utf-8', 'utf8']:
                        return 'utf-8'
                    return detected
        except Exception:
            pass
        
        try:
            detected = chardet.detect(response.content)
            if detected and detected.get('encoding'):
                encoding = detected['encoding'].lower()
                confidence = detected.get('confidence', 0)
                if confidence > 0.7:
                    if encoding in ['gbk', 'gb2312', 'gb18030']:
                        return 'gbk'
                    elif encoding in ['utf-8', 'utf8']:
                        return 'utf-8'
                    return encoding
        except Exception:
            pass
        
        return 'utf-8'
    
    def fetch(
        self,
        url: str,
        method: str = 'GET',
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict, str, bytes]] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        allow_redirects: bool = True,
        verify_ssl: bool = True,
        charset: Optional[str] = None,
        url_charset: Optional[str] = None,
        encoded_data: Optional[str] = None,
        encoded_params: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送HTTP请求（支持所有方法）"""
        final_headers = self.default_headers.copy()
        if headers:
            final_headers.update(headers)
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=final_headers,
                    cookies=cookies,
                    allow_redirects=allow_redirects,
                    verify=verify_ssl,
                    timeout=self.timeout
                )
                
                detected_encoding = self._detect_encoding(response, charset)
                
                try:
                    html_text = response.content.decode(detected_encoding, errors='replace')
                except (UnicodeDecodeError, LookupError):
                    html_text = response.content.decode('utf-8', errors='replace')
                    detected_encoding = 'utf-8'
                
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'url': response.url,
                    'method': method.upper(),
                    'headers': dict(response.headers),
                    'cookies': dict(response.cookies),
                    'encoding': detected_encoding,
                    'html': html_text,
                    'content': response.content,
                    'size': len(response.content),
                    'redirect_count': len(response.history),
                    'final_url': response.url,
                    'is_real': True
                }
                
            except requests.exceptions.Timeout:
                last_error = f"请求超时（{self.timeout}秒）"
            except requests.exceptions.ConnectionError:
                last_error = "连接错误"
            except requests.exceptions.SSLError as e:
                last_error = f"SSL错误: {str(e)}"
            except Exception as e:
                last_error = str(e)
        
        return {
            'success': False,
            'error': last_error,
            'url': url,
            'method': method.upper()
        }


# ---------------- CLI ----------------
def _main():
    import argparse, sys, io, warnings
    warnings.filterwarnings('ignore')
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    p = argparse.ArgumentParser(description='智能抓取工具：编码检测 + GET/POST 抓取真实 HTML')
    p.add_argument('url', nargs='?', help='目标 URL')
    p.add_argument('--detect', action='store_true', help='仅检测编码，不抓取')
    p.add_argument('--method', default='GET', choices=['GET', 'POST'], help='HTTP 方法')
    p.add_argument('--body', default=None, help='POST 请求体，如 "searchkey={{key}}"（原样发送）')
    p.add_argument('--header', action='append', default=[], help='附加请求头，格式 "Key: Value"，可多次')
    p.add_argument('--charset', default=None, help='强制指定编码（gbk/utf-8）')
    p.add_argument('--save', default=None, help='把 HTML 保存到指定文件')
    p.add_argument('--max', type=int, default=200000, help='终端预览字符数上限')
    args = p.parse_args()

    if not args.url:
        p.error('需要 URL')

    tool = SmartRequest()
    headers = {}
    for h in args.header:
        if ':' in h:
            k, v = h.split(':', 1)
            headers[k.strip()] = v.strip()

    if args.detect:
        import requests as _rq
        resp = _rq.get(args.url, headers={**tool.default_headers, **headers},
                       timeout=tool.timeout, verify=False)
        enc = tool._detect_encoding(resp, args.charset)
        print(f"URL: {args.url}")
        print(f"HTTP {resp.status_code}, Content-Type: {resp.headers.get('Content-Type','')}")
        print(f"检测编码: {enc}")
        print(f"书源配置建议: {'无需配置 charset' if enc == 'utf-8' else '\"charset\":\"' + enc + '\"'}")
        return

    result = tool.fetch(
        url=args.url, method=args.method,
        data=args.body if args.method == 'POST' else None,
        headers=headers or None, charset=args.charset, verify_ssl=False,
    )
    if not result.get('success'):
        print(f"[失败] {result.get('error')}")
        sys.exit(1)
    print(f"[成功] HTTP {result['status_code']}  编码: {result['encoding']}  大小: {result['size']}B")
    print(f"最终URL: {result['final_url']}")
    if args.save:
        with open(args.save, 'w', encoding='utf-8') as f:
            f.write(result['html'])
        print(f"HTML 已保存: {args.save}")
    else:
        print('---- HTML 预览（截断） ----')
        print(result['html'][:args.max])
        print(f'...（共 {len(result["html"])} 字符，用 --save 保存完整内容）')


if __name__ == '__main__':
    _main()
