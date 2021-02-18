from utils import compare_types, conforms, is_subset, join, join_list, set_common_ancestor, smart_add
import cmp.visitor as visitor
from cmp.semantic import AutoType, Context, ErrorType, Scope, SelfType, SemanticError, Type
from AST import AssignNode, AttrDeclarationNode, BlockNode, CallNode, CaseDeclarationNode, CaseVarNode, ClassDeclarationNode, ComparisonNode, ConstantBoolNode, ConstantNumNode, ConstantStringNode, FuncDeclarationNode, HyphenNode, IfDeclarationNode, InstantiateNode, IsVoidDeclarationNode, LetDeclarationNode, NotNode, OperationNode, ProgramNode, VarDeclarationNode, VariableNode, WhileDeclarationNode

WRONG_SIGNATURE = 'Method "%s" already defined in "%s" with a different signature.'
SELF_IS_READONLY = 'Variable "self" is read-only.'
LOCAL_ALREADY_DEFINED = 'Variable "%s" is already defined.'
INCOMPATIBLE_TYPES = 'Cannot convert "%s" into "%s".'
VARIABLE_NOT_DEFINED = 'Variable "%s" is not defined.'
INVALID_OPERATION = 'Operation is not defined between "%s" and "%s".'

class InferenceGatherer:
    def __init__(self, context:Context):
        self.context = context
        self.current_type = None
        self.current_method = None
        self.current_attrb = None
        self.inference_graph = dict()
        self.errors = []

    @visitor.on('node')
    def visit(self, node, scope):
        pass

    @visitor.when(ProgramNode)
    def visit(self, node:ProgramNode) -> Scope:
        scope = Scope()
        for declaration in node.declarations:
            self.visit(declaration, scope.create_child())
        
        return scope
    
    @visitor.when(ClassDeclarationNode)
    def visit(self, node:ClassDeclarationNode, scope):
        self.current_type = self.context.get_type(node.id)
        scope.define_variable("self", self.current_type)
        for attr in self.current_type.attributes:
            scope.define_variable(attr.name, attr.type)
        
        for feature in node.features:
            self.visit(feature, scope)
    
    @visitor.when(AttrDeclarationNode)
    def visit(self, node, scope):
        self.current_attrb = self.current_type.get_attribute(node.id)
        node_type = self.update_type(self.current_attrb.type)

        if not node.expr:
            self.current_attrb = None
            node.inferenced_type = node_type
            return
        
        self.visit(node.expr, scope)
        node_expr = self.update_type(node.expr.inferenced_type)
        node_expr = conforms(node_expr, node_type)
        node.expr.inferenced_type = node_expr

        node.inferenced_type = node_type# if len(node_expr.type_set) else ErrorType()
        
        var = scope.find_variable(node.id)
        var.type = node.inferenced_type
        self.current_attrb = None
    
    @visitor.when(FuncDeclarationNode)
    def visit(self, node, scopex):
        scope = scopex.create_child()
        self.current_method = self.current_type.get_method(node.id)
        for idx, typex in zip(self.current_method.param_names, self.current_method.param_types):
            scope.define_variable(idx, typex)
        
        self.visit(node.body, scope)
        ret_type_decl = self.update_type(self.current_method.return_type)
        ret_type_expr = self.update_type(node.body.inferenced_type)
        ret_type_expr = conforms(ret_type_expr, ret_type_decl)
        node.body.inferenced_type = ret_type_expr

        if isinstance(self.current_method.return_type, AutoType):
            auto_return = self.current_method.return_type
            ret_type_decl = conforms(ret_type_decl, ret_type_expr)
            if is_subset(ret_type_decl, auto_return):
                self.update_graph(ret_type_decl, ret_type_expr)
                self.current_method.return_type = ret_type_decl

        node.inferenced_type = ret_type_decl
        self.current_method = None
    
    @visitor.when(BlockNode)
    def visit(self, node, scope):
        for expr in node.body:
            self.visit(expr, scope)
        node.inferenced_type = node.body[-1].inferenced_type

    @visitor.when(IfDeclarationNode)
    def visit(self, node, scope):
        self.visit(node.ifexpr, scope)
        ifexpr_type = node.ifexpr.inferenced_type
        bool_type = self.context.get_type("Bool")
        if isinstance(ifexpr_type, AutoType):
            ifexpr_type.set_upper_limmit([bool_type])

        self.visit(node.thenexpr, scope)
        then_type = self.update_type(node.thenexpr.inferenced_type)
        self.visit(node.elseexpr, scope)
        else_type = self.update_type(node.elseexpr.inferenced_type)

        joined = join(then_type, else_type)
        if not isinstance(joined, ErrorType):
            type_sets, heads = joined
            node.inferenced_type = AutoType("IF", heads, type_sets)
        else:
            node.inferenced_type = ErrorType()

    @visitor.when(CaseDeclarationNode)
    def visit(self, node, scope:Scope):
        self.visit(node.expr, scope)
        self.update_type(node.expr.inferenced_type)

        type_list = []
        for var in node.casevars:
            child = scope.create_child()
            self.visit(var, child)
            type_list.append(var.inferenced_type)
        
        node_type = join_list(type_list)
        node.inferenced_type = node_type
    
    @visitor.when(WhileDeclarationNode)
    def visit(self, node, scope):
        self.visit(node.whileexpr, scope)
        pred_type = self.update_type(node.whileexpr.inferenced_type)
        bool_type = self.context.get_type("Bool")
        if isinstance(pred_type, AutoType):
            pred_type.set_upper_limmit([bool_type])

        self.visit(node.bodyexpr, scope)
        self.update_type(node.bodyexpr.inferenced_type)
        node.inferenced_type = self.context.get_type("Object")
    
    @visitor.when(LetDeclarationNode)
    def visit(self, node, scope):
        child = scope.create_child()
        for var in node.letvars:
            self.visit(var, child)
        self.visit(node.expr, child)
        node.inferenced_type = self.update_type(node.expr.inferenced_type)

    @visitor.when(CaseVarNode)
    def visit(self, node, scope):
        try:
            node_type = self.context.get_type(node.type, selftype=False, autotype=False)# if node.type != "SELF_TYPE" else SelfType()
        except SemanticError as err:
            node_type = ErrorType()
        scope.define_variable(node.id, node_type)
        self.visit(node.expr, scope)
        node.inferenced_type = self.update_type(node.expr.inferenced_type)

    @visitor.when(VarDeclarationNode)
    def visit(self, node, scope):
        try:
            node_type = self.context.get_type(node.type)
        except SemanticError as err:
            node_type = ErrorType()
        
        if not scope.is_local(node.id):
            scope.define_variable(node.id, node_type)
            node.define = True
        else:
            node.define = False
            self.AddError(f"Declaring Variable \"{node.id}\":",LOCAL_ALREADY_DEFINED.replace('%s', node.id, 1))

        if node.expr:
            self.visit(node.expr, scope)
            expr_type = self.update_type(node.expr.inferenced_type)
            expr_type = conforms(expr_type, node_type)
            node.expr.inferenced_type = expr_type
        
        node.inferenced_type = node_type
    
    @visitor.when(AssignNode)
    def visit(self, node, scope:Scope):
        var = scope.find_variable(node.id)
        if not var:
            node.define = False
            var_type = ErrorType()
        else:
            node.define = True
            var_type = var.type

        self.visit(node.expr, scope)
        node_expr = self.update_type(node.expr.inferenced_type)

        if var and var.name != "self":
            node_expr = conforms(node_expr, var_type)
            node.expr.inferenced_type = node_expr
            if isinstance(var_type, AutoType):
                var_type = conforms(var_type, node_expr)
                var.type = var_type

        node.inferenced_type = var_type

    @visitor.when(CallNode)
    def visit(self, node, scope):
        if node.obj == None:
            obj_type = self.current_type
        elif isinstance(node.obj, tuple):
            self.visit(node.obj[0], scope)
            child_type = self.update_type(node.obj[0].inferenced_type)
            try:
                obj_type = self.context.get_type(node.obj[1], selftype=False, autotype=False)
                if isinstance(child_type, AutoType):
                    child_type.set_upper_limmit([obj_type])
            except SemanticError:
                obj_type = ErrorType()
        else:
            self.visit(node.obj, scope)
            obj_type = self.update_type(node.obj.inferenced_type)
        
        methods = None
        try:
            methods = [(obj_type, obj_type.get_method(node.id))]
        except SemanticError as err:
            if isinstance(obj_type, AutoType):
                result = self.context.get_method_by_name(node.id, len(node.args))
                types = [typex for _, typex in result]
                obj_type.set_upper_limmit(types)
                if len(obj_type.upper_limmit):
                    methods = [(t, t.get_method(node.id)) for t in obj_type.upper_limmit]
            else:
                self.AddError(err)
        
        node.inferenced_obj_type = obj_type
        if methods:
            type_set = set()
            heads = []
            for typex, method in methods:
                ret_type = method.return_type
                ret_type = typex if isinstance(ret_type, SelfType) else ret_type
                heads, type_set = smart_add(type_set, heads, ret_type)
                if len(node.args) == len(method.param_types):
                    for  i in range(len(node.args)):
                        arg, param_type = node.args[i], method.param_types[i]
                        self.visit(arg, scope)
                        arg_type = self.update_type(arg.inferenced_type)
                        arg_type = conforms(arg_type, param_type)
                        if isinstance(param_type, AutoType):
                            param_type = conforms(param_type, arg_type)
                            method.param_types[i] = param_type
                        self.update_graph(arg_type, param_type)
                        arg.inferenced_type = arg_type
            node.inferenced_type = AutoType(node.id, heads, type_set)
        else:
            node.inferenced_type = ErrorType()

    @visitor.when(OperationNode)
    def visit(self, node, scope):
        self.visit(node.left, scope)
        left_type = self.update_type(node.left.inferenced_type)

        self.visit(node.right, scope)
        right_type = self.update_type(node.right.inferenced_type)

        int_type = self.context.get_type("Int")
        if isinstance(left_type, AutoType):
            left_type.set_upper_limmit([int_type])
        
        if isinstance(right_type, AutoType):
            right_type.set_upper_limmit([int_type])
        
        node.inferenced_type = int_type

    @visitor.when(ComparisonNode)
    def visit(self, node, scope):
        self.visit(node.left, scope)
        left_type = self.update_type(node.left.inferenced_type)

        self.visit(node.right, scope)
        right_type = self.update_type(node.right.inferenced_type)

        left_type = conforms(left_type, right_type)
        node.left.inferenced_type = left_type
        right_type = conforms(right_type, left_type)
        node.right.inferenced_type = right_type
        node.inferenced_type = self.context.get_type("Bool")
        
    @visitor.when(NotNode)
    def visit(self, node, scope):
        self.visit(node.lex, scope)
        lex_type = self.update_type(node.lex.inferenced_type)
        bool_type = self.context.get_type("Bool")
        if isinstance(lex_type, AutoType):
            lex_type.set_upper_limmit([bool_type])

        node.inferenced_type = bool_type
    
    @visitor.when(HyphenNode)
    def visit(self, node, scope):
        self.visit(node.lex, scope)
        lex_type = self.update_type(node.lex.inferenced_type)
        int_type = self.context.get_type("Int")
        if isinstance(lex_type, AutoType):
            lex_type.set_upper_limmit([int_type])
        node.inferenced_type = int_type
    
    @visitor.when(VariableNode)
    def visit(self, node, scope):
        var = scope.find_variable(node.lex)
        if var:
            node.define = True
            var_type = self.update_type(var.type) 
        else:
            node.define = False
            var_type = ErrorType()
        node.inferenced_type = var_type

    @visitor.when(IsVoidDeclarationNode)
    def visit(self, node, scope):
        self.visit(node.lex, scope)
        lex_type = self.update_type(node.lex.inferenced_type)
        node.inferenced_type = self.context.get_type("Bool")

    @visitor.when(InstantiateNode)
    def visit(self, node, scope):
        try:
            node_type = self.context.get_type(node.lex, selftype=False, autotype=False)
        except SemanticError as err:
            node_type = ErrorType()
        node.inferenced_type = node_type
    
    @visitor.when(ConstantNumNode)
    def visit(self, node, scope):
        node.inferenced_type = self.context.get_type("Int")
    
    @visitor.when(ConstantStringNode)
    def visit(self, node, scope):
        node.inferenced_type = self.context.get_type("String")
    
    @visitor.when(ConstantBoolNode)
    def visit(self, node, scope):
        node.inferenced_type = self.context.get_type("Bool")

    def update_graph(self, decl_type, expr_type) -> Type:
        if isinstance(decl_type ,AutoType) and isinstance(expr_type ,AutoType):
            self.set_dependencies(decl_type, expr_type)
            self.set_dependencies(expr_type, decl_type)
    
    def set_dependencies(self, type1:Type, type2:Type):
        try:
            self.inference_graph[type1].add(type2)
        except KeyError:
            self.inference_graph[type1] = set([type2])


    def update_type(self, typex:Type):
        if isinstance(typex, SelfType):
            typex = self.current_type
        return typex

    def AddError(self, extra = "", prefixed = ""):
        current_type = f"In class \"{self.current_type.name}\", "
        current_loc = f"in method \"{self.current_method.name}\". " if self.current_method else ""  
        current_loc = f"in attribute \"{self.current_attrb.name}\". " if self.current_attrb else current_loc
        self.errors.append(current_type + current_loc + extra + " " + prefixed)