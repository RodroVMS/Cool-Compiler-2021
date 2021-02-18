import cmp.visitor as visitor
from AST import ProgramNode, ClassDeclarationNode, AttrDeclarationNode, FuncDeclarationNode, BlockNode, IfDeclarationNode
from AST import VarDeclarationNode, AssignNode, CallNode, BinaryNode, LetDeclarationNode, CaseDeclarationNode
from AST import ConstantNumNode, VariableNode, InstantiateNode, WhileDeclarationNode, OperationNode, ComparisonNode
from AST import ConstantStringNode, ConstantBoolNode, NotNode, IsVoidDeclarationNode, HyphenNode, CaseVarNode

from cmp.semantic import AutoType, SemanticError
from cmp.semantic import Attribute, Method, Type
from cmp.semantic import VoidType, ErrorType, IntType, SelfType
from cmp.semantic import Context, Scope

WRONG_SIGNATURE = 'Method "%s" already defined in "%s" with a different signature.'
SELF_IS_READONLY = 'Variable "self" is read-only.'
LOCAL_ALREADY_DEFINED = 'Variable "%s" is already defined.'
INCOMPATIBLE_TYPES = 'Cannot convert "%s" into "%s".'
VARIABLE_NOT_DEFINED = 'Variable "%s" is not defined.'
INVALID_OPERATION = 'Operation is not defined between "%s" and "%s".'

class TypeChecker:
    def __init__(self, context, errors=[]):
        self.context = context
        self.current_type = None
        self.current_method = None
        self.current_attrb = None
        self.errors = errors

    @visitor.on('node')
    def visit(self, node, scope):
        pass

    @visitor.when(ProgramNode)
    def visit(self, node, scope=None):
        scope = Scope()
        for declaration in node.declarations:
            self.visit(declaration, scope.create_child())
        return scope

    @visitor.when(ClassDeclarationNode)
    def visit(self, node, scope):
        self.current_type = self.context.get_type(node.id)

        scope.define_variable('self', self.current_type)
        for attr in self.current_type.attributes:
            scope.define_variable(attr.name, attr.type)
        
        for feature in node.features:
            self.visit(feature, scope.create_child())
        
    @visitor.when(AttrDeclarationNode)
    def visit(self, node, scope : Scope):
        self.current_attrb = self.current_type.get_attribute(node.id)
        node_type = self.update_type(self.context.get_type(node.type))
        
        if not node.expr:
            node.computed_type = node_type
            self.current_attrb = None
            return

        self.visit(node.expr, scope)
        expr_type = self.update_type(node.expr.computed_type)
        if not expr_type.conforms_to(node_type):
            self.errors.append("Declaring Attribute:", INCOMPATIBLE_TYPES.replace('%s', expr_type.name, 1).replace('%s', node_type.name, 1))
            node.computed_type = ErrorType()
        else:
            node.computed_type = node_type
        var = scope.find_variable(node.id)
        var.type = node.computed_type
        self.current_attrb = None
    
    @visitor.when(FuncDeclarationNode)
    def visit(self, node, scope : Scope):
        self.current_method = self.current_type.get_method(node.id)
        
        for idx, typex in zip(self.current_method.param_names, self.current_method.param_types):
            scope.define_variable(idx, typex)
            
        self.visit(node.body, scope)
        
        ret_type_decl = self.update_type(self.current_method.return_type)
        ret_type_expr = self.update_type(node.body.computed_type)
        if not ret_type_expr.conforms_to(ret_type_decl):
            self.AddError("Incompatible Return Types",INCOMPATIBLE_TYPES.replace('%s', ret_type_decl.name, 1).replace('%s', ret_type_expr.name, 1))
        
        self.current_method = None
    
    @visitor.when(BlockNode)
    def visit(self, node, scope : Scope):
        for expr in node.body:
            self.visit(expr, scope)
        node.computed_type = node.body[-1].computed_type
    
    @visitor.when(IfDeclarationNode)
    def visit(self, node : IfDeclarationNode, scope : Scope):
        self.visit(node.ifexpr, scope)
        ifexpr_type = node.ifexpr.computed_type
        bool_type = self.context.get_type("Bool")
        if not ifexpr_type.conforms_to(bool_type):
            self.AddError("If predicate is not Bool:", INCOMPATIBLE_TYPES.replace('%s', ifexpr_type.name, 1).replace('%s', bool_type.name, 1))
            ifexpr_type = ErrorType()

        self.visit(node.thenexpr, scope)
        then_type = node.thenexpr.computed_type
        then_type = self.update_type(then_type)

        self.visit(node.elseexpr, scope)
        else_type = node.elseexpr.computed_type 
        else_type = self.update_type(else_type)

        typex = else_type.least_common_ancestor(then_type)
        if typex == None:
            self.AddError("The \"then\" and \"else\" expressions have different types with no common ancestor.")
            node.computed_type = ErrorType()
        else:
            node.computed_type = typex

    @visitor.when(WhileDeclarationNode)
    def visit(self, node : WhileDeclarationNode, scope : Scope):
        self.visit(node.whileexpr, scope)
        pred_type = node.whileexpr.computed_type
        bool_type = self.context.get_type("Bool")
        if not pred_type.conforms_to(bool_type):
            self.AddError("Cant Evaluate While Expression:",INCOMPATIBLE_TYPES.replace('%s', pred_type.name, 1).replace('%s', bool_type.name, 1))
            pred_type = ErrorType()
        
        self.visit(node.bodyexpr, scope)
        node.computed_type = self.context.get_type("Object")

    @visitor.when(LetDeclarationNode)
    def visit(self, node : LetDeclarationNode, scopex : Scope):
        scope = scopex.create_child()
        for var in node.letvars:
            self.visit(var, scope)
        self.visit(node.expr, scope)
        node.computed_type = node.expr.computed_type
    
    @visitor.when(CaseDeclarationNode)
    def visit(self, node : CaseDeclarationNode, scope : Scope):
        self.visit(node.expr, scope)
        case_expr_type = node.expr.computed_type if not isinstance(node.expr.computed_type, SelfType) else self.current_type
        if isinstance(case_expr_type, VoidType):
            self.AddError(f"Case expression evaluated void.")
            case_expr_type = ErrorType()
        
        var_names = set()
        general_type = None
        found = False
        for var in node.casevars:
            child = scope.create_child()
            self.visit(var, child)
            var_type = var.computed_type
            if var_type.name in var_names:
                self.AddError(f"Equal types of \"{var_type.name}\" detected on case expression.")
            else: 
                var_names.add(var.computed_type.name)
            
            try:
                general_type = general_type.least_common_ancestor(var_type) if general_type else var_type
            except SemanticError as err:
                self.AddError(f"In Case Expression, in branch \"{var.id}:{var.type}\":",err.text)

            if not found and case_expr_type.conforms_to(var.computed_type):
                found = True

        if not found:
            self.AddError(f"No branch conforms to Case Expresion Type \"{case_expr_type.name}\"")
            node.computed_type = ErrorType()
        else:
            node.computed_type = general_type

    @visitor.when(CaseVarNode)
    def visit(self, node, scope):
        try:
            node_type = self.update_type(self.context.get_type(node.type, selftype = False, autotype = False))# if node.type != "SELF_TYPE" else SelfType()
        except SemanticError as err:
            self.errors.append(err.text)
            node_type = ErrorType()

        scope.define_variable(node.id, node_type)

        self.visit(node.expr, scope)
        expr_type = node.expr.computed_type
        #if not expr_type.conforms_to(node_type):
        #    self.AddError(f"Declaring Case Variable \"{node.id}\":",INCOMPATIBLE_TYPES.replace('%s', expr_type.name, 1).replace('%s', node_type.name, 1))
        #    node_type = ErrorType()

        node.computed_type = expr_type

    @visitor.when(VarDeclarationNode)
    def visit(self, node, scope):
        try:
            node_type = self.context.get_type(node.type)# if node.type != "SELF_TYPE" else SelfType()
        except SemanticError as err:
            self.errors.append(err.text)
            node_type = ErrorType()

        if scope.is_local(node.id):
            self.AddError(f"Declaring Variable \"{node.id}\":",LOCAL_ALREADY_DEFINED.replace('%s', node.id, 1))
        else: scope.define_variable(node.id, node_type) 

        if node.expr:
            self.visit(node.expr, scope)
            expr_type = node.expr.computed_type
            if not expr_type.conforms_to(node_type):
                self.AddError(f"Declaring Variable \"{node.id}\":", INCOMPATIBLE_TYPES.replace('%s', expr_type.name, 1).replace('%s', node_type.name, 1))
                node_type = ErrorType()
        
        node.computed_type = node_type    
        
    @visitor.when(AssignNode)
    def visit(self, node, scope):
        var = scope.find_variable(node.id)
        if var:
            var_type = var.type
            
            self.visit(node.expr, scope)
            expr_type = node.expr.computed_type
            
            if var.name == 'self':
                self.AddError("Cant Assign", SELF_IS_READONLY)
            elif not expr_type.conforms_to(var_type):
                self.AddError("Cant Assign:", INCOMPATIBLE_TYPES.replace('%s', var_type.name, 1).replace('%s', expr_type.name, 1))
        else:
            self.AddError("Cant Assign:",VARIABLE_NOT_DEFINED.replace('%s', node.id, 1))
            var_type = ErrorType()
        node.computed_type = var_type
    
    @visitor.when(CallNode)
    def visit(self, node, scope):
        if node.obj == None:
            obj_type = self.current_type
        elif isinstance(node.obj, tuple):
            self.visit(node.obj[0], scope)
            type0 = self.update_type(node.obj[0].computed_type)
            try:
                obj_type = self.context.get_type(node.obj[1])
                if not type0.conforms_to(obj_type):
                    self.AddError(f"Class \"{type0.name}\" does not inherit from \"{obj_type.name}\".")
                    obj_type = ErrorType()
            except SemanticError as err:
                self.errors.add(err)
                obj_type = ErrorType()
        else:
            self.visit(node.obj, scope)
            obj_type = node.obj.computed_type
        
        try:
            method = obj_type.get_method(node.id)
            ret_type = self.update_type(method.return_type)
            if len(node.args) == len(method.param_types):
                for arg, param_type in zip(node.args, method.param_types):
                    self.visit(arg, scope)
                    arg_type = arg.computed_type
                    if not arg_type.conforms_to(param_type):
                        self.AddError(f"Method \"{method.name}\" in type \"{obj_type.name}\". Argument incompatibility: " + INCOMPATIBLE_TYPES.replace('%s', arg_type.name, 1).replace('%s', param_type.name, 1))
            else:
                self.AddError(f"Method \"{method.name}\" takes \"{len(method.param_types)}\" arguments, instead {len(node.args)} were given.")
        
        except SemanticError as err:
            self.AddError(err.text)
            ret_type = ErrorType()
            
        node.computed_type = ret_type
    
    @visitor.when(OperationNode)
    def visit(self, node, scope):
        self.visit(node.left, scope)
        left_type = node.left.computed_type
        
        self.visit(node.right, scope)
        right_type = node.right.computed_type

        int_type = self.context.get_type("Int")
        
        if not (left_type.conforms_to(int_type) and right_type.conforms_to(int_type)):
            self.AddError("Performing Arithmetic Operation:",INVALID_OPERATION.replace('%s', left_type.name, 1).replace('%s', right_type.name, 1))
            node_type = ErrorType()
        else:
            node_type = int_type
        node.computed_type = node_type
    
    @visitor.when(ComparisonNode)
    def visit(self, node, scope):
        self.visit(node.left, scope)
        left_type = node.left.computed_type
        
        self.visit(node.right, scope)
        right_type = node.right.computed_type

        if not (left_type.conforms_to(right_type) or right_type.conforms_to(left_type)):
            self.AddError("Performing Comparison: ", INVALID_OPERATION.replace('%s', left_type.name, 1).replace('%s', right_type.name, 1))
            node_type = ErrorType()
        else:
            node_type = self.context.get_type("Bool")
        node.computed_type = node_type

    
    @visitor.when(ConstantNumNode)
    def visit(self, node, scope):
        node.computed_type = self.context.get_type("Int")
    
    @visitor.when(ConstantStringNode)
    def visit(self, node, scope):
        node.computed_type = self.context.get_type("String")
    
    @visitor.when(ConstantBoolNode)
    def visit(self, node, scope):
        node.computed_type = self.context.get_type("Bool")
    
    @visitor.when(NotNode)
    def visit(self, node, scope):
        self.visit(node.lex, scope)
        bool_type = self.context.get_type("Bool")
        if not node.lex.computed_type.conforms_to(bool_type):
            self.AddError("Computing Not Expression:", INCOMPATIBLE_TYPES.replace('%s', node.lex.computed_type.name, 1).replace('%s',bool_type.name, 1))
            node.computed_type = ErrorType()
        node.computed_type = bool_type
    
    @visitor.when(IsVoidDeclarationNode)
    def visit(self, node, scope):
        self.visit(node.lex, scope)
        bool_type = self.context.get_type("Bool")
        node.computed_type = bool_type
    
    @visitor.when(HyphenNode)
    def visit(self, node, scope):
        self.visit(node.lex, scope)
        node_type = node.lex.computed_type
        int_type = self.context.get_type("Int")
        if not node_type.conforms_to(int_type):
            self.AddError("Computing Hyphen Expression:",INCOMPATIBLE_TYPES.replace('%s', node.lex.computed_type.name, 1).replace('%s',int_type.name, 1))
            node_type = ErrorType()
        node.computed_type = node_type

    @visitor.when(VariableNode)
    def visit(self, node, scope):
        var = scope.find_variable(node.lex)
        if var:
            var_type = var.type if not isinstance(var.type, SelfType) else self.current_type 
        else:
            self.AddError(VARIABLE_NOT_DEFINED.replace('%s', node.lex, 1))
            var_type = ErrorType()
        
        node.computed_type = var_type

    @visitor.when(InstantiateNode)
    def visit(self, node, scope):
        try:
            node_type = self.context.get_type(node.lex) if node.lex != "SELF_TYPE" else SelfType()
        except SemanticError as err:
            self.AddError(f"Unable to instantiate:",err.text)
            node_type = ErrorType()
        node.computed_type = node_type
    
    def update_type(self, typex:Type):
        if isinstance(typex, SelfType):
            return self.current_type

        return typex

    def AddError(self, extra = "", prefixed = ""):
        current_type = f"In class \"{self.current_type.name}\", "
        current_loc = f"in method \"{self.current_method.name}\". " if self.current_method else ""  
        current_loc = f"in attribute \"{self.current_attrb.name}\". " if self.current_attrb else current_loc
        self.errors.append(current_type + current_loc + extra + " " + prefixed)