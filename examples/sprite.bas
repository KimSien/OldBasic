10 REM sprite.bas - GET/PUT によるスプライト移動
20 SCREEN 1
30 CLS
40 REM 背景：星空
50 FOR I = 1 TO 60
60   LET SX = INT(RND(1) * 320)
70   LET SY = INT(RND(1) * 200)
80   PSET (SX, SY), 7 + (I MOD 9)
90 NEXT I
100 REM スプライト（16x16）を左上に描く
110 LINE (0, 0)-(15, 15), 4, BF
120 CIRCLE (8, 8), 5, 14
130 PSET (5, 6), 0
140 PSET (11, 6), 0
150 PSET (8, 10), 15
160 LINE (5, 12)-(11, 12), 15
170 REM スプライトをGETで取得
180 GET (0, 0)-(15, 15), SPR
190 REM 元の位置を黒で消す
200 LINE (0, 0)-(15, 15), 0, BF
210 REM スプライトをX方向に移動しながらPUT
220 LET PX = 0
230 LET PY = 92
240 DO WHILE PX < 305
250   REM 前の位置を消す
260   LINE (PX, PY)-(PX + 15, PY + 15), 0, BF
270   REM 背景の星を再描画（簡易：範囲内の点を再描画）
280   LET PX = PX + 2
290   REM スプライトを新位置に描画
300   PUT (PX, PY), SPR, PSET
310 LOOP
320 PRINT "Sprite done! X="; PX
330 END
