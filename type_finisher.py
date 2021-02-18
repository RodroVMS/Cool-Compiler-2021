
from collections import deque
from utils import find_possible_childs
import cmp.visitor as visitor
from AST import ProgramNode, ClassDeclarationNode, AttrDeclarationNode, FuncDeclarationNode, BlockNode, IfDeclarationNode
from AST import VarDeclarationNode, AssignNode, CallNode, BinaryNode, LetDeclarationNode, CaseDeclarationNode
from AST import ConstantNumNode, VariableNode, InstantiateNode, WhileDeclarationNode, OperationNode, ComparisonNode
from AST import ConstantStringNode, ConstantBoolNode, NotNode, IsVoidDeclarationNode, HyphenNode, CaseVarNode

from cmp.semantic import AutoType, SemanticError
from cmp.semantic import Attribute, Method, Type
from cmp.semantic import VoidType, ErrorType, IntType, SelfType
from cmp.semantic import Context, Scope

class TypeFinisher:
    def __init__(self, context):
        self.context:Context = context
        self.current_type = None
        self.values = ""

    @visitor.on('node')
    def visit(self, node):
        pass
    
    @visitor.when(ProgramNode)
    def visit(self, node, scope:Scope):
        for declaration in node.declarations:
            self.visit(declaration, scope.next_child())
        scope.reset()
    
    @visitor.when(ClassDeclarationNode)
    def visit(self, node, scope):
        self.current_type = self.context.get_type(node.id)
        
        for feature in node.features:
            self.visit(feature, scope)

    @visitor.when(AttrDeclarationNode)
    def visit(self, node, scope):
        var = scope.find_variable(node.id)
        if var:
            node.computed_type = self.update(node)
            var.type = node.computed_type
        else:
            node.computed_type = ErrorType()
            var.type = ErrorType()
        if node.expr:
            self.visit(node.expr, scope)
        self.log(f"Attribute Node {node.id} {node.computed_type.name}")

    @visitor.when(FuncDeclarationNode)
    def visit(self, node, scopex):
        scope = scopex.next_child()
        node.computed_type = self.update(node)
        method = self.current_type.get_method(node.id)
        for i in range(len(method.param_names)):
            idx, typex = (method.param_names[i], method.param_types[i])
            var = scope.find_variable(idx)
            var.type = self.update_var(var.type, strict=False)
            method.param_types[i] = self.update_var(typex, strict=False)
            assert var.type.conforms_to(method.param_types[i]) and method.param_types[i].conforms_to(var.type)

        self.log(f"Function Node {node.id}: {node.computed_type.name}")
        self.visit(node.body, scope)

    @visitor.when(BlockNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"Block Node: {node.computed_type.name}")
        for expr in node.body:
            self.visit(expr, scope)

    @visitor.when(WhileDeclarationNode)
    def visit(self, node : WhileDeclarationNode, scope):
        node.computed_type = self.update(node)
        self.log(f"While Node: {node.computed_type.name}")
        self.visit(node.whileexpr, scope)
        self.visit(node.bodyexpr, scope)

    @visitor.when(LetDeclarationNode)
    def visit(self, node : LetDeclarationNode, scope):
        node.computed_type = self.update(node)
        self.log(f"Let Node: {node.computed_type.name}")
        child = scope.next_child()
        for var in node.letvars:
            self.visit(var, child)
        self.visit(node.expr, child)

    @visitor.when(IfDeclarationNode)
    def visit(self, node:IfDeclarationNode, scope):
        node.computed_type = self.update(node)
        self.log(f"If Node: {node.computed_type.name}")
        self.visit(node.ifexpr, scope)
        self.visit(node.thenexpr, scope)
        self.visit(node.elseexpr, scope)

    @visitor.when(CaseDeclarationNode)
    def visit(self, node:CaseDeclarationNode, scope):
        node.computed_type = self.update(node)
        self.log(f"Case Node: {node.computed_type.name}")
        self.visit(node.expr, scope)
        for case_var in node.casevars:
            child = scope.next_child()
            self.visit(case_var, child)
            var = child.find_variable(case_var.id)
            var.type = self.update_var(var.type, strict=False)
            assert isinstance(var.type, Type), "var type is not type"

    @visitor.when(CallNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        node.computed_obj_type = node.computed_obj_type[-1]
        obj_type = node.computed_obj_type
        self.log(f"Call Node: ({obj_type.name}).{node.id}(...): {node.computed_type.name}")
        try:
            method = obj_type.get_method(node.id)
        except SemanticError as err:
            return
        
        if len(node.args) == len(method.param_types):
            for arg, param_type in zip(node.args, method.param_types):
                self.visit(arg, scope)

    @visitor.when(CaseVarNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"Case Var Node {node.id}: {node.computed_type.name}")
        self.visit(node.expr, scope)

    @visitor.when(VarDeclarationNode)
    def visit(self, node, scope):
        var = scope.find_variable(node.id)
        if var and node.define:
            node.computed_type = self.update(node)
            var.type = self.update_var(var.type)
        else:
            node.computed_type = ErrorType()
            var.type = ErrorType()
        self.log(f"Let Var Node {node.id}: {node.computed_type.name}")
        if node.expr:
                self.visit(node.expr, scope)

    @visitor.when(AssignNode)
    def visit(self, node, scope):
        if node.define:
            var = scope.find_variable(node.id)
            var.type = self.update_var(var.type)
            node.computed_type = self.update(node)
        else:
            node.computed_type = ErrorType()
        self.log(f"Assign Node {node.id}: {node.computed_type.name}")
        self.visit(node.expr, scope)

    @visitor.when(VariableNode)
    def visit(self, node, scope):
        if node.define:
            node.computed_type = self.update(node)
            var = scope.find_variable(node.lex)
            var.type = self.update_var(var.type)
        else:
            node.computed_type = ErrorType()
        self.log(f"Variable Node {node.lex}: {node.computed_type.name}")

    @visitor.when(IsVoidDeclarationNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"IsVoid Node: {node.computed_type.name}")
        self.visit(node.lex, scope)

    @visitor.when(NotNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"Not Node: {node.computed_type.name}")
        self.visit(node.lex, scope)

    @visitor.when(HyphenNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"Hyphen Node: {node.computed_type.name}")
        self.visit(node.lex, scope)

    @visitor.when(InstantiateNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"Instantiate Node {node.lex}: {node.computed_type.name}")

    @visitor.when(OperationNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"Operation Node: {node.computed_type.name}")
        self.visit(node.left, scope)
        
        self.visit(node.right, scope)

    @visitor.when(ComparisonNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"Comparison Node: {node.computed_type.name}")
        self.visit(node.left, scope)
        
        self.visit(node.right, scope)

    
    @visitor.when(ConstantNumNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"Constant Num Node: {node.computed_type.name}")
    
    @visitor.when(ConstantStringNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"Constant String Node: {node.computed_type.name}")
    
    @visitor.when(ConstantBoolNode)
    def visit(self, node, scope):
        node.computed_type = self.update(node)
        self.log(f"Constant Bool Node: {node.computed_type.name}")

    def update(self,node, strict = True):
        try:
            typex = node.computed_type
        except AttributeError:
            node.computed_type = ErrorType()
            return ErrorType()
        if isinstance(typex, Type):
            return typex
        if len(typex) == 0:
            return ErrorType()
        if strict:
            return self.find_lowest_ancestor(typex)
        return typex[-1]
    
    def update_var(self, typex, strict = True):
        if isinstance(typex, Type):
            return typex
        if len(typex) == 0:
            return ErrorType()
        if strict:
            return self.find_lowest_ancestor(typex)
        return typex[-1]

    def find_lowest_ancestor(self, type_list):
        if isinstance(type_list, Type):
            return type_list

        upper = type_list[-1] if not isinstance(type_list[-1], SelfType) else self.current_type
        if isinstance(upper, ErrorType):
            return ErrorType()
        upper = upper.name
        type_tree = self.context.type_tree
        type_set = set(type_list)

        children = type_tree[upper]
        possible_child = find_possible_childs(children, type_set, self.context)
        while len(possible_child) == 1:
            upper = children[possible_child[0]]
            children = type_tree[upper]
            possible_child = find_possible_childs(children, type_set, self.context)
        return self.context.get_type(upper)
    
    def log(self, s:str):
        self.values += f"In class {self.current_type.name} -> " + s + "\n"