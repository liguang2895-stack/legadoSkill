"""
规则验证和优化引擎
验证选择器和规则的正确性，优化性能，提供改进建议
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from bs4 import BeautifulSoup
from lxml import etree, html as lxml_html

# Legado 规则尾段 action 白名单（AnalyzeByJSoup.getResultLast 支持的关键字）
LEGADO_ACTIONS = {"text", "textNodes", "ownText", "html", "all",
                  "href", "src", "value", "content", "outerHtml"}


def strip_legado_rule(rule: str, rule_type: str) -> str:
    """从 Legado 规则中剥离选择器部分。

    只剥离**末尾**的合法 action（如 ".box a@text" -> ".box a"），
    不碰 XPath 属性谓词里的 @（如 '//div[@class="x"]/a'）。

    前缀处理：
      @css: / @CSS:  -> 去掉前缀
      @XPath:        -> 去掉前缀
    """
    rule = rule.strip()
    # 去前缀
    for prefix in ("@css:", "@CSS:", "@Css:"):
        if rule.startswith(prefix):
            rule = rule[len(prefix):]
            break
    for prefix in ("@xpath:", "@XPath:"):
        if rule.startswith(prefix):
            rule = rule[len(prefix):]
            break

    if rule_type == "regex":
        # 正则在 ## 之后
        if "##" in rule:
            return rule.split("##", 1)[1]
        return rule

    # css / xpath：只剥末尾合法 action
    m = re.search(r"@([A-Za-z][A-Za-z0-9_]*)\s*$", rule)
    if m and m.group(1) in LEGADO_ACTIONS:
        return rule[:m.start()].strip()
    # ## 之后是正则段，选择器在 ## 之前
    if "##" in rule:
        rule = rule.split("##", 1)[0]
    return rule.strip()


@dataclass
class ValidationIssue:
    """验证问题"""
    severity: str  # error, warning, info
    type: str
    message: str
    location: str
    suggestion: str


class RuleValidator:
    """规则验证器"""
    
    def __init__(self, html: str):
        self.html = html
        self.soup = BeautifulSoup(html, 'html.parser')
        self.lxml_doc = lxml_html.fromstring(html)
        self.issues = []
        self.suggestions = []
    
    def validate_rule(
        self,
        rule_type: str,
        rule_value: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """验证规则"""
        context = context or {}
        
        validation_result = {
            'rule_type': rule_type,
            'rule_value': rule_value,
            'valid': True,
            'issues': [],
            'suggestions': [],
            'test_results': {}
        }
        
        if rule_type == 'css':
            validation_result.update(self._validate_css(rule_value, context))
        elif rule_type == 'xpath':
            validation_result.update(self._validate_xpath(rule_value, context))
        elif rule_type == 'regex':
            validation_result.update(self._validate_regex(rule_value, context))
        
        return validation_result
    
    def _validate_css(self, selector: str, context: Dict) -> Dict:
        """验证CSS选择器"""
        result = {'valid': True, 'issues': []}
        
        if not selector or not selector.strip():
            result['valid'] = False
            result['issues'].append({
                'severity': 'error',
                'type': 'empty_selector',
                'message': 'CSS选择器不能为空',
                'suggestion': '请提供有效的CSS选择器'
            })
            return result
        
        try:
            elements = self.soup.select(selector)
        except Exception as e:
            result['valid'] = False
            result['issues'].append({
                'severity': 'error',
                'type': 'syntax_error',
                'message': f'CSS选择器语法错误: {str(e)}',
                'suggestion': '请检查选择器语法'
            })
            return result
        
        if not elements:
            result['issues'].append({
                'severity': 'warning',
                'type': 'no_match',
                'message': '选择器未匹配到任何元素',
                'suggestion': '请检查选择器是否正确'
            })
        
        return result
    
    def _validate_xpath(self, xpath: str, context: Dict) -> Dict:
        """验证XPath"""
        result = {'valid': True, 'issues': []}
        
        if not xpath or not xpath.strip():
            result['valid'] = False
            result['issues'].append({
                'severity': 'error',
                'type': 'empty_xpath',
                'message': 'XPath不能为空',
                'suggestion': '请提供有效的XPath表达式'
            })
            return result
        
        try:
            elements = self.lxml_doc.xpath(xpath)
        except Exception as e:
            result['valid'] = False
            result['issues'].append({
                'severity': 'error',
                'type': 'syntax_error',
                'message': f'XPath语法错误: {str(e)}',
                'suggestion': '请检查XPath语法'
            })
            return result
        
        if not elements:
            result['issues'].append({
                'severity': 'warning',
                'type': 'no_match',
                'message': 'XPath未匹配到任何元素',
                'suggestion': '请检查XPath是否正确'
            })
        
        return result
    
    def _validate_regex(self, pattern: str, context: Dict) -> Dict:
        """验证正则表达式"""
        result = {'valid': True, 'issues': []}
        
        if not pattern or not pattern.strip():
            result['valid'] = False
            result['issues'].append({
                'severity': 'error',
                'type': 'empty_pattern',
                'message': '正则表达式不能为空',
                'suggestion': '请提供有效的正则表达式'
            })
            return result
        
        try:
            re.compile(pattern)
        except Exception as e:
            result['valid'] = False
            result['issues'].append({
                'severity': 'error',
                'type': 'syntax_error',
                'message': f'正则表达式语法错误: {str(e)}',
                'suggestion': '请检查正则表达式语法'
            })
            return result
        
        matches = re.findall(pattern, self.html)
        if not matches:
            result['issues'].append({
                'severity': 'warning',
                'type': 'no_match',
                'message': '正则表达式未匹配到任何内容',
                'suggestion': '请检查正则表达式是否正确'
            })
        
        return result


# ---------------- CLI ----------------
def _main():
    import argparse, sys, io
    if sys.platform == 'win32':
        if not (isinstance(sys.stdout, io.TextIOWrapper)
                and (sys.stdout.encoding or '').lower().startswith('utf-8')):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    p = argparse.ArgumentParser(description='验证选择器/正则是否命中已保存的 HTML')
    p.add_argument('--html', required=True, help='已保存的 HTML 文件')
    p.add_argument('--type', default='css', choices=['css', 'xpath', 'regex'])
    p.add_argument('--rule', required=True,
                   help='规则，如 ".box a@text"（自动剥离 Legado 尾段 action）')
    p.add_argument('--json', action='store_true', help='输出 JSON（机器可读）')
    args = p.parse_args()

    try:
        html = open(args.html, encoding='utf-8', errors='replace').read()
    except OSError as e:
        print(f"读取 HTML 失败: {e}", file=sys.stderr)
        return 2

    rule = strip_legado_rule(args.rule, args.type)
    v = RuleValidator(html)
    r = v.validate_rule(args.type, rule)

    # 统计命中
    hits = 0
    preview = []
    syntax_error = any(i.get('severity') == 'error' for i in r.get('issues', []))
    if not syntax_error:
        try:
            if args.type == 'css':
                els = v.soup.select(rule)
                hits = len(els)
                preview = [(e.get_text(strip=True) or str(e))[:80] for e in els[:5]]
            elif args.type == 'xpath':
                els = v.lxml_doc.xpath(rule)
                hits = len(els)
                preview = [((e.text_content().strip() if hasattr(e, 'text_content')
                             else str(e))[:80]) for e in els[:5]]
            else:
                ms = re.findall(rule, html)
                hits = len(ms)
                preview = [str(m)[:80] for m in ms[:5]]
        except Exception as e:
            syntax_error = True
            r.setdefault('issues', []).append({
                'severity': 'error', 'type': 'runtime_error',
                'message': f'规则执行失败: {e}', 'suggestion': '检查规则语法',
            })

    result = {
        'ruleType': args.type,
        'inputRule': args.rule,
        'selector': rule,
        'valid': not syntax_error,
        'hitCount': hits,
        'preview': preview,
        'issues': r.get('issues', []),
    }

    # 退出码：0=命中；2=语法有效但未命中；1=语法错误
    if syntax_error:
        exit_code = 1
    elif hits == 0:
        exit_code = 2
    else:
        exit_code = 0

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"规则[{args.type}]: {rule}")
        print(f"有效: {result['valid']}")
        for i in result['issues']:
            print(f"  [{i.get('severity','info')}] {i.get('message')} -> {i.get('suggestion','')}")
        if not syntax_error:
            print(f"命中 {hits} 个")
            for s in preview:
                print('  -', s)

    return exit_code


if __name__ == '__main__':
    import sys
    sys.exit(_main())
