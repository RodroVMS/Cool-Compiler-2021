import cmp.visitor as visitor
from AST import HyphenNode, IsVoidDeclarationNode, NotNode, ProgramNode,ClassDeclarationNode,AttrDeclarationNode,VarDeclarationNode,AssignNode,FuncDeclarationNode,BinaryNode
from AST import AtomicNode,CallNode,InstantiateNode, IfDeclarationNode, LetDeclarationNode, CaseDeclarationNode, WhileDeclarationNode
from AST import BlockNode

class FormatVisitor(object):
    @visitor.on('node')
    def visit(self, node, tabs):
        pass
    
    @visitor.when(ProgramNode)
    def visit(self, node, tabs=0):
        ans = '\t' * tabs + f'\\__ProgramNode [<class> ... <class>]'
        statements = '\n'.join(self.visit(child, tabs + 1) for child in node.declarations)
        return f'{ans}\n{statements}'
    
    @visitor.when(ClassDeclarationNode)
    def visit(self, node, tabs=0):
        parent = '' if node.parent is None else f": {node.parent}"
        ans = '\t' * tabs + f'\\__ClassDeclarationNode: class {node.id} {parent} {{ <feature> ... <feature> }}'
        features = '\n'.join(self.visit(child, tabs + 1) for child in node.features)
        return f'{ans}\n{features}'
    
    @visitor.when(AttrDeclarationNode)
    def visit(self, node, tabs=0):
        ans = '\t' * tabs + f'\\__AttrDeclarationNode: {node.id} : {node.type}'
        if node.expr != None:
            ans += f"\n{self.visit(node.expr, tabs +1)}"
        return f'{ans}'
    
    @visitor.when(VarDeclarationNode)
    def visit(self, node, tabs=0):
        ans = '\t' * tabs + f'\\__VarDeclarationNode: {node.id} : {node.type} = <expr>'
        if node.expr != None:
            ans += f'\n{self.visit(node.expr, tabs + 1)}'
        return f'{ans}'

    @visitor.when(BlockNode)
    def visit(self, node, tabs=0):
        ans = '\t' * tabs + '\\__BlockNode: { <expr>; ... <expr>; }'
        body = '\n'.join(self.visit(child, tabs + 1) for child in node.body)
        return f'{ans}\n{body}'
    
    @visitor.when(IfDeclarationNode)
    def visit(self, node, tabs=0):
        ifexpr = self.visit(node.ifexpr, tabs + 1)
        thenexpr = self.visit(node.thenexpr, tabs + 1)
        elseexpr = self.visit(node.elseexpr,tabs + 1)
        ans = '\t' * tabs + f'\\__IfDeclarationNode: if <expr> then <expr> else <expr> \n'
        ifs = '\t' * (tabs + 1) + f'if:\n{ifexpr}\n'
        ths = '\t' * (tabs + 1) + f'then:\n{thenexpr}\n'
        els = '\t' * (tabs + 1) + f'else:\n{elseexpr}\n'
        ans = ans + ifs + ths + els
        return ans
    
    @visitor.when(CaseDeclarationNode)
    def visit(self, node, tabs=0):
        header = '\t' * tabs + f'\\__CaseDeclarationNode: case <expr> of ( <var> => <expr> ...)\n'
        caseexpr = self.visit(node.expr, tabs + 1)
        case = '\t' * (tabs + 1) + f'case:\n{caseexpr}\n'
        casevars =  '\n'.join(self.visit(child, tabs + 1) for child in node.casevars)
        of = '\t' * (tabs + 1) + f'of:\n{casevars}\n'
        return header + case + of

    @visitor.when(LetDeclarationNode)
    def visit(self, node, tabs=0):
        header = '\t' * tabs + f'\\__LetDeclarationNode: Let (<var> <- <expr> ...) in <expr>\n'
        letvars = '\n'.join(self.visit(child, tabs + 1) for child in node.letvars)
        expr = self.visit(node.expr, tabs + 1)
        let = '\t' * (tabs + 1) + f'let: \n{letvars}\n'
        inx = '\t' * (tabs + 1) + f'in: \n{expr}'
        return header + let + inx
    
    @visitor.when(WhileDeclarationNode)
    def visit(self, node, tabs=0):
        header = '\t' * tabs + f'\\__WhileDeclarationNode: while <expr> loop ( <expr> ... <expr> )\n'
        body =  self.visit(node.bodyexpr, tabs + 1) 
        whilex = self.visit(node.whileexpr, tabs + 1) + '\n'
        text1 =  '\t' * (tabs + 1) + f'while:\n {whilex}'
        text2 =  '\t' * (tabs + 1) + f'loop:\n {body}'
        return header + text1 + text2

    @visitor.when(AssignNode)
    def visit(self, node, tabs=0):
        ans = '\t' * tabs + f'\\__AssignNode: {node.id} = <expr>'
        expr = self.visit(node.expr, tabs + 1)
        return f'{ans}\n{expr}'
    
    @visitor.when(FuncDeclarationNode)
    def visit(self, node, tabs=0):
        params = ', '.join(':'.join(param) for param in node.params)
        ans = '\t' * tabs + f'\\__FuncDeclarationNode: {node.id}({params}) : {node.type} -> <body>'
        body = '\n' + self.visit(node.body, tabs + 1)
        return f'{ans}{body}'

    @visitor.when(IsVoidDeclarationNode)
    def visit(self, node, tabs=0):
        ans1 = '\t' * tabs + f'\\__IsVoidNode: isvoid <expr>'
        ans2 = self.visit(node.lex, tabs+1)
        return ans1 + "\n" + ans2
    
    @visitor.when(HyphenNode)
    def visit(self, node, tabs=0):
        ans1 = '\t' * tabs + f'\\__HyphenNode: ~ <expr>'
        ans2 = self.visit(node.lex, tabs+1)
        return ans1 + "\n" + ans2
    
    @visitor.when(NotNode)
    def visit(self, node, tabs=0):
        ans1 = '\t' * tabs + f'\\__NotNode: not <expr>'
        ans2 = self.visit(node.lex, tabs+1)
        return ans1 + "\n" + ans2

    @visitor.when(BinaryNode)
    def visit(self, node, tabs=0):
        ans = '\t' * tabs + f'\\__<expr> {node.__class__.__name__} <expr>'
        left = self.visit(node.left, tabs + 1)
        right = self.visit(node.right, tabs + 1)
        return f'{ans}\n{left}\n{right}'

    @visitor.when(AtomicNode)
    def visit(self, node, tabs=0):
        return '\t' * tabs + f'\\__ {node.__class__.__name__}: {node.lex}'
    
    @visitor.when(CallNode)
    def visit(self, node, tabs=0):
        obj = self.visit(node.obj, tabs + 1)
        ans = '\t' * tabs + f'\\__CallNode: <obj>.{node.id}(<expr>, ..., <expr>)'
        args = '\n'.join(self.visit(arg, tabs + 1) for arg in node.args)
        return f'{ans}\n{args}'#old f'{ans}\n{obj}\n{args}'
    
    @visitor.when(InstantiateNode)
    def visit(self, node, tabs=0):
        return '\t' * tabs + f'\\__ InstantiateNode: new {node.lex}()'