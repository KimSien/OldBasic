# ゴール

ブラウザーで動くゲームを作る為の機能を実装する

---

# 調査、レポート

## ブラウザ対応方式の比較

| 方式 | 実現性 | コスト | 評価 |
|---|---|---|---|
| **Pyodide**（CPython → WebAssembly） | 高 | 低〜中 | **推奨**: 既存Pythonコードをほぼそのまま流用可。JS←→Pythonブリッジ経由でCanvas操作 |
| JavaScript書き直し | 高 | 最高 | 長期的に最高性能。初期リリースには不向き |
| Brython | 中 | 中 | 軽量だがCPython非完全互換。インタープリタとの相性リスクあり |
| Transcrypt | 低 | 高 | `eval`/動的実行に非対応のため本用途に不向き |

**方針: まず Pyodide でブラウザ動作を実現し、必要なBASICゲーム機能を追加する**

## ゲームに必要なBASIC機能

### 必須
- `SCREEN n` — グラフィクスモード切替（SCREEN 13: 320×200 256色が定番）
- `CLS` — 画面クリア（毎フレーム先頭で使用）
- `PSET (x,y), color` — 1ピクセル描画
- `LINE (x1,y1)-(x2,y2), color [,BF]` — 直線・塗りつぶし矩形
- `COLOR fg, bg` — 前景色・背景色設定
- `GET/PUT` — スプライト取得・描画（ソフトウェアスプライト）
- `INKEY$` — ノンブロッキングキー入力（ゲームループの中核）

### 有用
- `CIRCLE (x,y), r, color` — 円・楕円描画
- `PAINT (x,y), color` — 領域塗りつぶし
- `POINT (x,y)` — 座標の色取得（衝突判定に利用）
- `PALETTE attr, color` — パレット色変更
- `SOUND freq, duration` — ビープ音生成
- `PLAY "string"` — MML形式の音楽演奏
- `SLEEP n` — n秒停止（フレーム待機に利用）

---

# 課題

## フェーズ1: ブラウザ実行環境の構築

- [x] Pyodide を使ったHTMLシェルの作成 → `web/index.html`
- [x] Canvas要素へのPython→JS描画ブリッジの設計 → `web/canvas_renderer.py`（CanvasRenderer）
- [x] REPL入力エリアとRUNボタンを持つWebUIの作成 → `web/index.html`

## フェーズ2: グラフィクス系ステートメントの実装

- [x] `SCREEN n` — スクリーンモード切替（SCREEN 1, 7, 9, 12, 13 対応）
- [x] `CLS` — 画面クリア（Canvasをリセット）
- [x] `PSET (x, y), color` — ピクセル描画
- [x] `LINE (x1,y1)-(x2,y2), color` — 直線描画
- [x] `LINE (x1,y1)-(x2,y2), color, B` — 矩形描画
- [x] `LINE (x1,y1)-(x2,y2), color, BF` — 塗りつぶし矩形描画
- [x] `CIRCLE (x,y), r, color` — 円描画（楕円・円弧も対応）
- [x] `PAINT (x,y), color` — 塗りつぶし
- [x] `POINT (x,y)` — 座標の色取得（関数として実装）
- [x] `GET (x1,y1)-(x2,y2), array` — 画面領域を配列へ取得
- [x] `PUT (x,y), array [, mode]` — 配列を画面へ描画（PSET / XOR / AND モード）

## フェーズ3: 色・表示制御

- [x] `COLOR fg [, bg]` — 前景色・背景色の設定
- [x] `PALETTE attr, color` — パレット色の変更

## フェーズ4: サウンド

- [x] `BEEP` — ビープ音（Web Audio API）
- [x] `SOUND freq, duration` — 周波数・長さ指定の音生成
- [x] `PLAY "string"` — MML文字列による音楽演奏（簡易対応）

## フェーズ5: タイミング・制御

- [x] `SLEEP n` — n秒間処理停止
- [x] `DO / LOOP` — 条件ループ構文（`DO WHILE` / `DO UNTIL` / `LOOP WHILE` / `LOOP UNTIL` / 無条件）
- [ ] `DO / LOOP` をゲームループとして使う際の非同期対応（ブラウザのUIスレッドをブロックしない設計）※ 将来課題

---

# 実装ファイル一覧

| ファイル | 内容 |
|---|---|
| `basic/renderer.py` | `Renderer`（no-op基底クラス）+ `NullRenderer`（テスト用） |
| `web/canvas_renderer.py` | `CanvasRenderer`（Pyodide/Canvas ブリッジ） |
| `web/index.html` | ブラウザUI（コードエディタ・Canvas・コンソール） |
| `tests/test_graphics.py` | グラフィクス・サウンド・DO/LOOP のテスト（58件） |

# ブラウザでの起動方法

プロジェクトルートからWebサーバーを起動して `web/index.html` を開く:
```
python3 -m http.server 8080
# ブラウザで http://localhost:8080/web/index.html を開く
```
