"""
多模式提取引擎
支持CSS选择器、XPath、正则表达式、JSONPath等多种提取方式
"""

import re
import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from bs4 import BeautifulSoup
from lxml import etree, html as lxml_html


@dataclass
class ExtractionResult:
    """提取结果"""
    content: Union[str, List[str]]
    method: str
    selector: str
    success: bool
    confidence: float
    error_message: Optional[str] = None
    sample_items: List[str] = None
    extracted_count: int = 0


class MultiModeExtractor:
    """多模式提取器"""
    
    def __init__(self, html: str):
        self.html = html
        self.soup = BeautifulSoup(html, 'html.parser')
        self.lxml_doc = lxml_html.fromstring(html)
        self.results = {}
    
    def extract(
        self,
        selector: str,
        method: str = 'auto',
        extract_attr: str = None,
        extract_all: bool = True
    ) -> ExtractionResult:
        """提取内容"""
        if method == 'auto':
            method = self._detect_method(selector)
        
        if method == 'css':
            return self._extract_css(selector, extract_attr, extract_all)
        elif method == 'xpath':
            return self._extract_xpath(selector, extract_attr, extract_all)
        elif method == 'regex':
            return self._extract_regex(selector, extract_all)
        elif method == 'json':
            return self._extract_json(selector, extract_attr)
        
        return ExtractionResult(
            content='',
            method=method,
            selector=selector,
            success=False,
            confidence=0.0,
            error_message=f'不支持的提取方法: {method}',
            extracted_count=0
        )
    
    def _detect_method(self, selector: str) -> str:
        """自动检测提取方法"""
        if selector.startswith('//') or selector.startswith('/'):
            return 'xpath'
        if selector.startswith('regex:') or selector.startswith('re:'):
            return 'regex'
        if selector.startswith('json:') or selector.startswith('jsonPath:'):
            return 'json'
        return 'css'
    
    def _extract_css(
        self,
        selector: str,
        extract_attr: str = None,
        extract_all: bool = True
    ) -> ExtractionResult:
        """使用CSS选择器提取"""
        try:
            if extract_all:
                elements = self.soup.select(selector)
            else:
                element = self.soup.select_one(selector)
                elements = [element] if element else []
            
            if not elements:
                return ExtractionResult(
                    content=[],
                    method='css',
                    selector=selector,
                    success=True,
                    confidence=0.0,
                    extracted_count=0
                )

            if extract_attr:
                contents = [elem.get(extract_attr, '') for elem in elements if elem.get(extract_attr)]
            else:
                contents = [elem.get_text(strip=True) for elem in elements]

            contents = [c for c in contents if c]
            extracted_count = len(contents)

            return ExtractionResult(
                content=contents if extract_all else (contents[0] if contents else ''),
                method='css',
                selector=selector,
                success=True,
                confidence=min(extracted_count / max(1, len(elements)), 1.0),
                sample_items=contents[:5],
                extracted_count=extracted_count
            )
            
        except Exception as e:
            return ExtractionResult(
                content=[],
                method='css',
                selector=selector,
                success=False,
                confidence=0.0,
                error_message=str(e)
            )
    
    def _extract_xpath(
        self,
        selector: str,
        extract_attr: str = None,
        extract_all: bool = True
    ) -> ExtractionResult:
        """使用XPath提取"""
        try:
            if extract_all:
                elements = self.lxml_doc.xpath(selector)
            else:
                elements = self.lxml_doc.xpath(f'{selector}[1]')
            
            if not elements:
                return ExtractionResult(
                    content=[],
                    method='xpath',
                    selector=selector,
                    success=True,
                    confidence=0.0,
                    extracted_count=0
                )

            if extract_attr:
                contents = [elem.get(extract_attr, '') for elem in elements if hasattr(elem, 'get')]
            else:
                contents = [elem.text_content().strip() for elem in elements if hasattr(elem, 'text_content')]

            contents = [c for c in contents if c]
            extracted_count = len(contents)

            return ExtractionResult(
                content=contents if extract_all else (contents[0] if contents else ''),
                method='xpath',
                selector=selector,
                success=True,
                confidence=min(extracted_count / max(1, len(elements)), 1.0),
                sample_items=contents[:5],
                extracted_count=extracted_count
            )
            
        except Exception as e:
            return ExtractionResult(
                content=[],
                method='xpath',
                selector=selector,
                success=False,
                confidence=0.0,
                error_message=str(e)
            )
    
    def _extract_regex(
        self,
        selector: str,
        extract_all: bool = True
    ) -> ExtractionResult:
        """使用正则表达式提取"""
        try:
            pattern = selector.replace('regex:', '').replace('re:', '')
            matches = re.findall(pattern, self.html)
            
            if not matches:
                return ExtractionResult(
                    content=[],
                    method='regex',
                    selector=pattern,
                    success=True,
                    confidence=0.0,
                    extracted_count=0
                )

            if extract_all:
                contents = matches
                extracted_count = len(matches) if isinstance(matches, list) else 1
            else:
                contents = matches[0]
                extracted_count = 1

            return ExtractionResult(
                content=contents,
                method='regex',
                selector=pattern,
                success=True,
                confidence=1.0,
                sample_items=matches[:5] if isinstance(matches, list) else [str(matches)],
                extracted_count=extracted_count
            )
            
        except Exception as e:
            return ExtractionResult(
                content=[],
                method='regex',
                selector=selector,
                success=False,
                confidence=0.0,
                error_message=str(e)
            )


    def _extract_json(
        self,
        selector: str,
        extract_attr: str = None
    ) -> ExtractionResult:
        """使用 JSONPath 从 JSON 内容提取（json: / jsonPath: 前缀）"""
        expr = selector
        for prefix in ('jsonPath:', 'jsonpath:', 'json:'):
            if expr.lower().startswith(prefix.lower()):
                expr = expr[len(prefix):]
                break
        expr = expr.strip()

        try:
            try:
                data = json.loads(self.html)
            except json.JSONDecodeError as e:
                return ExtractionResult(
                    content=[], method='json', selector=expr,
                    success=False, confidence=0.0,
                    error_message=f'内容不是合法 JSON: {e}'
                )

            try:
                from jsonpath_ng.ext import parse as jsonpath_parse
            except ImportError:
                return ExtractionResult(
                    content=[], method='json', selector=expr,
                    success=False, confidence=0.0,
                    error_message='缺少 jsonpath-ng 依赖: pip install jsonpath-ng'
                )

            try:
                matches = jsonpath_parse(expr).find(data)
            except Exception as e:
                return ExtractionResult(
                    content=[], method='json', selector=expr,
                    success=False, confidence=0.0,
                    error_message=f'JSONPath 表达式错误: {e}'
                )

            values = []
            for m in matches:
                v = m.value
                if extract_attr and isinstance(v, dict):
                    v = v.get(extract_attr, '')
                values.append(v)

            if not values:
                return ExtractionResult(
                    content=[], method='json', selector=expr,
                    success=True, confidence=0.0, extracted_count=0
                )

            samples = [json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list))
                       else str(v) for v in values[:5]]
            return ExtractionResult(
                content=values,
                method='json',
                selector=expr,
                success=True,
                confidence=1.0,
                sample_items=samples,
                extracted_count=len(values)
            )
        except Exception as e:
            return ExtractionResult(
                content=[], method='json', selector=selector,
                success=False, confidence=0.0, error_message=str(e)
            )


# ---------------- CLI ----------------
def _main():
    import argparse, sys, io
    if sys.platform == 'win32':
        if not (isinstance(sys.stdout, io.TextIOWrapper)
                and (sys.stdout.encoding or '').lower().startswith('utf-8')):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    p = argparse.ArgumentParser(description='多模式提取试验（css/xpath/regex/json 自动识别）')
    p.add_argument('--html', required=True, help='已保存的 HTML 或 JSON 文件')
    p.add_argument('--rule', required=True, help='选择器/表达式')
    p.add_argument('--method', default='auto', choices=['auto', 'css', 'xpath', 'regex', 'json'])
    p.add_argument('--attr', default=None, help='提取属性（如 href/src/data-original）')
    p.add_argument('--json', action='store_true', help='输出 JSON（机器可读）')
    args = p.parse_args()

    text = open(args.html, encoding='utf-8', errors='replace').read()
    ex = MultiModeExtractor(text)
    r = ex.extract(args.rule, method=args.method, extract_attr=args.attr)

    if args.json:
        print(json.dumps({
            'method': r.method, 'selector': r.selector, 'success': r.success,
            'extractedCount': r.extracted_count, 'confidence': r.confidence,
            'error': r.error_message, 'samples': r.sample_items or [],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"方法: {r.method}  成功: {r.success}  命中: {r.extracted_count}")
        if r.error_message:
            print(f"错误: {r.error_message}")
        samples = r.sample_items if r.sample_items else []
        if isinstance(r.content, list) and not samples:
            samples = [str(x) for x in r.content[:5]]
        for s in samples:
            print('  -', str(s)[:100])

    # 退出码：0=成功且有命中；2=成功但未命中；1=错误
    if not r.success:
        return 1
    return 0 if r.extracted_count > 0 else 2


if __name__ == '__main__':
    import sys
    sys.exit(_main())
