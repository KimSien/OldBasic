# 構成
- basic.py — CLIエントリポイント
- basic/lexer.py — トークナイザー
- basic/parser.py — 再帰降下パーサー（AST生成）
- basic/interpreter.py — ツリーウォーク型インタープリタ
- tests/test_interpreter.py — pytestテストスイート


# サポートする構文

## ステートメント
| 構文 | 説明 | 例 |
|---|---|---|
| `PRINT` | 値を出力する。`,` で桁揃え、`;` で連結 | `PRINT "A"; TAB(10); "B"` |
| `LET` | 変数に値を代入する（`LET` は省略可） | `LET X = 3 * 4` |
| `INPUT` | キーボードから入力を受け取る | `INPUT "名前: "; N$` |
| `IF / THEN / ELSE` | 条件分岐 | `IF X > 0 THEN PRINT "正" ELSE PRINT "負"` |
| `GOTO` | 指定行番号へジャンプ | `GOTO 100` |
| `GOSUB / RETURN` | サブルーチン呼び出しと復帰 | `GOSUB 500` |
| `FOR / NEXT` | カウントループ（`STEP` 対応） | `FOR I = 1 TO 10 STEP 2` |
| `WHILE / WEND` | 条件ループ | `WHILE I < 10 ... WEND` |
| `ON ... GOTO` | 式の値で行番号へ分岐 | `ON N GOTO 100,200,300` |
| `ON ... GOSUB` | 式の値でサブルーチンへ分岐 | `ON N GOSUB 100,200,300` |
| `DIM` | 配列を宣言する（1始まり） | `DIM A(10)` |
| `DATA / READ / RESTORE` | 定数データの定義と読み込み | `DATA 1,2,3 : READ X` |
| `DEF FN` | ユーザー定義の一行関数 | `DEF FNSQ(X) = X * X` |
| `RANDOMIZE` | 乱数シードを設定する | `RANDOMIZE 42` |
| `END` | プログラムを即時終了する | `END` |
| `STOP` | 実行を停止する（デバッグ用） | `STOP` |
| `REM` | コメント | `REM これはコメント` |

## 演算子
| 種別 | 演算子 |
|---|---|
| 算術 | `+` `-` `*` `/` `^`（べき乗） `MOD` |
| 比較 | `=` `<>` `<` `>` `<=` `>=` |
| 論理 | `AND` `OR` `NOT` |

## 組み込み関数

### 文字列
| 関数 | 説明 |
|---|---|
| `LEN(s$)` | 文字列の長さ |
| `LEFT$(s$, n)` | 先頭n文字 |
| `RIGHT$(s$, n)` | 末尾n文字 |
| `MID$(s$, n[, l])` | 位置n（1始まり）からl文字 |
| `STR$(x)` | 数値を文字列に変換 |
| `VAL(s$)` | 文字列を数値に変換 |
| `CHR$(n)` | ASCII コードから文字 |
| `ASC(s$)` | 文字の ASCII コード |
| `INSTR([n,] s$, t$)` | s$ 内の t$ の位置（1始まり、0=未発見） |
| `SPACE$(n)` | n個のスペース文字列 |
| `STRING$(n, c)` | 文字cをn回繰り返した文字列 |
| `UCASE$(s$)` | 大文字に変換 |
| `LCASE$(s$)` | 小文字に変換 |
| `LTRIM$(s$)` | 先頭スペースを除去 |
| `RTRIM$(s$)` | 末尾スペースを除去 |
| `HEX$(n)` | 16進数表記の文字列 |
| `OCT$(n)` | 8進数表記の文字列 |

### 数値
| 関数 | 説明 |
|---|---|
| `INT(x)` | 床関数（負方向に切り捨て） |
| `FIX(x)` | ゼロ方向に切り捨て |
| `CINT(x)` | 最近接整数へ丸め |
| `ABS(x)` | 絶対値 |
| `SGN(x)` | 符号（1 / 0 / -1） |
| `SQR(x)` | 平方根 |
| `RND([n])` | 0以上1未満の乱数 |
| `LOG(x)` | 自然対数 |
| `EXP(x)` | 自然指数 |
| `SIN(x)` | サイン（ラジアン） |
| `COS(x)` | コサイン（ラジアン） |
| `TAN(x)` | タンジェント（ラジアン） |
| `ATN(x)` | アークタンジェント |
| `CLNG(x)` | 長整数に変換 |
| `CSNG(x)` | 単精度浮動小数点に変換 |
| `CDBL(x)` | 倍精度浮動小数点に変換 |

### 出力・I/O
| 関数 | 説明 |
|---|---|
| `TAB(n)` | PRINT 内で桁位置nへ移動 |
| `SPC(n)` | PRINT 内でn個のスペースを出力 |
| `INPUT$(n)` | キーボードからn文字を読み込む |
| `INKEY$()` | 非ブロッキングで1文字取得（なければ空文字） |
| `POS(0)` | カーソル列位置（テキストモードでは0） |
| `CSRLIN()` | カーソル行位置（テキストモードでは0） |

### システム
| 関数 | 説明 |
|---|---|
| `TIMER()` | 深夜0時からの経過秒数（浮動小数点） |
| `DATE$()` | 現在の日付（"MM-DD-YYYY"形式） |
| `TIME$()` | 現在の時刻（"HH:MM:SS"形式） |


# 使い方

## ファイルを実行
```
python3 basic.py examples/hello.bas
```

## 対話型REPL
```
python3 basic.py
```

REPLの特殊コマンド:
- `RUN` — プログラムを実行
- `LIST` — プログラムを表示
- `NEW` — プログラムと変数をクリア
- `QUIT` — 終了


# 開発メモ

## テストの実行
```
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/test_interpreter.py -v
```
