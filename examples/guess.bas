10 REM Number guessing game
20 LET SECRET = INT(RND(1) * 100) + 1
30 LET TRIES = 0
40 PRINT "I'm thinking of a number between 1 and 100"
50 INPUT "Your guess: "; G
60 LET TRIES = TRIES + 1
70 IF G = SECRET THEN GOTO 120
80 IF G < SECRET THEN PRINT "Too low!"
90 IF G > SECRET THEN PRINT "Too high!"
100 GOTO 50
120 PRINT "Correct! You got it in "; TRIES; " tries!"
130 END
