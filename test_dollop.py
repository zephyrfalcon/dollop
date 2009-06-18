# test_dollop.py

import unittest
#
import dollop

class TestDollop(unittest.TestCase):
    
    def test_tokenize(self):
        tokens = dollop.tokenize("3")
        self.assertEquals(tokens, ["3"])
        
        tokens = dollop.tokenize("(+ 1 2)")
        self.assertEquals(tokens, ["(", "+", "1", "2", ")"])

        tokens = dollop.tokenize("(if (foo bar) #t 33")
        self.assertEquals(tokens, 
          ["(", "if", "(", "foo", "bar", ")", "#t", "33"])
        
    def test_parse(self):
        tokens = ["(", "if", "(", "foo", "bar", ")", "#t", "33"]
        tree = dollop.parse(tokens)
        self.assertEquals(repr(tree), 
          repr(["if", ["foo", "bar"], True, 33]))
          
        tokens = ["3"]
        tree = dollop.parse(tokens)
        self.assertEquals(tree, 3)
        
    def test_eval(self):
        bi = dollop.BatchInterpreter()
        
        # literals
        self.assertEquals(bi.eval('3'), 3)
        self.assertEquals(bi.eval('#f'), False)
        self.assertEquals(bi.eval('  42  \n'), 42)
        
        # symbols (variable lookup)
        self.assertEquals(bi.eval('magic'), 42)
        
        # builtin function calls
        self.assertEquals(bi.eval("(+ 1 2)"), 3)
        self.assertEquals(bi.eval("(+ (+ 1 2) (+ 3 4))"), 10)
        self.assertEquals(bi._num_calls, 13)
        
        self.assertEquals(bi.eval("(list 1 2 3)"), [1, 2, 3])
        self.assertEquals(bi.eval("(+ (list 1 2) (list 3 4))"), [1, 2, 3, 4])
        self.assertEquals(bi.eval("(+ (list 1 2) (list 3 (+ 0 4)))"), 
          [1, 2, 3, 4])
          
        # special forms
        self.assertEquals(bi.eval("(define x 4)"), False)
        self.assertEquals(bi._env.get('x')[1], 4)
        
        self.assertEquals(bi.eval("(if #t 4 5)"), 4)
        self.assertEquals(bi.eval("(if #f 4 5)"), 5)
        self.assertEquals(bi.eval("(if #t (+ 1 2) (+ 3 4))"), 3)
        self.assertEquals(bi.eval("(if #t (+ 1 2) bogus)"), 3)
        self.assertEquals(bi.eval("(if #f bogus (+ 2 3))"), 5)
        
        z = bi.eval("(lambda (x) x)")
        self.assert_(isinstance(z, dollop.Lambda))
        
        self.assertEquals(bi.eval("""
            (begin (+ 1 2)
                   (+ 3 4)
                   (+ 5 6))"""), 11)
                   
        # continuations
        self.assertEquals(bi.eval("(call/cc (lambda (k) 3))"), 3)
        self.assertEquals(bi.eval("(+ 1 (call/cc (lambda (k) 3)))"), 4)
        
        self.assertEquals(bi.eval("(call/cc (lambda (k) (+ 1 (k 2))))"), 2)
        self.assertEquals(bi.eval("(+ 3 (call/cc (lambda (k) (+ 1 (k 2)))))"), 
          5)
          
        # quote
        self.assertEquals(bi.eval("(quote x)"), "x")
        self.assertEquals(bi.eval("(quote (1 2 3))"), [1, 2, 3])
          
        # eval/apply
        self.assertEquals(bi.eval("(eval (quote (+ 10 20)))"), 30)
        self.assertEquals(bi.eval("(apply + (quote (1 2)))"), 3)
        self.assertEquals(bi.eval("(apply + (list 3 magic))"), 45)
        
    def test_eval_lambda(self):
        bi = dollop.BatchInterpreter()
        
        bi.eval("(define inc (lambda (x) (+ x 1)))")
        self.assertEquals(bi.eval("(inc 3)"), 4)
        
        bi.eval("(define a 1)")
        bi.eval("(define f (lambda (x) (+ a x)))")
        self.assertEquals(bi.eval("(f 3)"), 4) 
        
        bi.eval("""
          (define add-n
            (lambda (n)
              (lambda (x) (+ x n)))) """)
        self.assertEquals(bi.eval("((add-n 4) 5)"), 9)
        
    def test_eval_builtin_function_call(self):
        bi = dollop.BatchInterpreter()
        tokens = dollop.tokenize("(+ 1 2)")
        tree = dollop.parse(tokens)
        bi._feed(tree)
        
        self.assertEquals(bi._call_stack[0].lisp_repr(), "(+ 1 2)")
        
        bi.run()
        self.assertEquals(len(bi._call_stack), 2)
        self.assertEquals(bi._call_stack[0].lisp_repr(), "($$ 1 2)")
        self.assertEquals(bi._call_stack[1].lisp_repr(), "+")
        
        bi.run()
        self.assertEquals(len(bi._call_stack), 2)
        self.assertEquals(bi._call_stack[0].lisp_repr(), "(<lambda:+> $$ 2)")
        self.assertEquals(bi._call_stack[1].lisp_repr(), "1")
        
        bi.run()
        self.assertEquals(len(bi._call_stack), 2)
        self.assertEquals(bi._call_stack[0].lisp_repr(), "(<lambda:+> 1 $$)")
        self.assertEquals(bi._call_stack[1].lisp_repr(), "2")

        bi.run()
        self.assertEquals(len(bi._call_stack), 1)
        self.assertEquals(bi._call_stack[0].lisp_repr(), "(<lambda:+> 1 2)")
        self.assert_(bi._call_stack[0].done)
        
        result = bi.run()
        self.assertEquals(result, 3)
        
        self.assertEquals(bi._num_calls, 5)

    def test_eval_builtin_function_calls_nested(self):
        bi = dollop.BatchInterpreter()
        tokens = dollop.tokenize("(+ (+ 1 2) (+ 3 4))")
        tree = dollop.parse(tokens)
        bi._feed(tree)
        
        self.acs(bi, "(+ (+ 1 2) (+ 3 4))")
        
        bi.run()
        self.acs(bi, "($$ (+ 1 2) (+ 3 4)) +")
        
        bi.run()
        self.acs(bi, "(<lambda:+> $$ (+ 3 4)) (+ 1 2)")
        
        bi.run()
        self.acs(bi, "(<lambda:+> $$ (+ 3 4)) ($$ 1 2) +")

        bi.run()
        self.acs(bi, "(<lambda:+> $$ (+ 3 4)) (<lambda:+> $$ 2) 1")

        bi.run()
        self.acs(bi, "(<lambda:+> $$ (+ 3 4)) (<lambda:+> 1 $$) 2")

        bi.run()
        self.acs(bi, "(<lambda:+> $$ (+ 3 4)) (<lambda:+> 1 2)")
        self.assert_(bi._call_stack[-1].done)

        bi.run()
        self.acs(bi, "(<lambda:+> 3 $$) (+ 3 4)")
        
    def test_eval_define(self):
        bi = dollop.BatchInterpreter()
        tokens = dollop.tokenize("(define x 4)")
        tree = dollop.parse(tokens)
        bi._feed(tree)
        
        self.acs(bi, "(define x 4)")
        
        bi.run()
        self.acs(bi, "(define x $$) 4")
        
        bi.run()
        self.acs(bi, "(define x 4)")
        self.assert_(bi._call_stack[-1].done)
        
        result = bi.run()
        self.assertEquals(result, False)
        self.assert_(bi._env.get('x')[1], 4)
        
    def test_recursion(self):
        bi = dollop.BatchInterpreter()
        
        bi.eval("""
          (define fac
            (lambda (n)
              (if (= n 1)
                  1
                  (* n (fac (- n 1))))))""")
        result = bi.eval("(fac 10)")
        self.assertEquals(result, 3628800)
        self.assertEquals(bi._max_depth, 12) # 10 for fac calls
        
    def test_tail_recursion(self):
        bi = dollop.BatchInterpreter()
        
        bi.eval("""
          (define fac
            (lambda (n)
              (begin
                (define fac-aux
                  (lambda (n acc) 
                    (if (= n 1)
                        acc
                        (fac-aux (- n 1) (* acc n)))))
                (fac-aux n 1))))
        """)
        result = bi.eval("(fac 10)")
        self.assertEquals(result, 3628800)
        self.assertEquals(bi._max_depth, 3) # 1 for fac calls
        
    def acs(self, bi, s):
        self.assertEquals(bi.call_stack_repr(), s)
        