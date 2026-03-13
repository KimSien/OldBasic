# 課題実装の方向性

機能追加を行い、テストまでを行う。

# 課題

## 追加候補のステートメント

### 優先度: 高

- [x] `END` — プログラムを即時終了する。全BASIC方言で共通の基本構文。
- [x] `STOP` — 実行を一時停止する。デバッグ用途。GW-BASIC / QBasic に存在する。
- [x] `WHILE / WEND` — 条件が真の間ループを繰り返す構文。`WHILE I < 10 ... WEND` のように使用。GW-BASIC / QBasic の標準的なループ構文。
- [x] `RANDOMIZE` — RNDの乱数シードを設定する。`RANDOMIZE 1234` または `RANDOMIZE TIMER()` のように使用。GW-BASIC / QBasic に存在する。

### 優先度: 中

- [x] `ON ... GOTO` — 式の値に応じて行番号へジャンプする。`ON N GOTO 100,200,300` のように使用。GW-BASIC / QBasic に存在する。
- [x] `ON ... GOSUB` — 式の値に応じてサブルーチンへ分岐する。`ON N GOSUB 100,200,300` のように使用。GW-BASIC / QBasic に存在する。
- [x] `DEF FN` — ユーザー定義の簡易関数を作る。`DEF FNSQR(X) = X * X` のように使用。GW-BASIC / QBasic に存在する。


## 追加候補の組み込み関数

### 優先度: 高

- [x] `INSTR(s$, t$)` / `INSTR(n, s$, t$)` — 文字列内の部分文字列位置を返す（1始まり、見つからない場合は0）。GW-BASIC / QBasic / QuickBASIC に存在し、文字列処理の基本として使用頻度が高い。
- [x] `SPACE$(n)` — n個のスペース文字からなる文字列を返す。PRINT出力の整形に多用される。
- [x] `CINT(x)` — xを最近接整数に丸める（INT=床関数、FIX=切り捨てと異なる）。GW-BASIC / QBasic の標準的な整数変換関数。
- [x] `UCASE$(s$)` — 文字列を大文字に変換する。QBasic 以降の方言に広く存在する。
- [x] `LCASE$(s$)` — 文字列を小文字に変換する。QBasic 以降の方言に広く存在する。
- [x] `STRING$(n, c)` — 文字cをn回繰り返した文字列を返す（cは文字コードまたは1文字の文字列）。区切り線などの生成に多用される。
- [x] `INKEY$()` — キー入力を待たずに1文字取得する（入力がなければ空文字列）。対話型・ゲーム系プログラムに必須。GW-BASIC / QBasic / Commodore BASIC に存在する。
- [x] `TIMER()` — 深夜0時からの経過秒数を浮動小数点で返す。ループ計測やRNDのシード設定に広く使われる。GW-BASIC / QBasic に存在する。

### 優先度: 中

- [x] `LTRIM$(s$)` — 文字列の先頭スペースを除去する。QBasic / QuickBASIC に存在する。
- [x] `RTRIM$(s$)` — 文字列の末尾スペースを除去する。QBasic / QuickBASIC に存在する。
- [x] `HEX$(n)` — 整数nを16進数表記の文字列に変換する。GW-BASIC / QBasic に存在する。
- [x] `OCT$(n)` — 整数nを8進数表記の文字列に変換する。GW-BASIC / QBasic に存在する。
- [x] `SPC(n)` — PRINT文中でn個のスペースを出力する。TABと異なり相対的な空白挿入。QBasic / Commodore BASIC に存在する。
- [x] `DATE$()` — 現在の日付を文字列（"MM-DD-YYYY"形式）で返す。GW-BASIC / QBasic に存在する。
- [x] `TIME$()` — 現在の時刻を文字列（"HH:MM:SS"形式）で返す。GW-BASIC / QBasic に存在する。
- [x] `INPUT$(n)` — キーボードからn文字をエコーなしで読み込む。GW-BASIC / QBasic に存在する。
- [x] `POS(0)` — 現在のカーソル列位置を返す（テキストモードでは0を返す）。GW-BASIC / QBasic に存在する。
- [x] `CSRLIN()` — 現在のカーソル行位置を返す（テキストモードでは0を返す）。GW-BASIC / QBasic に存在する。

### 優先度: 低

- [x] `CLNG(x)` — xを長整数に変換する。QBasic / QuickBASIC に存在する。
- [x] `CSNG(x)` — xを単精度浮動小数点に変換する。GW-BASIC / QBasic に存在する。
- [x] `CDBL(x)` — xを倍精度浮動小数点に変換する。GW-BASIC / QBasic に存在する。
