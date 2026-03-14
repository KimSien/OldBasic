# Issue_03: ブラウザアニメーション非表示問題

## 概要

`bounce.bas`・`sprite.bas` などループアニメーションを含むプログラムをブラウザで実行しても、
中間フレームが描画されず最終フレームのみが表示される。

---

## 根本原因

### 原因 1 — 同期ブロッキング実行（最重要）

**ファイル**: `web/index.html`（`btnRun` ハンドラ内）

`pyodide.runPythonAsync()` の中で `interp.run()` を呼ぶと、
Python コードは **完全に同期** で実行される。
`runPythonAsync` は JS 側から await できるが、内部の Python ループは
一切 JS イベントループに制御を返さない。

```js
await pyodide.runPythonAsync(`
    interp.run()   // ← DO WHILE 200回ぶん全て完走してから返る
`);
// ここに来て初めてブラウザが再描画する
```

ブラウザの再描画（コンポジット）は JS イベントループがアイドルになった瞬間にしか
行われないため、全フレーム描画後の最終状態だけが見える。

**深刻度**: 致命的

---

### 原因 2 — `time.sleep()` によるイベントループ完全ブロック

**ファイル**: `web/canvas_renderer.py` `sleep()` メソッド

```python
def sleep(self, seconds: float) -> None:
    import time
    time.sleep(seconds)   # JS イベントループごとブロック
```

`SLEEP` でフレーム間隔を付けようとしても、ブラウザの再描画タイミングを
得られないまま待機時間だけ増える。

**深刻度**: 高

---

### 原因 3 — Canvas 描画のフラッシュ機構が存在しない

**ファイル**: `web/canvas_renderer.py`

`pset`・`line`・`circle` などは 2D context に即座に書き込むが、
ブラウザが画面に反映するのはイベントループが空いたタイミングのみ。
フレーム単位で「ここで表示を更新する」メカニズムがない。

```python
def pset(self, x, y, color):
    self._ctx.fillStyle = self._css(color)
    self._ctx.fillRect(x, y, 1, 1)   # バッファに書くだけ
    # ← flush / requestAnimationFrame の呼び出しなし
```

**深刻度**: 高

---

### 原因 4 — `_run_loop` がタイトな同期ループ（yield なし）

**ファイル**: `basic/interpreter.py` `_run_loop()`

```python
def _run_loop(self):
    while 0 <= self._pc < len(self._lines):
        line = self._lines[self._pc]
        try:
            self._exec_line(line)
            self._pc += 1
        except _PcJumpSignal as j:
            self._pc = j.pc   # 非同期チェックポイントなし
```

DO/LOOP・WHILE/WEND の全イテレーションが、JS に制御を返す機会なしに
完走する。

**深刻度**: 高

---

### 原因 5 — stdout が実行完了まで StringIO にバッファされる

**ファイル**: `web/index.html`

実行中の `PRINT` 出力はすべて `StringIO` に蓄積され、
`interp.run()` 完了後にまとめてコンソールへ書き出される。
アニメーション中の途中経過テキストもリアルタイムには表示されない。

**深刻度**: 中

---

## 解決方針（優先順）

### Phase A — フレーム描画の非同期化（必須）

| # | 作業 | 詳細 |
|---|------|------|
| A-1 | `_run_loop` を Python async generator に変換 | `yield` で各行実行後に JS へ制御を返せるようにする |
| A-2 | `interp.run()` を `async def` に変換 | `await asyncio.sleep(0)` を挿入して JS イベントループを解放 |
| A-3 | `index.html` の実行ループを `requestAnimationFrame` ベースに変更 | Python generator を JS 側で 1 フレームずつ進める |

### Phase B — SLEEP の非同期化

| # | 作業 | 詳細 |
|---|------|------|
| B-1 | `CanvasRenderer.sleep()` を `await asyncio.sleep(seconds)` に変更 | Pyodide の event loop と統合 |
| B-2 | `SLEEP` 文の実行を async 対応に変更 | interpreter の async chain が必要 |

### Phase C — フレーム単位フラッシュ

| # | 作業 | 詳細 |
|---|------|------|
| C-1 | `CanvasRenderer` に `flip()` / `present()` メソッドを追加 | JS 側で `requestAnimationFrame` の完了を待つ |
| C-2 | BASIC 文 `FLIP` または暗黙フラッシュ（LOOP/WEND 毎）を検討 | フレームバウンダリを明示する手段 |

### Phase D — stdout リアルタイム出力

| # | 作業 | 詳細 |
|---|------|------|
| D-1 | `sys.stdout.write` を JS `log()` に直結するカスタム `TextIO` に変更 | StringIO バッファをなくす |

---

## 実装メモ

### Pyodide での async 実行パターン（参考）

```python
# interpreter.py のイメージ
async def run_async(self):
    for line in self._lines:
        self._exec_line(line)
        await asyncio.sleep(0)   # JS イベントループへ yield
```

```js
// index.html のイメージ
await pyodide.runPythonAsync(`
    import asyncio
    await interp.run_async()
`);
```

### requestAnimationFrame ベース実装（より滑らか）

```js
function scheduleFrame(gen) {
    requestAnimationFrame(() => {
        const { done } = gen.next();
        if (!done) scheduleFrame(gen);
    });
}
```

```python
# Python 側 generator
def run_frames(self):
    for line in self._lines:
        self._exec_line(line)
        if is_frame_boundary(line):
            yield   # JS requestAnimationFrame まで待機
```

---

## 影響するサンプル

| ファイル | 問題 |
|----------|------|
| `examples/bounce.bas` | DO WHILE 200 回ループ — 最終位置だけ表示 |
| `examples/sprite.bas` | DO WHILE PX < 305 — スプライト移動が見えない |
| `examples/gradient.bas` | 静止画のため問題なし |
| `examples/colors.bas` | 静止画のため問題なし |
| `examples/shapes.bas` | 静止画のため問題なし |

---

## ステータス

- [x] A-1 `_run_loop_async` 追加（`await asyncio.sleep(0)` で毎行 JS へ yield）
- [x] A-2 `interp.run_async()` 追加
- [x] A-3 `index.html` を `await interp.run_async()` に切り替え
- [x] B-1/B-2 `_SleepSignal` 導入 → async ループで `await asyncio.sleep(secs)` に変換
- [ ] C-1 `flip()` メソッド追加（現状は毎行 yield で代替）
- [ ] C-2 FLIP 文設計（将来タスク）
- [x] D-1 `_LiveOut` カスタム stdout → コンソールへリアルタイム出力
