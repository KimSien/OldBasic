# 構成
- basic.py — CLIエントリポイント
- basic/lexer.py — トークナイザー 
- basic/parser.py — 再帰降下パーサー（AST生成）
- basic/interpreter.py — ツリーウォーク型インタープリタ 
  
  
# サポートする構文 
- PRINT, LET, INPUT, IF/THEN/ELSE, GOTO, GOSUB/RETURN 
- FOR/NEXTループ、DIM配列 
- DATA/READ/RESTORE、REMコメント 
- 算術・比較・論理演算子 
- 組み込み関数（文字列）: LEN, LEFT$, RIGHT$, MID$, STR$, VAL, CHR$, ASC
- 組み込み関数（数値）: INT, ABS, FIX, SGN, SQR, RND, LOG, EXP, SIN, COS, TAN, ATN
- 組み込み関数（出力）: TAB

# 使い方
## ファイルを実行 
python3 basic.py examples/hello.bas 

## 対話型REPL
python3 basic.py


