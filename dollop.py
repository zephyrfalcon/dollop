# dollop.py
# Requires: Python 3.0

"""
Interpreter for a very minimal subset of Lisp/Scheme. Its purpose is to
explore and demonstrate batch interpretation, tail recursion, etc.

Unlike other Lisp interpreter attempts (Mango, Liquid, etc), we represent
Lisp types by Python types.

Supported types:

Lisp                   represented as (in Python):
----                   --------------------------- 
list                   list
symbol                 string
integer                integer
built-in function      function
user-defined function  ...
boolean                boolean

We have the following special forms:

(begin e1 .. eN)
(define name value)
(if cond e1 e2)
(lambda (params) body)     [one expr in body]

And these built-in functions:

(+ a b)
(- a b)
(* a b)
(list ...exprs...)
(= a b)

TODO:

- Rewrite some parts in a more functional style, esp. where we change
  expressions in place (placeholder etc).  Instead, we may be able to
  just use a new expression.  That way, we won't have to use copy.deepcopy...
- Add a few more special forms like QUOTE, AND and OR

"""

import copy
import re
import types

def lisp_repr(obj):
    if isinstance(obj, list):
        return '({0})'.format(' '.join(lisp_repr(x) for x in obj))
    elif isinstance(obj, str):
        return str(obj)
    elif isinstance(obj, int):
        return repr(obj)
    elif isinstance(obj, types.FunctionType):
        return "<lambda:%s>" % obj.name
    elif isinstance(obj, Lambda):
        return "<lambda>"
    elif isinstance(obj, bool):
        return '#t' if obj else '#f'
    elif isinstance(obj, complex):
        # not really a supported type, but useful for debugging ^_^
        return '$$'
    else:
        raise ValueError("Unsupported type: %r" % obj)
        
def tokenize(s):
    """ Simple tokenizer that recognizes (, ), and "words" terminated by
        parentheses and whitespace. """
    tokens = []
    s = s.strip()
    while s:
        if s.startswith('('):
            tokens.append('(')
            s = s[1:]
        elif s.startswith(')'):
            tokens.append(')')
            s = s[1:]
        else:
            token = ""
            while s and s[:1] not in "() \n\t\r":
                token += s[:1]
                s = s[1:]
            tokens.append(token)
        s = s.lstrip()
        
    return tokens
        
def parse(tokens):
    """ Somewhat brain-damaged parser that parses one Lisp expression,
        converting types on the fly. """
    # only allows for one expression at the toplevel
    expr_stack = []
    for token in tokens:
        if token == '(':
            expr_stack.append([])
        elif token == ')':
            last_expr = expr_stack.pop()
            if expr_stack:
                expr_stack[-1].append(last_expr)
            else:
                return last_expr
        else:
            # TODO: figure out type, and convert it
            ctoken = convert_token(token)
            if expr_stack:
                expr_stack[-1].append(ctoken)
            else:
                return ctoken
            
    # TODO: check if parentheses are balanced
    return expr_stack[-1]
    
def convert_token(token):
    if re.match("^-?\d+$", token):
        return int(token)
    if token == '#t':
        return True
    if token == '#f':
        return False
    # anything else is a symbol
    return token
    
class Environment:
    def __init__(self, parent=None):
        self._data = {}
        self._parent = parent
    def bind(self, name, value):
        self._data[name] = value
    def rebind(self, name, value):
        env, old_value = self.get(name)
        env.bind(name, value)
    def get(self, name):
        try:
            value = self._data[name]
        except KeyError:
            if self._parent:
                return self._parent.get(name)
            else:
                raise NameError("Undefined name: %r" % name)
        return self, value

def with_name(f, name):
    f.name = name
    return f        
    
class Frame:
    def __init__(self, expr, env):
        self.expr = expr
        self.env = env
        self.done = False
    def lisp_repr(self):
        return lisp_repr(self.expr)
    
class Lambda:
    def __init__(self, params, body, env):
        self._params = params
        self._body = body
        self.env = env
    def params(self): return self._params[:]
    def body(self): return copy.deepcopy(self._body)
    # since we change expression in-place elsewhere, this should always be
    # a fresh copy w/o dependencies
    # alternatively, we could try to *not* change things in-place. :-}
    
class Continuation:
    def __init__(self, stack):
        self.stack = copy.deepcopy(stack)
    
PLACEHOLDER = 42j
SPECIAL_FORMS = ["begin", "define", "if", "lambda"]

def sf_apply(expr, env):
    """ Apply the special form.  Return a 2-tuple (result, done).  If done is 
        True, then result is treated as an evaluated result; otherwise, it
        is treated as an expression that needs to be evaluated further. """
    spname = expr[0]
    
    if spname == 'begin':
        return expr[-1], False # TCO
    
    if spname == 'define':
        name = expr[1]
        value = expr[2]
        env.bind(name, value)
        return False, True
        
    if spname == 'if':
        # TCO: replace the if statement with these expressions.
        if expr[1]:
            return expr[2], False
        else:
            return expr[3], False
            
    if spname == 'lambda':
        l = Lambda(expr[1], expr[2], env)
        return l, True
    
    raise NotImplementedError("sf_apply: %s" % expr)

def sf_next(expr, plpos):
    """ Determine the position of the next element to be evaluated. Return
        -1 when done. """
    spname = expr[0]
    
    if spname == 'begin':
        # (begin e1 .. eN)
        if plpos < len(expr) - 1:
            return plpos
        return -1 # don't evaluate last expr yet (TCO)
        
    elif spname == 'if':
        # (if cond eval-if-true eval-if-false)
        #  0   1    2            3
        if plpos < 2:
            return 1
        # we evaluate the other expressions elsewhere (conditionally)
        return -1
            
    elif spname == 'define':
        # (define name value)
        #  0       1    2
        if plpos < 2:
            return 2
        else:
            return -1
            
    elif spname == 'lambda':
        return -1 # don't evaluate anything
        
    else:
        raise ValueError("Unsupported special form: %s" % spname)

class BatchInterpreter:
    
    def __init__(self):
        self._call_stack = []
        self._env = self._create_toplevel_env()
        self._num_calls = 0
        self._max_depth = 0

    def _create_toplevel_env(self):
        env = Environment()
        env.bind('+', with_name(lambda x, y: x+y, '+'))
        env.bind('-', with_name(lambda x, y: x-y, '-'))
        env.bind('*', with_name(lambda x, y: x*y, '*'))
        env.bind('=', with_name(lambda x, y: x==y, '='))
        env.bind('list', with_name(lambda *args: list(args), 'list'))
        env.bind('call/cc', with_name(lambda f: self._call_cc(f), 'call/cc'))
        env.bind('magic', 42) # pre-defined variable
        return env
    
    def run(self):
        """ Execute the next step in the evaluation process. If we're done with
            the evaluation, return the result, otherwise None. """
        self._num_calls += 1
        self._max_depth = max(self._max_depth, len(self._call_stack))
            
        # what's on the call stack?
        frame = self._call_stack[-1]
        expr = frame.expr
        
        if isinstance(expr, list):
            # empty list just evaluates to itself (unlike Scheme)
            if expr == []:
                return expr
                
            if frame.done:
                if expr[0] in SPECIAL_FORMS:
                    result, done = sf_apply(expr, frame.env) # VERIFY
                    if done:
                        return self._collapse(result)
                    else:
                        self._call_stack.pop()
                        new_frame = Frame(expr=result, env=frame.env)
                        self._call_stack.append(new_frame)
                        return None
                elif isinstance(expr[0], Lambda):
                    f = expr[0]
                    # create new env (with lambda's env as parent)
                    newenv = Environment(parent=f.env)
                    # assign variables
                    assert len(expr[1:]) == len(f.params())
                    for name, value in zip(f.params(), expr[1:]):
                        newenv.bind(name, value)
                    newframe = Frame(expr=f.body(), env=newenv)
                    # then evaluate lambda body in that env!
                    self._call_stack.pop()
                    self._call_stack.append(newframe)
                    # no TCO here because this version of lambda only
                    # takes one expression... but BEGIN will have TCO, yes?
                    return None
                else:
                    # built-in function
                    value = self._apply(expr, frame.env) # VERIFY env
                    if value is None:
                        return None # used for call/cc stack manipulation
                    else:
                        return self._collapse(value)
                
            if expr[0] in SPECIAL_FORMS:
                plpos = sf_next(expr, 1)
                if plpos > -1:
                    subexpr = expr[plpos]
                    expr[plpos] = PLACEHOLDER
                    newframe = Frame(expr=subexpr, env=frame.env) # VERIFY env
                    self._call_stack.append(newframe)
                    return None
                else:
                    frame.done = True
                    return None

            # non-empty list: special form or function call
            # start at the beginning of the list
            # extract subexpr, substitute with placeholder, push subexpr
            subexpr = expr[0]
            expr[0] = PLACEHOLDER
            newframe = Frame(expr=subexpr, env=frame.env) # VERIFY env
            self._call_stack.append(newframe)
            return None
                
        elif isinstance(expr, str):
            # it's a symbol... look it up and return it
            _, value = frame.env.get(expr)
            return self._collapse(value)
            
        else:
            # anything else evaluates to itself
            return self._collapse(expr)
                    
    def _collapse(self, expr):
        """ Take an expression that we're done evaluating. If it's the last
            thing left on the call stack, return it. Otherwise, collapse it
            into the parent expression, i.e. replace PLACEHOLDER with the
            expression, then position the next subexpression (if any) to be
            evaluated, or mark the parent expression as done; return None. """ 
        if len(self._call_stack) == 1:
            return expr
        else:
            parent_frame = self._call_stack.pop()
            parent_expr = self._call_stack[-1].expr
            plpos = parent_expr.index(PLACEHOLDER)
            parent_expr[plpos] = expr
            
            if parent_expr[0] in SPECIAL_FORMS:
                plpos = sf_next(parent_expr, plpos+1)
                if plpos == -1:
                    self._call_stack[-1].done = True
                    return None
                else:
                    subexpr = parent_expr[plpos]
                    parent_expr[plpos] = PLACEHOLDER
                    newframe = Frame(expr=subexpr, env=parent_frame.env) # VERIFY
                    self._call_stack.append(newframe)
                    return None
                
            else:
                # normal evaluation
                if len(parent_expr) == plpos+1:
                    self._call_stack[-1].done = True
                    return None
                else:
                    # try next subexpr
                    plpos += 1
                    subexpr = parent_expr[plpos]
                    parent_expr[plpos] = PLACEHOLDER
                    newframe = Frame(expr=subexpr, env=parent_frame.env) # VERIFY
                    self._call_stack.append(newframe)
                    return None
            
    def eval(self, s):
        self.feed(s)
        
        while True:
            result = self.run()
            if result is not None:
                return result
                
    def _feed(self, expr):
        frame = Frame(expr=expr, env=self._env)
        self._call_stack = [frame]
        self._num_calls = 0
        
    def feed(self, s):
        tokens = tokenize(s)
        tree = parse(tokens)
        
        self._feed(tree)
                
    def _apply(self, lst, env):
        assert lst, "cannot apply empty list"
        f, args = lst[0], lst[1:]
        return f(*args)
        
    def call_stack_repr(self):
        return " ".join(f.lisp_repr() for f in self._call_stack)
        
    def _call_cc(self, f):
        assert isinstance(f, Lambda) # only lambdas for now
        assert len(f.params()) == 1
        cont = Continuation(self._call_stack)
        
        # define a new built-in function that simulates calling of the
        # continuation...
        def g(x):
            self._call_stack = copy.deepcopy(cont.stack)
            return x

        # XXX duplicate code, sort of (lambda expansion)
        newenv = Environment(parent=f.env)
        # assign variable
        newenv.bind(f.params()[0], with_name(g, "<cont>"))
        newframe = Frame(expr=f.body(), env=newenv)
        # then evaluate lambda body in that env!
        self._call_stack.pop()
        self._call_stack.append(newframe)

        # we just manipulate the call stack, but don't return a value
        return None
        