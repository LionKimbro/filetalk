
import filetalk


D = filetalk.arg()
S = []

for cmd in D["EXPR"]:
    if cmd == "+":
        S.append(S.pop()+S.pop())
    else:
        S.append(cmd)

filetalk.write(D["WRITE_RESULT"], S.pop())

