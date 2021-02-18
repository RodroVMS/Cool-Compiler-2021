import types
from collections import deque
from os import error

import cmp.visitor as visitor
from AST import (
    AssignNode, AttrDeclarationNode, BinaryNode, BlockNode,
    CallNode, CaseDeclarationNode, CaseVarNode,
    ClassDeclarationNode, ComparisonNode, ConstantBoolNode,
    ConstantNumNode, ConstantStringNode, FuncDeclarationNode,
    HyphenNode, IfDeclarationNode, InstantiateNode,
    IsVoidDeclarationNode, LetDeclarationNode, NotNode,
    OperationNode, ProgramNode, VarDeclarationNode, VariableNode,
    WhileDeclarationNode
    )
from cmp.semantic import (
    Attribute, AutoType, Context, ErrorType, IntType,
    Method, Scope, SelfType, SemanticError, Type,
    VoidType
    )
from utils import global_upper_graph, set_global_upper

WRONG_SIGNATURE = 'Method "%s" already defined in "%s" with a different signature.'
SELF_IS_READONLY = 'Variable "self" is read-only.'
LOCAL_ALREADY_DEFINED = 'Variable "%s" is already defined.'
INCOMPATIBLE_TYPES = 'Cannot convert "%s" into "%s".'
VARIABLE_NOT_DEFINED = 'Variable "%s" is not defined.'
INVALID_OPERATION = 'Operation is not defined between "%s" and "%s".'

class TypeLinker:
    def __init__(self, context,  inference_graph):
        self.context:Context = context
        self.current_type = None
        self.current_method = None
        self.current_attrb = None
        self.errors = []
        self.inferenced = set()
        self.ok = set_global_upper(inference_graph) 
        self.inference_graph = inference_graph
        self.global_graph = global_upper_graph(self.inference_graph) if self.ok else dict()
    
    @visitor.on('node')
    def visit(self, node, scope):
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
    def visit(self, node, scope : Scope):
        self.current_attrb = self.current_type.get_attribute(node.id)
        node_type = self.all_pos_types(self.current_attrb.type)
        
        if not node.expr:
            node.computed_type = node_type
            self.current_attrb = None
            return

        self.visit(node.expr, scope)
        expr_type = node.expr.computed_type

        error_type = node_type.copy()
        error_expr = expr_type.copy()

        self.establish_conform(expr_type, node_type)
        if len(expr_type)*len(node_type) == 0:
            self.errors.append(f"Declaring Attribute {node.id} in class {self.current_type.name}. Incompatible types between possible declared types (" + ", ".join([typex.name for typex in error_type]) + ") and possible expression types (" + ", ".join([typex.name for typex in error_expr]) + ")")
            node.computed_type = ErrorType()
        else:
            node.computed_type = node_type
        var = scope.find_variable(node.id)
        var.type = node.computed_type
        self.current_attrb = None

    @visitor.when(FuncDeclarationNode)
    def visit(self, node, scopex: Scope):
        scope = scopex.next_child()
        self.current_method = self.current_type.get_method(node.id)
        self.current_method.return_type = self.all_pos_types(self.current_method.return_type)

        for i in range(len(self.current_method.param_names)):
            idx, typex = (self.current_method.param_names[i], self.current_method.param_types[i])
            var = scope.find_variable(idx)
            var.type = self.all_pos_types(var.type)
            self.current_method.param_types[i] = var.type

        self.visit(node.body, scope)
        
        ret_type_expr = node.body.computed_type
        ret_type_decl = self.current_method.return_type

        error_type = ret_type_decl.copy()
        error_expr = ret_type_expr.copy()
        self.establish_conform(ret_type_expr, ret_type_decl)
        if len(ret_type_decl)*len(ret_type_expr) == 0:
            self.errors.append(f"Declaring Function {node.id} in class {self.current_type.name}: incompatible types between possible declared return types (" + ", ".join([typex.name for typex in error_type]) + ") and possible expression return types (" + ", ".join([typex.name for typex in error_expr]) + ")")
            node.computed_type = ErrorType()
        else:
            node.computed_type = ret_type_decl
        self.current_method = None

    @visitor.when(BlockNode)
    def visit(self, node, scope : Scope):
        for expr in node.body:
            self.visit(expr, scope)
        node.computed_type = node.body[-1].computed_type

    @visitor.when(WhileDeclarationNode)
    def visit(self, node : WhileDeclarationNode, scope : Scope):
        self.visit(node.whileexpr, scope)
        pred_type = node.whileexpr.computed_type
        bool_type = self.context.get_type("Bool")

        pred_error = pred_type.copy()
        self.conform_list(pred_type, bool_type)
        if len(pred_type) == 0:
            self.AddError("Impossible to evaluate While expression: Possible predicate types(" + ",".join([typex.name for typex in pred_error]) +") does not conforms to Bool")
            pred_type = ErrorType()
        
        self.visit(node.bodyexpr, scope)
        node.computed_type = [self.context.get_type("Object")]

    @visitor.when(LetDeclarationNode)
    def visit(self, node : LetDeclarationNode, scopex : Scope):
        scope = scopex.next_child()
        for var in node.letvars:
            self.visit(var, scope)
        self.visit(node.expr, scope)
        node.computed_type = node.expr.computed_type

    @visitor.when(IfDeclarationNode)
    def visit(self, node:IfDeclarationNode, scope:Scope):
        self.visit(node.ifexpr, scope)
        if_type = node.ifexpr.computed_type
        bool_type = self.context.get_type("Bool")
        pred_error = if_type.copy()
        self.conform_list(if_type, bool_type)
        if len(if_type) == 0:
            self.AddError("Impossible to evaluate If expression: Possible predicate types(" + ",".join([typex.name for typex in pred_error]) +") does not conforms to Bool")
            node.ifexpr.computed_type = ErrorType()

        self.visit(node.thenexpr, scope)
        #then_type = node.thenexpr.computed_type
        #node.thenexpr.computed_type = then_type

        self.visit(node.elseexpr, scope)
        #else_type = node.elseexpr.computed_type
        #node.elseexpr.computed_type = else_type

        node.computed_type = self.all_pos_types(node.inferenced_type)

    @visitor.when(CaseDeclarationNode)
    def visit(self, node:CaseDeclarationNode, scope:Scope):
        self.visit(node.expr, scope)
        case_expr_type = node.expr.computed_type
        if isinstance(case_expr_type, VoidType):#arreglar esto case expr es ahora una lista
            self.AddError(f"Case expression evaluated void.")
            case_expr_type = [ErrorType()]
            node.expr.computed_type  = case_expr_type
        
        var_types = set()
        found = False
        for case_var in node.casevars:
            child = scope.next_child()
            self.visit(case_var, child)
            var = child.find_variable(case_var.id)
            var.type = self.all_pos_types(var.type)
            var_type = var.type
            if var_type[0] in var_types:
                self.AddError(f"Equal types of \"{var_type.name}\" detected on case expression.")
            else:
                assert len(var_type) == 1, "Var type mayor que 1 big oof"
                var_types.add(var_type[0])

        for typex in var_types:
            for expr in case_expr_type:
                if expr.conforms_to(typex):
                    found = True
                    break
            if found:
                break
        else:
            self.AddError(f"No branch(" + ",".join(typex.name for typex in var_types) + ") conforms to possible Case Expresion types: " + ", ".join([typex.name for typex in case_expr_type]))
            node.computed_type = [ErrorType()]
            return
        node.computed_type = self.all_pos_types(node.inferenced_type)

    @visitor.when(CallNode)
    def visit(self, node, scope):
        obj_type = self.all_pos_types(node.inferenced_obj_type)
        node.computed_obj_type = obj_type
        try:
            method = obj_type[-1].get_method(node.id)
        except SemanticError as err:
            self.AddError(err.text)
            node.computed_type = [ErrorType()]
            return
        
        method.return_type = self.all_pos_types(method.return_type)
        ret_type = method.return_type
        if len(node.args) == len(method.param_types):
            count = 0
            for arg, param_type in zip(node.args, method.param_types):
                self.visit(arg, scope)
                arg_type = arg.computed_type
                param_type = self.all_pos_types(param_type)
                method.param_types[count] = param_type

                arg_error = arg_type.copy()
                param_error = param_type.copy()
                self.establish_conform(arg_type, param_type)
                count += 1
                if len(param_type)*len(arg_type) == 0:
                    self.AddError(f"While calling \"{method.name}\". Argument({count + 1}) incompatibility between argument possible types: " + ", ".join([typex.name for typex in arg_error]) + " and parameters possible types:" + ", ".join([typex.name for typex in param_error]))
        else:
            self.AddError(f"Method \"{method.name}\" takes \"{len(method.param_types)}\" arguments, instead {len(node.args)} were given.")
        
        node.computed_type = method.return_type.copy()
        for i in range(len(node.computed_type)):
            typex = node.computed_type[i]
            if isinstance(typex, SelfType):
                node.computed_type[i] = obj_type[-1]
                break

    @visitor.when(CaseVarNode)
    def visit(self, node, scope):
        self.check_id(node.id)
        try:
            node_type = self.context.get_type(node.type, selftype = False, autotype = False)
        except SemanticError as err:
            self.errors.append(err.text)
            node_type = ErrorType()

        self.visit(node.expr, scope)
        node.computed_type = node.expr.computed_type #Ya a node.expr se le debio haber hecho all_types

    @visitor.when(VarDeclarationNode)
    def visit(self, node, scope:Scope):
        try:
            node_type = self.context.get_type(node.type) if node.type != "SELF_TYPE" else self.current_type
        except SemanticError as err:
            self.errors.append(err.text)
            node_type = [ErrorType()]
        self.check_id(node.id)
        if node.define and scope.is_local(node.id):
            var = scope.find_variable(node.id)
            var.type = self.all_pos_types(var.type)

        if node.expr:
            self.visit(node.expr, scope)
            expr_type = node.expr.computed_type
            node_type = self.all_pos_types(node_type)

            error_expr = expr_type.copy()
            error_type = node_type.copy()
            self.establish_conform(expr_type, node_type)
            if len(expr_type)*len(node_type) == 0:
                self.AddError(f"Declaring Let Variable {node.id}. Incompatible types between possible declared types (" + ", ".join([typex.name for typex in error_type]) + ") and possible expression types (" + ", ".join([typex.name for typex in error_expr]) + ")")
                node_type = [ErrorType()]
        
        node.computed_type = node_type

    @visitor.when(AssignNode)
    def visit(self, node, scope):
        var = scope.find_variable(node.id)
        if node.define:
            var.type = self.all_pos_types(var.type)
            var_type = var.type
            self.visit(node.expr, scope)
            expr_type = node.expr.computed_type
            
            error_expr = expr_type.copy()
            error_type = var_type.copy()
            self.establish_conform(var_type, expr_type)
            if len(var_type)*len(expr_type) == 0:
                self.AddError(f"Cant assign new value to {node.id}. Incompatible types between defined variable declared types (" + ", ".join([typex.name for typex in error_type]) + ") and possible expression types (" + ", ".join([typex.name for typex in error_expr]) + ")")
                var_type = [ErrorType()]
            if var.name == 'self':
                self.AddError("Cant Assign:", SELF_IS_READONLY)
                var_type = [ErrorType()]
        else:
            self.AddError("Cant Assign:",VARIABLE_NOT_DEFINED.replace('%s', node.id, 1))
            var_type = [ErrorType()]
        node.computed_type = var_type #No es necesario hacerle un al pos

    #chequear que se quiten valores de var.type cuando se hagan un conform
    @visitor.when(VariableNode)
    def visit(self, node, scope):
        if node.define:
            var = scope.find_variable(node.lex)
            var.type = self.all_pos_types(var.type)
            node.computed_type = var.type
        else:
            self.AddError(VARIABLE_NOT_DEFINED.replace('%s', node.lex, 1))
            node.computed_type  = [ErrorType()]

    @visitor.when(IsVoidDeclarationNode)
    def visit(self, node, scope):
        self.visit(node.lex, scope)
        node.computed_type = [self.context.get_type("Bool")]

    @visitor.when(NotNode)
    def visit(self, node, scope):
        self.visit(node.lex, scope)
        lex_type = node.lex.computed_type
        lex_error = lex_type.copy()
        bool_type = self.context.get_type("Bool")
        self.conform_list(lex_type, bool_type)
        if len(lex_type) == 0:
            self.AddError("Computing Not Expression: None of the expression possible values(" +", ".join([typex.name for typex in lex_error]) +") conforms to Bool")
            node.computed_type = [ErrorType()]
        
        node.computed_type = [bool_type]

    @visitor.when(HyphenNode)
    def visit(self, node, scope):
        self.visit(node.lex, scope)
        lex_type = node.lex.computed_type
        lex_error = lex_type.copy()
        int_type = self.context.get_type("Int")
        self.conform_list(lex_type, int_type)
        if len(lex_type) == 0:
            self.AddError("Computing Hyphen Expression: None of the expression possible values(" +", ".join([typex.name for typex in lex_error]) +") conforms to Int")
            lex_type = [ErrorType()]
        
        node.computed_type = [int_type] #Not all posible because lex is already a list

    @visitor.when(InstantiateNode)
    def visit(self, node, scope):
        try:
            node_type = self.context.get_type(node.lex, selftype = False, autotype=False)
        except SemanticError as err:
            self.AddError(f"Unable to instantiate:",err.text)
            node_type = [ErrorType()]
        node.computed_type =  self.all_pos_types(node_type)

    @visitor.when(OperationNode)
    def visit(self, node, scope):
        self.visit(node.left, scope)
        left_type = node.left.computed_type
        
        self.visit(node.right, scope)
        right_type = node.right.computed_type

        left_error = left_type.copy()
        right_error = right_type.copy()
        int_type = self.context.get_type("Int")
        self.conform_list(left_type, int_type)
        self.conform_list(right_type, int_type)
        if  len(left_type)*len(right_type) == 0:
            s = "Performing Arithmetic Operation:"
            if not len(left_type):
                s += ("\n   -None of the left memeber possible values("+ ",".join(typex.name for typex in left_error) +") conforms to Int")
            if not len(right_type):
                s += ("\n   -None of the right memeber possible values("+ ",".join(typex.name for typex in right_error) +") conforms to Int")
            self.AddError(s)
            node_type = [ErrorType()]
        else:
            node_type = [int_type]
        
        node.computed_type = node_type

    @visitor.when(ComparisonNode)
    def visit(self, node, scope):
        self.visit(node.left, scope)
        left_type = node.left.computed_type
        
        self.visit(node.right, scope)
        right_type = node.right.computed_type

        left_error = left_type.copy()
        right_error = right_type.copy()
        ancestors = self.get_common_ancestors(left_type, right_type)
        self.conform_list(left_type, ancestors)
        self.conform_list(right_type, ancestors)
        if len(left_type)*len(right_type) == 0:
            self.AddError(f"Performing Comparison: None of the left member possible values("+",".join(typex.name for typex in left_error)+") conforms to the right member possible values("+",".join(typex.name for typex in left_error)+")")
            node_type = [ErrorType()]
        else:
            node_type = [self.context.get_type("Bool")]
        
        node.computed_type = node_type

    
    @visitor.when(ConstantNumNode)
    def visit(self, node, scope):
        node.computed_type = self.all_pos_types(node.inferenced_type)
    
    @visitor.when(ConstantStringNode)
    def visit(self, node, scope):
        node.computed_type = self.all_pos_types(node.inferenced_type)
    
    @visitor.when(ConstantBoolNode)
    def visit(self, node, scope):
        node.computed_type = self.all_pos_types(node.inferenced_type)

    def establish_conform(self, expr, decl, *common_ancestors):
        if len(decl) == 0:
            decl = [ErrorType()]
        if len(expr) == 0:
            expr = [ErrorType()]
        
        if not common_ancestors:
            common_ancestors = self.get_common_ancestors(expr, decl)

        self.conform_list(decl, common_ancestors)
        self.conform_list(expr, common_ancestors, left_to_right=True)

    def all_pos_types(self, typex):
        if isinstance(typex, (list, deque)):
            return typex
        if not isinstance(typex, AutoType):
            return [typex]

        type_set = typex.type_set
        result =  sorted(list(type_set), key=lambda x: -x.index)
        return result

    def conform_list(self, types:list, common_ancestor, left_to_right=False):
        if isinstance(common_ancestor, Type):
            common_ancestor = [common_ancestor]
        conformed = set()
        for typex in common_ancestor:
            typex = self.update_type(typex)
            for i in range(len(types)):
                if types[i] in conformed:
                    continue
                if not left_to_right:
                    if typex.conforms_to(self.update_type(types[i])):
                        conformed.add(types[i])
                else:
                    if self.update_type(types[i]).conforms_to(typex):
                        conformed.add(types[i])
        
        pop_list = deque()
        for i in range(len(types)):
            if not types[i] in conformed:
                pop_list.appendleft(i)
        for i in pop_list:
            types.pop(i)
        return types

    def get_common_ancestors(self, expr, decl):
        common_ancestors = set()
        for e in expr:
                e = self.update_type(e)
                for d in decl:
                    d = self.update_type(d)
                    common = d.least_common_ancestor(e)
                    if not isinstance(common, ErrorType):
                        common_ancestors.add(common)
        return common_ancestors

    def update_type(self, typex:Type):
        if isinstance(typex, SelfType):
            return self.current_type
        return typex

    def check_id(self, name:str):
        if name[0] != name[0].lower():
            self.AddError(f"Error in \"{name}\". Objects different than types must start with lower case.")

    def AddError(self, extra = "", prefixed = ""):
        current_type = f"In class \"{self.current_type.name}\", "
        current_loc = f"in method \"{self.current_method.name}\". " if self.current_method else ""  
        current_loc = f"in attribute \"{self.current_attrb.name}\". " if self.current_attrb else current_loc
        self.errors.append(current_type + current_loc + extra + " " + prefixed)
