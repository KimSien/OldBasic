10 REM gradient.bas - グラデーションとサイン波
20 SCREEN 1
30 CLS
40 REM 横方向グラデーション（色番号をX座標でサイクル）
50 FOR Y = 0 TO 149
60   FOR X = 0 TO 319
70     LET C = (X + Y) MOD 16
80     PSET (X, Y), C
90   NEXT X
100 NEXT Y
110 REM サイン波（下半分）
120 LINE (0, 174)-(319, 174), 0, BF
130 LINE (0, 150)-(319, 199), 0, BF
140 FOR X = 0 TO 319
150   LET ANGLE = X * 6.28318 / 80
160   LET Y = 174 + INT(SIN(ANGLE) * 20)
170   PSET (X, Y), 15
180 NEXT X
190 REM ラベル
200 LINE (0, 150)-(319, 151), 7
210 PRINT "Gradient & Sine Wave"
220 END
