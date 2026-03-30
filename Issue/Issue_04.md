# Issue_04: ブラウザ実行パフォーマンス改善

## 概要

Issue_03 でアニメーション描画の非同期化は完了したが、
`invader.bas` 等のゲームループが体感的に遅く、実用的な速度で動作しない。

---

## 計測対象

| サンプル | ループ構造 | 1 フレームあたりの BASIC 行数 | SLEEP |
|----------|-----------|-------------------------------|-------|
| `invader.bas` | `DO WHILE RUNNING=1 ... LOOP` | 約 100 行 + サブルーチン呼出 | `SLEEP 0.05` (50ms) |
| `bounce.bas` | `DO WHILE FRAMES < 200` | 約 30 行 | なし |
| `sprite.bas` | `DO WHILE PX < 305` | 約 20 行 | なし |

---

## ボトルネック分析

### 原因 1 — 毎行 `await asyncio.sleep(0)` のオーバーヘッド（最重要）

**ファイル**: `basic/interpreter.py:156-180`

```python
async def _run_loop_async(self):
    while 0 <= self._pc < len(self._lines):
        line = self._lines[self._pc]
        try:
            self._exec_line(line)
            self._pc += 1
        # ... 例外処理 ...
        await asyncio.sleep(0)  # ← 毎行で JS イベントループに yield
```

`await asyncio.sleep(0)` は Pyodide 環境では単純なゼロコスト yield ではない。
Python → JS Promise → microtask queue → Python 復帰 という往復が毎行発生する。

`invader.bas` のメインループ 1 フレームで約 100 行 + サブルーチン 80 行 = **180 回の yield** が発生。
50ms の `SLEEP` を除いても yield だけで数十 ms を消費している可能性が高い。

**深刻度**: 致命的

---

### 原因 2 — Canvas 描画の Python→JS プロキシ呼出コスト

**ファイル**: `web/canvas_renderer.py:81-96`

```python
def pset(self, x: int, y: int, color: int) -> None:
    self._ctx.fillStyle = self._css(color)   # JS プロキシ経由のプロパティ設定
    self._ctx.fillRect(x, y, 1, 1)           # JS プロキシ経由のメソッド呼出

def line(self, x1, y1, x2, y2, color, mode='') -> None:
    self._ctx.strokeStyle = self._css(color)  # プロキシ
    self._ctx.fillStyle   = self._css(color)  # プロキシ
    self._ctx.beginPath()                     # プロキシ
    self._ctx.moveTo(x1, y1)                  # プロキシ
    self._ctx.lineTo(x2, y2)                  # プロキシ
    self._ctx.stroke()                        # プロキシ
```

Pyodide の JS プロキシは Python のメソッド呼出を JavaScript の
`Reflect.apply` 等を通じて実行する。1 回あたりのオーバーヘッドは小さいが、
`invader.bas` のメインループでは 1 フレームで以下が発生する:

- `LINE ... BF` × 約 15 回 → プロキシ呼出 45 回
- `PSET` × 約 5 回 → プロキシ呼出 10 回
- `LINE ... B` × 数回 → プロキシ呼出 20 回前後

合計 **70〜80 回の JS プロキシ呼出**/フレーム。
これに原因 1 の yield オーバーヘッドが乗算される。

**深刻度**: 高

---

### 原因 3 — `_css()` カラー変換の繰り返し呼出

**ファイル**: `web/canvas_renderer.py:50-53`

```python
def _css(self, color: int) -> str:
    if isinstance(color, int) and 0 <= color < len(self._palette):
        return self._palette[color]
    return '#FFFFFF'
```

単純なリストルックアップだが、`isinstance` チェック + 範囲チェックを
毎回行う。描画関数では `strokeStyle` と `fillStyle` の両方で呼ばれるため
1 つの `LINE` で 2 回呼出される。

**深刻度**: 低（単体では軽微だが改善容易）

---

### 原因 4 — `PAINT` (flood-fill) の Pure Python 実装

**ファイル**: `web/canvas_renderer.py:114-163`

```python
def paint(self, x, y, color, border=None):
    img = self._ctx.getImageData(0, 0, w, h)  # 全画面読み出し
    buf = bytearray(img.data.to_py())          # JS→Python 変換 (256KB @640x480)
    # ... Python による BFS flood-fill ...
    img.data.set(to_js(bytes(buf)))            # Python→JS 変換
    self._ctx.putImageData(img, 0, 0)          # 全画面書き戻し
```

320x200 RGBA = 256KB のデータを JS↔Python 間で 2 回コピーし、
さらに BFS を Pure Python で実行する。

**深刻度**: 高（ただし `invader.bas` では PAINT 未使用）

---

### 原因 5 — 式評価の `isinstance` チェーン

**ファイル**: `basic/interpreter.py:799-832`

```python
def _eval(self, node, lineno):
    if isinstance(node, NumberNode):   ...
    if isinstance(node, StringNode):   ...
    if isinstance(node, VarNode):      ...
    if isinstance(node, ArrayAccessNode): ...
    if isinstance(node, FuncCallNode): ...
    if isinstance(node, UnaryOpNode):  ...
    if isinstance(node, BinOpNode):    ...
```

7 段の `isinstance` チェーンにより、`BinOpNode` は最大 7 回の型チェックを通過する。
`invader.bas` の条件分岐（IF 文に `AND`/比較演算を含むもの）は
1 フレームに 30 回以上評価される。

**深刻度**: 中

---

### 原因 6 — `_LiveOut.write()` の DOM 操作

**ファイル**: `web/index.html:157-163`

```python
class _LiveOut:
    def write(self, text):
        import js as _js
        el = _js.document.getElementById('console')
        if el and text:
            el.textContent += text
```

`PRINT` のたびに `document.getElementById` を呼び、
`textContent +=` で DOM ノードの文字列を書き換える。
`invader.bas` では毎フレームのスコア表示でこれが発生する。

**深刻度**: 低

---

## 解決方針（優先順）

### Phase A — yield 頻度の最適化（必須・効果大）

| # | 作業 | 詳細 |
|---|------|------|
| A-1 | yield をフレーム境界のみに変更 | `SLEEP` / `LOOP` / `WEND` / `NEXT`（最外ループ）でのみ `await asyncio.sleep(0)` する。毎行 yield を廃止 |
| A-2 | 行数カウンタによるフォールバック yield | 無限ループで UI が固まるのを防ぐため、N 行（例: 500 行）実行ごとに 1 回 yield するガードを入れる |
| A-3 | `SLEEP 0` を `await asyncio.sleep(0)` にマップ | 明示的にフレーム更新を要求する手段を残す |

**期待効果**: invader.bas で 180 回/フレーム → 1〜2 回/フレームに削減。
yield オーバーヘッドが 1/100 以下に。

---

### Phase B — Canvas 描画の JS 側バッチ化

| # | 作業 | 詳細 |
|---|------|------|
| B-1 | JS 側にバッチ描画関数を用意 | `window.basicBatchDraw(commands)` — 描画コマンド配列を一括実行 |
| B-2 | Python 側で描画コマンドをキューイング | `pset`/`line`/`circle` を即座に実行せずリストに蓄積 |
| B-3 | フレーム境界（yield 時）でフラッシュ | `await asyncio.sleep(0)` の直前にバッチを JS に送信して一括描画 |

**期待効果**: 70〜80 回/フレームのプロキシ呼出 → 1 回のバッチ呼出に。

**代替案**: ImageData バッファに直接ピクセルを書き込み、
フレーム末に `putImageData` 1 回で反映する。
PSET には最適だが LINE/CIRCLE のラスタライズを Python 側で行う必要があり工数大。

---

### Phase C — PAINT の高速化

| # | 作業 | 詳細 |
|---|------|------|
| C-1 | JS 側で flood-fill を実行 | Canvas の `getImageData`/`putImageData` と BFS を JS で実装し、Python からは 1 回の JS 呼出で完了させる |
| C-2 | スキャンライン最適化 | 現在のピクセル単位 BFS をスキャンライン方式に変更（JS 実装内で） |

**期待効果**: PAINT の実行時間を 1/10〜1/50 に短縮。

---

### Phase D — 式評価の軽量化

| # | 作業 | 詳細 |
|---|------|------|
| D-1 | ディスパッチテーブル化 | `isinstance` チェーンを `dict[type, handler]` に変更。ノードタイプから O(1) で評価関数を取得 |
| D-2 | NumberNode / VarNode の短絡評価 | `_eval` 呼出前に `isinstance(node, (NumberNode, VarNode))` で頻出パターンを先にチェック |

**期待効果**: 式評価のオーバーヘッドを 20〜30% 削減。

---

### Phase E — 細部の最適化

| # | 作業 | 詳細 |
|---|------|------|
| E-1 | `_css()` 結果のキャッシュ | `_css_cache: dict[int, str]` を持ち、パレット変更時のみ無効化 |
| E-2 | `_LiveOut` の DOM 参照キャッシュ | `__init__` で要素参照を保持し `getElementById` を毎回呼ばない |
| E-3 | `fillStyle`/`strokeStyle` の重複設定回避 | 直前の色と同じなら再設定しない（JS プロキシ呼出削減） |

**期待効果**: 個々は小さいが A〜D と組み合わせて全体の滑らかさが向上。

---

## 実装メモ

### Phase A — yield 最適化の実装イメージ

```python
async def _run_loop_async(self):
    step = 0
    while 0 <= self._pc < len(self._lines):
        line = self._lines[self._pc]
        try:
            self._exec_line(line)
            self._pc += 1
        except _SleepSignal as s:
            self._pc += 1
            self._flush_draw_batch()           # Phase B: バッチ描画フラッシュ
            await asyncio.sleep(s.seconds)
            step = 0
            continue
        except _PcJumpSignal as j:
            self._pc = j.pc
        except _EndSignal:
            return
        # ... 他の例外 ...

        step += 1
        if step >= 500:                        # フォールバック: N 行ごとに yield
            self._flush_draw_batch()
            await asyncio.sleep(0)
            step = 0
```

### Phase B — JS バッチ描画の実装イメージ

```javascript
// index.html に追加
window.basicBatchDraw = function(cmds) {
  const ctx = document.getElementById('canvas').getContext('2d');
  for (const c of cmds) {
    switch (c[0]) {
      case 'fs': ctx.fillStyle = c[1]; break;
      case 'fr': ctx.fillRect(c[1], c[2], c[3], c[4]); break;
      case 'ss': ctx.strokeStyle = c[1]; break;
      case 'bp': ctx.beginPath(); break;
      case 'mt': ctx.moveTo(c[1], c[2]); break;
      case 'lt': ctx.lineTo(c[1], c[2]); break;
      case 'sk': ctx.stroke(); break;
      case 'sr': ctx.strokeRect(c[1], c[2], c[3], c[4]); break;
      case 'ar': ctx.arc(c[1], c[2], c[3], c[4], c[5]); break;
    }
  }
};
```

```python
# canvas_renderer.py — バッチ化版
class CanvasRenderer(Renderer):
    def __init__(self, ...):
        ...
        self._batch = []

    def pset(self, x, y, color):
        c = self._css(color)
        self._batch.append(('fs', c))
        self._batch.append(('fr', x, y, 1, 1))

    def flush(self):
        if self._batch:
            js.window.basicBatchDraw(to_js(self._batch))
            self._batch.clear()
```

### Phase C — JS 側 flood-fill のイメージ

```javascript
window.basicFloodFill = function(cx, cy, fillR, fillG, fillB, borderR, borderG, borderB, useBorder) {
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  // ... JS で BFS/scanline fill ...
  ctx.putImageData(img, 0, 0);
};
```

---

## 影響するサンプル

| ファイル | 改善効果 |
|----------|----------|
| `examples/invader.bas` | Phase A で大幅改善（yield 180→1〜2 回/frame） |
| `examples/bounce.bas` | Phase A + B で改善 |
| `examples/sprite.bas` | Phase A で改善 |
| `examples/gradient.bas` | Phase B で改善（48,000 PSET のバッチ化） |

---

## 参考資料

- [Pyodide Performance Guidance](https://github.com/pyodide/pyodide/discussions/1406)
- [Pyodide JSPI Integration](https://blog.pyodide.org/posts/jspi/)
- [Canvas Pixel Manipulation (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Pixel_manipulation_with_canvas)
- [Faster Canvas Pixel Manipulation with Typed Arrays](https://hacks.mozilla.org/2011/12/faster-canvas-pixel-manipulation-with-typed-arrays/)

---

## ステータス

- [x] A-1 yield をフレーム境界のみに変更
- [x] A-2 行数カウンタによるフォールバック yield
- [x] A-3 `SLEEP 0` のマッピング
- [x] B-1 JS 側バッチ描画関数
- [x] B-2 Python 側描画コマンドキューイング
- [x] B-3 フレーム境界でフラッシュ
- [x] C-1 PAINT を JS 側で実行
- [x] C-2 スキャンライン最適化
- [x] D-1 式評価のディスパッチテーブル化
- [x] D-2 頻出ノードの短絡評価
- [x] E-1 `_css()` キャッシュ
- [x] E-2 `_LiveOut` DOM 参照キャッシュ
- [x] E-3 `fillStyle`/`strokeStyle` 重複設定回避
