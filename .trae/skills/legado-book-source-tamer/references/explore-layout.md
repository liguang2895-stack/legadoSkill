# 发现页（exploreUrl）布局规范

> 来源：Legado 源码实测（`ExploreAdapter.kt` / `FlexChildStyle.kt` / `item_fillet_text.xml`）。
> 目标：让生成的发现页**整齐、两列对齐、分组清晰**，而不是大小不一的散排 chips。

## 一、渲染机制（必须理解的真相）

Legado 发现页把 `exploreUrl` 返回的 JSON 数组渲染成**单行 Flexbox 流式布局**：

| 事实 | 说明 |
|------|------|
| 每个条目 = 一个圆角按钮（chip） | 默认 `wrap_content` 宽度 + 左右 12dp padding + margin 3dp |
| **只有 `style` 里的 `layout_*` 字段生效** | `FlexChildStyle` 只有 6 个字段：`layout_flexGrow` / `layout_flexShrink` / `layout_alignSelf` / `layout_flexBasisPercent` / `layout_wrapBefore` / `layout_justifySelf` |
| **`textAlign` / `fontWeight` 是无效字段** | 不存在的字段被静默忽略（GSON 宽松解析），写了不报错但**没有任何效果**。别再写！ |
| 行内对齐靠 `layout_justifySelf` | `flex_start`=左、`flex_end`=右、其他/不写=居中（Type.url 默认居中） |
| 不写 `style` 的条目 | 宽度随文字长度变化 → **这就是"不整齐"的根源** |
| 容器间隔 | flexbox 自带 `showDivider=middle`，divider 宽 8dp；item 自身 margin 3dp |

## 二、布局规范（照抄即可）

### 1. 分组标题（分区标题）

```json
{"title": "周点击", "url": "", "style": {"layout_flexBasisPercent": 1.0, "layout_justifySelf": "center"}}
```

- **必须写 `layout_flexBasisPercent: 1.0`** → 占满整行，独立成行。
- `url: ""` 是分组标题的标准写法（点击无动作）。
- 对齐：`center`（居中）或 `flex_start`（左对齐）；**推荐 center，与按钮区形成层次**。

### 2. 两列按钮（最常用、最整齐）

```json
{"title": "玄幻奇幻", "url": "/sort/1/{{page}}.html", "style": {"layout_flexBasisPercent": 0.45}}
```

- **`0.45` 是两列的黄金值**：两列 0.45 + 3 个 margin(3dp) + 1 个 divider(8dp) ≈ 305dp ≤ 320dp 最小屏宽，安全不换行。
- 用 `0.5` 会溢出（337dp）→ 第二列被挤到下一行，出现"假两列"。**不要用 0.5**。

### 3. 三列按钮（分类很多时）

```json
{"style": {"layout_flexBasisPercent": 0.29}}
```

- 三列用 `0.29`（306dp 安全）；`0.33` 会溢出（345dp）。

### 4. 四列按钮（短词分类，如"全部/男频/女频"）

```json
{"style": {"layout_flexBasisPercent": 0.2}}
```

- 四列用 `0.2`（295dp 安全）；`0.25` 会溢出。

### 5. 单行通栏按钮（"全本""排行榜"等单入口）

```json
{"style": {"layout_flexBasisPercent": 1.0, "layout_justifySelf": "center"}}
```

### 6. 强制换行

需要在某个条目**之前**强制换行（如标题后第一个按钮、奇数个按钮补行）：

```json
{"style": {"layout_wrapBefore": true, "layout_flexBasisPercent": 0.45}}
```

### 7. 固定宽度不参与拉伸

```json
{"style": {"layout_flexGrow": 0, "layout_flexBasisPercent": -1}}
```

- `flexBasisPercent: -1` = 不指定百分比（退回 wrap_content）。一般不需要写。

## 三、黄金模板（JS 生成器）

> 生成任何书源的发现页时，**直接套用这个骨架**，只替换 `cats` / `tops` / URL 前缀。

```js
@js:
// ===== 配置区：替换为目标站真实分类 =====
var cats = [
  ["玄幻奇幻", "1"], ["都市青春", "2"], ["武侠仙侠", "3"], ["历史军事", "4"],
  ["女生言情", "5"], ["网游竞技", "6"], ["都市激情", "7"], ["综合其他", "8"]
];
var tops = [
  ["周点击", "weekvisit"], ["月点击", "monthvisit"], ["总点击", "allvisit"],
  ["周推荐", "weekvote"], ["月推荐", "monthvote"], ["总推荐", "allvote"]
];
// URL 前缀（按目标站真实路径替换）
var sortUrl = "/sort/";        // 分类页
var topUrl = "/top/";          // 榜单页
var sortSuffix = "/{{page}}.html";
var topSuffix = "/{{page}}.html";

// ===== 骨架：分组标题 + 两列按钮 =====
var fil = [];
var TITLE = function (t) {
    return {title: t, url: "", style: {layout_flexBasisPercent: 1.0, layout_justifySelf: "center"}};
};
var BTN2 = function (t, u) {
    return {title: t, url: u, style: {layout_flexBasisPercent: 0.45}};
};
var FULL = function (t, u) {
    return {title: t, url: u, style: {layout_flexBasisPercent: 1.0, layout_justifySelf: "center"}};
};
var i;

// 一、分类区（两列）
fil.push(TITLE("分类"));
for (i = 0; i < cats.length; i++) {
    fil.push(BTN2(cats[i][0], sortUrl + cats[i][1] + sortSuffix));
}

// 二、排行榜（两列）
fil.push(TITLE("排行榜"));
for (i = 0; i < tops.length; i++) {
    fil.push(BTN2(tops[i][0], topUrl + tops[i][1] + topSuffix));
}

// 三、单入口（通栏）
fil.push(FULL("全本", "/modules/article/toplist.php?fullflag=1&page={{page}}"));

JSON.stringify(fil);
```

## 四、进阶：筛选矩阵（排序 × 分类）

> 当站点支持「排序参数 + 分类参数」组合筛选（如八叉书库 `articlefilter.php?order=X&sortid=Y`），
> 可生成「每个排序分区下挂全部分类」的矩阵。**注意条目会非常多**（15 排序 × 20 分类 = 300 条），
> 只在站点筛选体系确实丰富时使用；否则用第三节的黄金模板。

```js
// 排序分区 + 分类矩阵（每行 2 列）
for (i = 0; i < ord.length; i++) {
    fil.push(TITLE(ord[i][0]));
    for (j = 0; j < cat.length; j++) {
        fil.push(BTN2(cat[j][0], "/modules/article/articlefilter.php?order=" + ord[i][1]
            + "&page={{page}}" + (cat[j][1] !== "" ? "&sortid=" + cat[j][1] : "")));
    }
}
```

## 五、反面清单（这些写法导致不整齐）

| ❌ 错误写法 | 后果 |
|-----------|------|
| 不写 `style` | 按钮宽度随文字变化，参差不齐 |
| `{"layout_flexBasisPercent": 0.5}` 两列 | 溢出换行，出现"假两列" |
| `{"layout_flexBasisPercent": 0.33}` 三列 | 溢出换行 |
| 分组标题不写 `flexBasisPercent: 1.0` | 标题只占一格宽度，和按钮混排 |
| 写 `textAlign` / `fontWeight` / `textSize` | 无效字段，被静默忽略（白写） |
| 分组标题写了真实 URL | 点击后进入一个奇怪的列表，失去"标题"语义 |
| 全部条目都写 `flexBasisPercent: 1.0` | 每个按钮独占一行，浪费空间 |

## 六、进阶：交互控件（select / button / toggle / text）

> 除 `url` 类型外，条目还能做成**交互控件**，点击后执行 `action` JS。
> 适合：筛选器（排序/状态/字数）、搜索框、折叠开关。

### 6.1 控件类型一览（ExploreKind.Type）

| type | 渲染 | 交互 | 必须字段 |
|------|------|------|---------|
| `url`（默认） | 圆角按钮 | 点击打开 url | `url` |
| `button` | 圆角按钮 | 点击执行 `action` JS | `action` |
| `toggle` | 圆角按钮 | **点击循环切换** `chars` 里的值 | `chars` |
| `select` | 下拉框 | 选择后执行 `action` JS | `chars` |
| `text` | 输入框 | 用户输入（值自动存入 infoMap） | — |

### 6.2 关键机制（源码实测）

- **`infoMap[title]` 自动存取**：`select`/`toggle`/`text` 控件的值按 `title` 自动存入 `infoMap`，action JS 里可用 `infoMap['标题']` 读取。
- **action JS 的绑定**：`source`（BaseSource，有 `getVariable`/`setVariable`）、`java`（SourceLoginJsExtensions，有 `refreshExplore()`/`toast()`/`searchBook()`/`getSource()`/`put()`/`get()`）、`infoMap`。
- **刷新发现页**：action 里调 `java.refreshExplore()` 会重新执行 exploreUrl JS（读取新状态重绘）。这是**折叠/筛选的核心机制**。
- **`viewName` 动态标题**：设 `viewName` 为 JS 字符串（或 `'固定文本'` 形式），标题会异步求值显示（如显示当前筛选状态）。
- **状态持久化**：exploreUrl JS 和 action JS 里都可用 `source.getVariable()` / `source.setVariable()` 读写 JSON 状态。

### 6.3 模式 A：下拉筛选器（select + 状态保存）

> 效果：一个下拉框（频道/排序/状态），选择后刷新发现页并按新条件重绘。

```js
// exploreUrl JS 中：
var cfg = {};
try { cfg = JSON.parse(String(source.getVariable() || '{}')) || {}; } catch (e) {}

var SORT = [['按热度','0'],['按更新','1'],['按评分','2']];
var cur = cfg.sort || '0';
function label(opts, v) { return (opts.filter(function(o){return o[1]==v;})[0]||opts[0])[0]; }

var fil = [];
// 下拉框：chars 是选项文本，default 是当前值
fil.push({
    title: '排序',
    type: 'select',
    chars: SORT.map(function(o){ return o[0]; }),
    default: label(SORT, cur),
    action: "(function(){var c={};try{c=JSON.parse(String(source.getVariable()||'{}'))||{};}catch(e){}"
          + "var m=" + JSON.stringify((function(){var x={};SORT.forEach(function(o){x[o[0]]=o[1];});return x;})()) + ";"
          + "c.sort=m[String(infoMap['排序'])]||'0';"
          + "source.setVariable(JSON.stringify(c));java.refreshExplore();})()",
    style: {layout_flexBasisPercent: 1.0}
});
// 用当前筛选值生成列表 URL
var sortVal = cur;
fil.push({title: '玄幻', url: '/list?sort=' + sortVal + '&page={{page}}', style: {layout_flexBasisPercent: 0.45}});
JSON.stringify(fil);
```

要点：
- `chars` 只能是字符串数组；选项的**显示文本**即 `infoMap` 里的值。
- action 里先读状态 JSON → 改字段 → 写回 → `java.refreshExplore()`。
- `default` 要与 `chars` 中的某项**完全一致**才会选中。

### 6.4 模式 B：toggle 循环切换（轻量筛选）

> 效果：点一下按钮循环切换 开/关 或 多个档位，比 select 更省空间。

```js
var ON = ['仅免费', '全部'];
var cur = cfg.free || '全部';
fil.push({
    title: '范围',           // 显示为 "范围: 仅免费"（前缀可自定义）
    type: 'toggle',
    chars: ON,
    default: cur,
    action: "var c={};try{c=JSON.parse(String(source.getVariable()||'{}'))||{};}catch(e){}"
          + "c.free=String(infoMap['范围']);"
          + "source.setVariable(JSON.stringify(c));java.refreshExplore();",
    style: {layout_flexBasisPercent: 0.45}
});
```

要点：toggle 点击时**自动**把 `chars` 里的下一项写入 `infoMap[title]`，action 只需读取并保存。显示文本为 `"值 + title"` 拼接。

### 6.5 模式 C：搜索框（text + button）

```js
fil.push({title: '关键字', type: 'text', default: '', style: {layout_flexBasisPercent: 0.45}});
fil.push({
    title: '🔍 搜索', type: 'button',
    action: "var k=infoMap['关键字']; if(k && String(k).replace(/\\s/g,'')){ java.searchBook(String(k).replace(/^\\s+|\\s+$/g,''), java.getSource()); } else { java.toast('请输入关键字'); }",
    style: {layout_flexBasisPercent: 0.45}
});
```

要点：`text` 控件的输入值实时同步到 `infoMap['关键字']`；`java.searchBook(key, source)` 发起书源搜索。

## 七、进阶：折叠分组（▸/▾）

> 效果：分组标题可点击展开/收起，收起时只显示标题行。适合分类非常多（十几个组）的站点。

### 7.1 机制

- 每个组的展开状态存在书源变量 JSON 里（`open` 字段）。
- 标题用 **`type: 'button'`**（不是 `url`），action 切换该组的 `open` 状态并 `java.refreshExplore()`。
- exploreUrl JS 每次重绘时读取 `open` 状态：展开的组才 push 其分类按钮。

### 7.2 模板

```js
// exploreUrl JS 中：
var cfg = {};
try { cfg = JSON.parse(String(source.getVariable() || '{}')) || {}; } catch (e) {}
var open = cfg.open || {};

var fil = [];
// 折叠组：标题行（button）+ 展开时的内容
function group(name, defOpen, items) {
    var isOpen = (name in open) ? !!open[name] : defOpen;
    fil.push({
        title: (isOpen ? '▾ ' : '▸ ') + name + '（' + items.length + '）',
        type: 'button',
        action: "(function(){var c={};try{c=JSON.parse(String(source.getVariable()||'{}'))||{};}catch(e){}"
              + "var o=c.open||{};o[" + JSON.stringify(name) + "]=" + (isOpen ? 0 : 1) + ";"
              + "c.open=o;source.setVariable(JSON.stringify(c));java.refreshExplore();})()",
        style: {layout_flexBasisPercent: 1.0, layout_justifySelf: 'flex_start'}
    });
    if (isOpen) {
        items.forEach(function (it) {
            fil.push({title: it[0], url: it[1], style: {layout_flexBasisPercent: 0.45}});
        });
    }
}

// 用法：分类多的站按题材分组
group('玄幻奇幻', true, [['东方玄幻','/sort/1/{{page}}.html'], ['异世大陆','/sort/2/{{page}}.html']]);
group('都市青春', false, [['都市生活','/sort/3/{{page}}.html'], ['青春校园','/sort/4/{{page}}.html']]);

// 最后保存状态（可选，用于持久化）
cfg.open = open;
source.setVariable(JSON.stringify(cfg));
JSON.stringify(fil);
```

要点：
- 标题前缀 `▾`（展开）/ `▸`（收起）是视觉提示，**必须放在 title 里**（Legado 无内置箭头）。
- 组标题建议 `layout_justifySelf: 'flex_start'`（左对齐更像列表项），也可用 `center`。
- 默认第一个组展开（`defOpen=true`），其余收起，页面首屏不至于太长。

## 八、进阶：等宽格子（自适应列宽 + 空位补齐）

> 效果：短标签 4 列、长标签 3 列混排，每行严格对齐、末尾用空位补齐——适合标签长度差异大的站。

### 8.1 机制

纯 JS 计算：按文字宽度算每个标签占几格（span），按行打包（pack），每行不足的用**全角空格**按钮补齐。`layout_flexGrow: span` 让按钮吃掉对应比例的宽度。

### 8.2 模板（可直接复用）

```js
// ===== 等宽格子布局工具 =====
var LAYOUT = {gap: 0.042, pad: 0.068, ch: 0.0368, shortMax: 3.3};
function textWidth(t) {
    var w = 0;
    for (var i = 0; i < t.length; i++) {
        var c = t.charCodeAt(i);
        if (c == 32) w += 0.32;           // 半角空格
        else if (c < 128) w += 0.65;      // ASCII
        else if (c == 0xB7) w += 0.5;     // ·
        else if (c == 0x25CF) w += 0.9;   // ●
        else w += 1;                      // 全角字符
    }
    return w;
}
function pack(items, cols) {
    cols = cols || 4;
    var g = LAYOUT.gap, cell = (1 - g * (cols - 1)) / cols;
    var fit = (cell - LAYOUT.pad) / LAYOUT.ch;
    var queue = items.map(function (it) {
        return {it: it, span: Math.min(cols, Math.ceil(textWidth(it.title) / fit) || 1)};
    });
    var out = [];
    while (queue.length) {
        var row = [], left = cols;
        while (queue.length && left > 0) {
            var k = 0;
            while (k < queue.length && queue[k].span > left) k++;
            if (k == queue.length) break;
            var x = queue.splice(k, 1)[0];
            row.push(x); left -= x.span;
        }
        for (; left > 0; left--) row.push({it: {title: '　', url: ''}, span: 1});  // 空位补齐
        row.forEach(function (x, i) {
            var st = {layout_flexGrow: x.span,
                      layout_flexBasisPercent: Math.round((x.span / (cols + 1) + (x.span - 1) * g) * 1e4) / 1e4};
            if (i == 0) st.layout_wrapBefore = true;  // 每行首个强制换行
            x.it.style = st;
            out.push(x.it);
        });
    }
    return out;
}

// ===== 用法 =====
var fil = [];
var shortTags = [], longTags = [];
// 按标题宽度分短/长
myTags.forEach(function (t) {
    var it = {title: t[0], url: t[1]};
    (textWidth(t[0]) > LAYOUT.shortMax ? longTags : shortTags).push(it);
});
fil = fil.concat(pack(shortTags, 4));   // 短标签 4 列
fil = fil.concat(pack(longTags, 3));    // 长标签 3 列
JSON.stringify(fil);
```

要点：
- `layout_wrapBefore: true` 用在**每行第一个**按钮上，强制换行保证网格对齐。
- 空位补齐按钮 `{title: '　', url: ''}` 用**全角空格**（不是普通空格），保证等宽。
- 这套算法来自社区实战源（七猫/轻之国度），参数 `LAYOUT` 已调优，可直接用。

## 九、自检清单（生成发现页后必查）

- [ ] 每个分组标题都带 `layout_flexBasisPercent: 1.0`
- [ ] 两列按钮统一 `0.45`；三列 `0.29`；四列 `0.2`
- [ ] 没有写 `textAlign` / `fontWeight`（无效字段）
- [ ] 同一分组内按钮数量为偶数（两列时避免最后一行单个按钮；奇数时给最后一个补 `layout_wrapBefore` 或改用通栏）
- [ ] 分组标题的 `url` 为空字符串 `""`
- [ ] JS 用 `var` + 传统函数（Rhino 兼容），输出 `JSON.stringify(fil)`
- [ ] 输出的数组元素只含 `title` / `url` / `style` 三个键（交互控件加 `type` / `action` / `chars` / `default`）
- [ ] 交互控件（select/toggle/button）的 action 里用 `java.refreshExplore()` 刷新
- [ ] 折叠组的展开状态存在 `source.getVariable()` 的 `open` 字段
- [ ] 等宽格子用 `layout_wrapBefore` 在每行首强制换行

## 十、验证方式

生成后用 Node 本地跑一遍 JS，检查输出结构与百分比：

```bash
node -e "var f=require('./explore.js'); var a=JSON.parse(f()); console.log('条目数:', a.length);
a.forEach(function(x){ if(!x.style) console.log('⚠️ 缺 style:', x.title); });
var pcts={}; a.forEach(function(x){var p=x.style&&x.style.layout_flexBasisPercent; pcts[p]=(pcts[p]||0)+1;});
console.log('百分比分布:', JSON.stringify(pcts));"
```

预期：无"缺 style"警告；百分比集中在 `0.45`（两列）与 `1`（标题/通栏）。
交互控件的 action JS 无法在 Node 里跑（依赖 `java`/`infoMap`），需在 Legado App 里实测。
