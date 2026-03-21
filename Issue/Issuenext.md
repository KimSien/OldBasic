# Issuenext: 今後実装すべき機能

現状の実装（Issue_01〜04）を踏まえ、GW-BASIC / QBasic 互換性・実用性・開発体験の観点から
今後追加すべき機能をリサーチしてまとめた。

---

## 1. 構造化サブルーチン / ユーザー定義関数（SUB / FUNCTION）

### 概要

現在は `DEF FN name(x) = expr` による単一式関数のみサポート。
QBasic のマルチライン `SUB` / `FUNCTION` ブロックは未実装。

### 対象構文

```basic
SUB DrawBox(x, y, w, h)
    LINE (x, y)-(x+w, y+h), 7, B
END SUB

FUNCTION Square(n)
    Square = n * n
END FUNCTION

CALL DrawBox(10, 20, 100, 80)
PRINT Square(5)
```

### 実装ポイント

| 項目 | 内容 |
|------|------|
| スコープ | SUB/FUNCTION 内は独立したローカル変数スコープ |
| 引数渡し | 値渡し（デフォルト）/ 参照渡し（`BYREF` キーワード）|
| 戻り値 | FUNCTION 名への代入で戻り値を設定（QBasic 方式）|
| 再帰 | コールスタック管理が必要 |
| パーサー | `SUB`〜`END SUB` / `FUNCTION`〜`END FUNCTION` ブロックの収集 |

### 優先度: 高

大規模プログラム（ゲーム等）の保守性が大幅に向上する。
`invader.bas` も `GOSUB` から `SUB` に書き換えることで可読性が上がる。

---

## 2. SELECT CASE 文

### 概要

条件分岐が `IF/ELSEIF` の連鎖になりがちな現状を改善する。
GW-BASIC には存在しないが QBasic 以降の標準構文で、可読性が高い。

### 対象構文

```basic
SELECT CASE key$
    CASE "w", "W"
        y = y - 1
    CASE "s", "S"
        y = y + 1
    CASE IS > 100
        PRINT "over 100"
    CASE 1 TO 10
        PRINT "range"
    CASE ELSE
        PRINT "other"
END SELECT
```

### 実装ポイント

| 項目 | 内容 |
|------|------|
| マッチング | 値リスト / `IS` 演算子 / `TO` 範囲 の3形式 |
| 評価式 | 文字列・数値どちらにも対応 |
| フォールスルー | QBasic はフォールスルーなし（マッチしたら即 END SELECT へ）|

### 優先度: 高

`keytest.bas` / `invader.bas` のキー分岐が簡潔になる。

---

## 3. EXIT FOR / EXIT DO / EXIT WHILE

### 概要

ループの途中脱出。現在はループを抜けるには `GOTO` しか手段がない。

### 対象構文

```basic
FOR i = 1 TO 100
    IF arr(i) = target THEN EXIT FOR
NEXT i

DO WHILE running
    IF hp <= 0 THEN EXIT DO
    ' ...
LOOP
```

### 実装ポイント

- ループスタックに「現在ループ種別」を記録し、対応する NEXT/LOOP/WEND の位置へジャンプ
- `_ExitLoopSignal` 例外を追加し、各ループ実行ハンドラでキャッチ

### 優先度: 高

ゲームのメインループや検索ループで必須パターン。

---

## 4. PRINT USING 文

### 概要

書式指定付き出力。数値の桁揃え・小数点位置指定が可能。
スコア表示・表形式出力に多用される。

### 対象構文

```basic
PRINT USING "####.##"; score
PRINT USING "\\        \\"; name$   ' 文字列フィールド（10文字）
PRINT USING "+##.##^^"; 3.14159    ' 科学表記
```

### 書式文字

| 文字 | 意味 |
|------|------|
| `#` | 数値桁（1桁）|
| `.` | 小数点位置 |
| `+` / `-` | 符号 |
| `^` | 指数部（4文字で指数表記）|
| `\\...\\` | 文字列フィールド（間の文字数＋2文字分）|
| `&` | 可変長文字列フィールド |
| `!` | 先頭1文字のみ |

### 優先度: 中

テキストUI・スコア表示の品質が向上する。

---

## 5. LOCATE 文 / テキストカーソル制御

### 概要

テキストモードでのカーソル位置指定。テキストUI・メニュー画面の構築に必須。

### 対象構文

```basic
LOCATE 5, 10          ' 5行目10列にカーソル移動
LOCATE 5, 10, 0       ' カーソル非表示
LOCATE , , 1          ' カーソル表示（位置変更なし）
```

### 実装ポイント

- ブラウザ版: Canvas 上にテキスト描画座標として管理（`fillText` の x/y 計算）
- CLI 版: ANSI エスケープシーケンス `\033[row;colH` で実現
- `POS(0)` / `CSRLIN()` との整合性確保（現在は常に 0 を返す）

### 優先度: 中

---

## 6. ファイル I/O（OPEN / CLOSE / INPUT# / PRINT# / LINE INPUT#）

### 概要

ファイルの読み書きは実用プログラムの基盤。現在は一切未実装。

### 対象構文

```basic
OPEN "data.txt" FOR INPUT AS #1
LINE INPUT #1, line$
CLOSE #1

OPEN "out.txt" FOR OUTPUT AS #2
PRINT #2, "Hello"
CLOSE #2

OPEN "data.dat" FOR RANDOM AS #3 LEN = 128
GET #3, recnum, buffer$
PUT #3, recnum, buffer$
CLOSE #3
```

### モード

| モード | 説明 |
|--------|------|
| INPUT | 順次読み込み |
| OUTPUT | 順次書き込み（上書き）|
| APPEND | 追記 |
| RANDOM | ランダムアクセス |
| BINARY | バイナリ |

### 関連関数

`EOF(n)`, `LOF(n)`, `LOC(n)`, `FREEFILE`

### ブラウザ版の対応方針

- ブラウザ環境ではローカルファイルに直接アクセスできないため、
  `localStorage` または IndexedDB を仮想ファイルシステムとして使用
- `OPEN "file.txt" FOR OUTPUT` → localStorage への書き込み
- ダウンロードボタン（ファイルエクスポート）との連携も検討

### 優先度: 中（CLI版は高、ブラウザ版は中〜低）

---

## 7. ON ERROR GOTO / RESUME / ERR / ERL

### 概要

実行時エラーのハンドリング機構。現在はエラー発生で即停止する。

### 対象構文

```basic
ON ERROR GOTO ErrHandler
' ... 処理 ...
ON ERROR GOTO 0     ' エラーハンドラ解除
END

ErrHandler:
    PRINT "Error"; ERR; "at line"; ERL
    RESUME NEXT     ' エラー行の次から再開
    ' または RESUME  → エラー行を再実行
    ' または RESUME 100 → 100行へジャンプ
```

### 実装ポイント

- `Interpreter` にエラーハンドラ行番号を保持
- `BasicError` 発生時にハンドラへジャンプ
- `ERR`（エラーコード）/ `ERL`（エラー発生行）組み込み変数を追加
- `RESUME` は `_ResumeSignal` 例外で実装

### 優先度: 低

---

## 8. ERASE / LBOUND / UBOUND（配列管理）

### 概要

配列の動的管理と境界値取得。

### 対象構文

```basic
DIM arr(10)
ERASE arr         ' 配列を消去・初期化
REDIM arr(20)     ' 配列を再定義（サイズ変更）

PRINT LBOUND(arr) ' 下限インデックス（通常 0 または 1）
PRINT UBOUND(arr) ' 上限インデックス
```

### 実装ポイント

- `ERASE`: `_arrays` から削除またはゼロ初期化
- `REDIM`: 配列の再確保（`REDIM PRESERVE` で既存データ保持）
- `LBOUND` / `UBOUND`: 配列メタデータ（次元ごとのサイズ）を管理
- `OPTION BASE 0 / 1`: 配列の最小インデックスを全体設定

### 優先度: 低

---

## 9. SWAP 文

### 概要

2変数の値を交換する。ソートアルゴリズム等で多用される。

### 対象構文

```basic
SWAP a, b
SWAP arr(i), arr(j)
```

### 実装ポイント

- パーサーで `SwapNode(left, right)` を生成
- インタープリタで両辺を評価して交換

### 優先度: 低（実装容易）

---

## 10. DRAW 文（グラフィックス拡張）

### 概要

描画命令を文字列で記述するミニ言語（タートルグラフィクス的）。
GW-BASIC の `DRAW` 文。

### 対象構文

```basic
DRAW "M100,100"    ' カーソル移動（絶対）
DRAW "R20 U20 L20 D20"  ' 相対移動しながら描画
DRAW "C3 BM50,50 F20"   ' 色指定・斜め移動
```

### 主要コマンド

| コマンド | 意味 |
|----------|------|
| `Ux` | Up x ピクセル |
| `Dx` | Down |
| `Lx` | Left |
| `Rx` | Right |
| `Ex` / `Fx` / `Gx` / `Hx` | 斜め移動 |
| `Mx,y` | 絶対/相対移動 |
| `Cn` | 色設定 |
| `B` | 移動のみ（描画なし）|
| `N` | 描画後元位置に戻る |
| `S` | スケール |
| `A` | 角度 |
| `TAn` | 任意角度 |
| `Pf,b` | 塗りつぶし |
| `X` | サブストリング実行 |

### 優先度: 低

---

## 11. WRITE 文

### 概要

`PRINT` と同様だが、文字列をダブルクォートで囲みカンマ区切りで出力する。
ファイル出力（`WRITE #n`）と組み合わせてCSV形式データ生成に使う。

### 対象構文

```basic
WRITE a$, b, c$
' 出力: "hello",42,"world"

WRITE #1, name$, score
```

### 優先度: 低

---

## 12. デバッグ支援（TRON / TROFF / ブレークポイント）

### 概要

実行トレース機能。学習・デバッグ用途に有用。

### 対象構文

```basic
TRON          ' トレースオン: 実行中の行番号を表示
TROFF         ' トレースオフ
```

### 拡張案（独自機能）

- `--trace` CLI フラグで起動時から有効化
- ブレークポイント指定（`--break=100,200`）で特定行で一時停止
- ステップ実行モード（REPL でのデバッグ）

### 実装ポイント

- `Interpreter` にトレースフラグを追加
- 各行実行前に `sys.stderr.write(f"[{lineno}] ")` を出力
- ブレークポイント: 対象行到達時に入力待ち状態へ

### 優先度: 低

---

## 13. Web UI の改善

### 概要

現在の Web UI（`web/index.html`）はシンプルなエディタ＋実行ボタンのみ。
以下の機能追加で開発体験が大きく向上する。

### 追加項目

| 機能 | 詳細 |
|------|------|
| シンタックスハイライト | CodeMirror 等を組み込み、キーワードを色分け |
| ファイルの保存・読み込み | ブラウザの `localStorage` または JSON エクスポート |
| サンプル選択 | ドロップダウンでサンプルプログラムをロード |
| エラー表示 | エラー発生行をエディタ上でハイライト |
| フルスクリーン Canvas | ゲーム実行時に Canvas を大画面表示 |
| モバイル対応 | タッチ操作・仮想キーボード（矢印キー等）|
| 共有 URL | プログラムを URL に埋め込み（Base64）して共有 |

### 優先度: 中（ユーザー体験への影響大）

---

## 14. 多次元配列の完全サポート

### 概要

現在の `DIM` は単次元のみ（実装確認が必要）。
GW-BASIC は最大 255 次元の多次元配列をサポートする。

### 対象構文

```basic
DIM matrix(10, 10)
DIM cube(5, 5, 5)

matrix(3, 7) = 42
PRINT cube(1, 2, 3)
```

### 実装ポイント

- `_arrays` の格納形式を多次元対応に（ネストリストまたはフラット配列＋次元情報）
- `DIM` パース時に複数の次元サイズを収集

### 優先度: 中

---

## 優先度サマリー

| # | 機能 | 優先度 | 実装規模 |
|---|------|--------|----------|
| 1 | SUB / FUNCTION（構造化サブルーチン）| 高 | 大 |
| 2 | SELECT CASE | 高 | 中 |
| 3 | EXIT FOR / EXIT DO / EXIT WHILE | 高 | 小 |
| 4 | PRINT USING | 中 | 中 |
| 5 | LOCATE / テキストカーソル制御 | 中 | 中 |
| 6 | ファイル I/O | 中 | 大 |
| 7 | 多次元配列の完全サポート | 中 | 中 |
| 8 | Web UI 改善 | 中 | 中 |
| 9 | ON ERROR GOTO / RESUME | 低 | 中 |
| 10 | ERASE / REDIM / LBOUND / UBOUND | 低 | 小 |
| 11 | SWAP | 低 | 小 |
| 12 | DRAW 文 | 低 | 中 |
| 13 | WRITE 文 | 低 | 小 |
| 14 | TRON / TROFF / デバッグ支援 | 低 | 小 |

---

## 実装ロードマップ案

### Phase 1（次期リリース）

Issue_04（パフォーマンス最適化）完了後に着手。

1. **EXIT FOR / EXIT DO / EXIT WHILE** — 小規模・効果大
2. **SELECT CASE** — ゲーム・対話プログラムの可読性向上
3. **SWAP** — 実装コスト最小

### Phase 2

4. **SUB / FUNCTION** — 大規模だが言語の表現力を根本的に拡張
5. **多次元配列** — 数値計算・行列演算のサポート

### Phase 3

6. **PRINT USING** — 出力品質の向上
7. **LOCATE** — テキストUI の実現
8. **Web UI 改善** — ユーザー向け体験の向上

### Phase 4（長期）

9. **ファイル I/O** — ブラウザ仮想FSの設計が必要
10. **ON ERROR GOTO** — エラー回復機構
11. **DRAW 文** — グラフィクス表現力の拡張
12. **TRON / TROFF** — 教育・デバッグ用途

---

## 参考

- [GW-BASIC User's Guide](https://hwiegman.home.xs4all.nl/gw-man/)
- [QBasic Language Reference](https://www.qbasic.net/en/reference/qb11/overview/language_reference.htm)
- [Pyodide Filesystem (Emscripten)](https://pyodide.org/en/stable/usage/file-system.html)
- [CodeMirror BASIC mode](https://codemirror.net/)
