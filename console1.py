# console1.py
# Simple "console" that takes an expression and prints the evaluation tree.

import sys
import dollop

interactive = not sys.argv[1:]

if not interactive:
    s = sys.argv[1]

bi = dollop.BatchInterpreter()

while True:
    if interactive:
        s = input("Enter an expression: ")
        if not s.strip():
            break
        
    bi.feed(s)
        
    while True:
        print(bi.call_stack_repr())
        result = bi.run()
        if result is not None:
            print("=>", dollop.lisp_repr(result))
            break
            
    if not interactive:
        break
        
        