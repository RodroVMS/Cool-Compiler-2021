from utils import conforms, is_subset, join, join_list, smart_add
import cmp.visitor as visitor
from cmp.semantic import AutoType, Context, ErrorType, Scope, SelfType, SemanticError, Type
from AST import AssignNode, AttrDeclarationNode, BlockNode, CallNode, CaseDeclarationNode, CaseVarNode, ClassDeclarationNode, ComparisonNode, ConstantBoolNode, ConstantNumNode, ConstantStringNode, FuncDeclarationNode, HyphenNode, IfDeclarationNode, InstantiateNode, IsVoidDeclarationNode, LetDeclarationNode, NotNode, OperationNode, ProgramNode, VarDeclarationNode, VariableNode, WhileDeclarationNode

class TypeInferencer:
    def __init__(self, context:Context):
        self.context = context
        self.errors = []
        self.current_type = None
        self.current_method = None
        self.current_attrb = None
        self.types_updated = False

    @visitor.on('node')
    def visit(self, node):
        pass

    @visitor.when(ProgramNode)
    def visit(self, node:ProgramNode, scope:Scope):
        self.types_updated = False
        for declaration in node.declarations:
            self.visit(declaration, scope.next_child())
        scope.reset()
        return self.types_updated
    
    @visitor.when(ClassDeclarationNode)
    def visit(self, node:ClassDeclarationNode, scope):
        self.current_type = self.context.get_type(node.id)
        
        for feature in node.features:
            self.visit(feature, scope)
    
    @visitor.when(AttrDeclarationNode)
    def visit(self, node, scope):
        self.current_attrb = self.current_type.get_attribute(node.id)
        node_type = self.current_attrb.type
        
        if not node.expr:
            self.current_attrb = None
            return
        
        type_infered = node.inferenced_type
        expr_infered = node.expr.inferenced_type

        self.visit(node.expr, scope)
        node_expr = self.update_type(node.expr.inferenced_type)
        node_expr = conforms(node_expr, node_type)
        node.inferenced_type = self.compare_types(type_infered, node_type)
        node.expr.inferenced_type = self.compare_types(expr_infered, node_expr)
        
        var = scope.find_variable(node.id)
        var.type = node.inferenced_type
        self.current_attrb = None

    @visitor.when(FuncDeclarationNode)
    def visit(self, node, scopex:Scope()):
        scope:Scope = scopex.next_child()
        self.current_method = self.current_type.get_method(node.id)
        for idx, typex in zip(self.current_method.param_names, self.current_method.param_types):
            var = scope.find_variable(idx)
            var.type = self.compare_types(var.type, typex)

        decl_inferred = node.inferenced_type
        expr_inferred = node.body.inferenced_type
        ret_type_decl = self.update_type(self.current_method.return_type)
        self.visit(node.body, scope)
        ret_type_expr = self.update_type(node.body.inferenced_type)
        conforms(ret_type_expr, ret_type_decl)

        print("Comapring inferenced type in FuncDecl")
        node.inferenced_type = self.compare_types(decl_inferred, ret_type_decl)
        print("Comapring Body inferenced type in FuncDecl")
        node.body.inferenced_type = self.compare_types(expr_inferred, ret_type_expr)

        if isinstance(self.current_method.return_type, AutoType):
            auto_return = self.current_method.return_type
            ret_type_decl = conforms(ret_type_decl, ret_type_expr)
            print("Comapring inferenced type in FuncDecl Once Agagin")
            node.inferenced_type = self.compare_types(decl_inferred, ret_type_decl)
            if is_subset(ret_type_decl, auto_return):
                self.current_method.return_type = ret_type_decl
        self.current_method = None

    @visitor.when(BlockNode)
    def visit(self, node, scope):
        for expr in node.body:
            self.visit(expr, scope)
        node.inferenced_type = node.body[-1].inferenced_type

    @visitor.when(IfDeclarationNode)
    def visit(self, node, scope):
        if_inferred = node.ifexpr.inferenced_type
        self.visit(node.ifexpr, scope)
        ifexpr_type = self.update_type(node.ifexpr.inferenced_type)
        bool_type = self.context.get_type("Bool")
        if isinstance(ifexpr_type, AutoType):
            ifexpr_type.set_upper_limmit([bool_type])
        node.ifexpr.inferenced_type = self.compare_types(if_inferred, ifexpr_type)

        self.visit(node.thenexpr, scope)
        then_type = self.update_type(node.thenexpr.inferenced_type)

        self.visit(node.elseexpr, scope)
        else_type = self.update_type(node.elseexpr.inferenced_type)

        node_inferred = node.inferenced_type

        joined = join(then_type, else_type)
        if not isinstance(joined, ErrorType):
            type_sets, heads = joined
            auto = AutoType("IF", heads, type_sets)
        else:
            auto = ErrorType()
        
        if is_subset(auto, node_inferred):
            node.inferenced_type = self.compare_types(node_inferred, auto)
    
    @visitor.when(CaseDeclarationNode)
    def visit(self, node, scope:Scope):
        self.visit(node.expr, scope)

        var_types = []
        for var in node.casevars:
            child = scope.next_child()
            self.visit(var, child)
            var_types.append(var.inferenced_type)

        node_inferred = node.inferenced_type
        auto = join_list(var_types)
        if is_subset(auto, node_inferred):
            node.inferenced_type = self.compare_types(node_inferred, auto)
    
    @visitor.when(WhileDeclarationNode)
    def visit(self, node, scope):
        while_inferred = node.whileexpr.inferenced_type
        body_inferred = node.bodyexpr.inferenced_type

        self.visit(node.whileexpr, scope)
        wh_expr = self.update_type(node.whileexpr.inferenced_type)
        if isinstance(wh_expr, AutoType):
            wh_expr.set_upper_limmit([self.context.get_type("Bool")])
        node.whileexpr.inferenced_type = self.compare_types(while_inferred, wh_expr)
        
        self.visit(node.bodyexpr, scope)
        body = self.update_type(node.bodyexpr.inferenced_type)
        node.bodyexpr.inferenced_type = self.compare_types(body_inferred, body)
    
    @visitor.when(LetDeclarationNode)
    def visit(self, node, scope):
        child = scope.next_child()
        for var in node.letvars:
            self.visit(var, child)
        node_inferred = node.inferenced_type
        self.visit(node.expr, child)
        node_type= self.update_type(node.expr.inferenced_type)
        node.inferenced_type = self.compare_types(node_inferred, node_type)
    
    @visitor.when(CaseVarNode)
    def visit(self, node, scope:Scope):
        node_infer = node.inferenced_type
        self.visit(node.expr, scope)
        expr_type = self.update_type(node.expr.inferenced_type)
        node.inferenced_type = self.compare_types(node_infer, expr_type)

    @visitor.when(VarDeclarationNode)
    def visit(self, node, scope:Scope):
        if node.define:
            node_type = scope.find_variable(node.id).type
        else:
            node_type = ErrorType()

        if node.expr:
            expr_inferr = node.expr.inferenced_type
            self.visit(node.expr, scope)
            expr_type = self.update_type(node.expr.inferenced_type)
            expr_type = conforms(expr_type, node_type)
            node.expr.inferenced_type = self.compare_types(expr_inferr, expr_type)
        
        node.inferenced_type = self.compare_types(node.inferenced_type, node_type)
    
    @visitor.when(AssignNode)
    def visit(self, node, scope:Scope):
        if not node.define:
            var = None
            var_type = ErrorType()
        else:
            var = scope.find_variable(node.id)
            var_type = var.type

        expr_inferred = node.expr.inferenced_type
        self.visit(node.expr, scope)
        node_expr = self.update_type(node.expr.inferenced_type)

        if node.define:
            node_expr = conforms(node_expr, var_type)
            node.expr.inferenced_type = self.compare_types(expr_inferred, node_expr)
            if isinstance(var_type, AutoType):
                var_type = conforms(var_type, node_expr)
                var.type = self.compare_types(var.type, var_type)

        node.inferenced_type = self.compare_types(node.inferenced_type, var_type)

    @visitor.when(CallNode)
    def visit(self, node, scope):
        if isinstance(node.inferenced_type, ErrorType):
            return

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
        
        method = None
        try:
            method = obj_type.get_method(node.id)
        except SemanticError:
            if isinstance(obj_type, AutoType):
                result = self.context.get_method_by_name(node.id, len(node.args))
                valid = []
                for meth, typex in result:
                    if typex in obj_type.type_set:
                        valid.append((meth, typex))

                if len(valid) > 1:
                    error = f"Method \"{node.id}\" found in {len(valid)} unrelated types:\n"
                    error += "   -Found in: "
                    error += ", ".join(typex.name for _, typex in valid)
                    self.AddError(error)
                    obj_type = ErrorType()
                elif len(valid) == 0:
                    self.AddError(f"There is no method called {node.id} which takes {len(node.args)} paramters.")
                    obj_type == ErrorType()
                else:
                    method, types = valid[0]
                    obj_type.set_upper_limmit([types])
        node.inferenced_obj_type = self.compare_types(node.inferenced_obj_type, obj_type)
        if method:
            type_set = set()
            heads = []
            ret_type = self.update_type(method.return_type)
            heads, type_set = smart_add(type_set, heads, ret_type)
            if len(node.args) == len(method.param_types):
                for  i in range(len(node.args)):
                    arg, param_type = node.args[i], method.param_types[i]
                    arg_infer = arg.inferenced_type
                    self.visit(arg, scope)
                    arg_type = self.update_type(arg.inferenced_type)
                    arg_type = conforms(arg_type, param_type)
                    if isinstance(param_type, AutoType):
                        param_type = conforms(param_type, arg_type)
                        method.param_types[i] = self.compare_types(method.param_types[i], param_type)
                    arg.inferenced_type = self.compare_types(arg_infer, arg_type)
            
            inferred = node.inferenced_type
            if isinstance(ret_type, AutoType) and is_subset(inferred, ret_type):
                method.return_type.set_upper_limmit(heads)
                node.inferenced_type = self.compare_types(inferred, method.return_type)
            elif is_subset(ret_type, inferred):
                node.inferenced_type = self.compare_types(inferred, ret_type)
        else:
            node.inferenced_type = ErrorType()

    @visitor.when(OperationNode)
    def visit(self, node, scope):
        left_infer = node.left.inferenced_type
        self.visit(node.left, scope)
        left_type = self.update_type(node.left.inferenced_type)
        

        right_infer = node.right.inferenced_type
        self.visit(node.right, scope)
        right_type = self.update_type(node.right.inferenced_type)
        
        int_type = self.context.get_type("Int")
        if isinstance(left_type, AutoType):
            left_type.set_upper_limmit([int_type])
        node.left.inferenced_type = self.compare_types(left_infer, left_type)
        
        if isinstance(right_type, AutoType):
            right_type.set_upper_limmit([int_type])
        node.right.inferenced_type = self.compare_types(right_infer, right_type)

    @visitor.when(ComparisonNode)
    def visit(self, node, scope):
        left_infer = node.left.inferenced_type
        self.visit(node.left, scope)
        left_type = self.update_type(node.left.inferenced_type)

        right_infer = node.right.inferenced_type
        self.visit(node.right, scope)
        right_type = self.update_type(node.right.inferenced_type)

        left_type = conforms(left_type, right_type)
        node.left.inferenced_type = self.compare_types(left_infer, left_type)
        right_type = conforms(right_type, left_type)
        node.right.inferenced_type = self.compare_types(right_infer, right_type)
        
        node.inferenced_type = self.context.get_type("Bool")# if len(right_type.type_set) > 0 and len(left_type.type_set) > 0 else ErrorType()
        
    @visitor.when(NotNode)
    def visit(self, node, scope):
        lex_infer = node.lex.inferenced_type
        self.visit(node.lex, scope)
        lex_type = self.update_type(node.lex.inferenced_type)
        bool_type = self.context.get_type("Bool")
        if isinstance(lex_type, AutoType):
            lex_type.set_upper_limmit([bool_type])
        node.lex.inferenced_type = self.compare_types(lex_infer, lex_type)
        node.inferenced_type = bool_type
    
    @visitor.when(HyphenNode)
    def visit(self, node, scope):
        lex_infer = node.lex.inferenced_type
        self.visit(node.lex, scope)
        lex_type = self.update_type(node.lex.inferenced_type)
        int_type = self.context.get_type("Int")
        if isinstance(lex_type, AutoType):
            lex_type.set_upper_limmit([int_type])
        node.lex.inferenced_type = self.compare_types(lex_infer, lex_type)
        node.inferenced_type = int_type
    
    @visitor.when(IsVoidDeclarationNode)
    def visit(self, node, scope):
        lex_infer = node.lex.inferenced_type
        self.visit(node.lex, scope)
        lex_type = self.update_type(node.lex.inferenced_type)
        node.lex.inferenced_type = self.compare_types(lex_infer, lex_type)
    
    @visitor.when(VariableNode)
    def visit(self, node, scope):
        
        if node.define:
            var = scope.find_variable(node.lex)
            var.type = self.update_type(var.type)
            var_type =var.type
        else:
            var_type = ErrorType()
        node.inferenced_type = self.compare_types(node.inferenced_type, var_type)

    @visitor.when(InstantiateNode)
    def visit(self, node, scope):
        pass
    
    @visitor.when(ConstantNumNode)
    def visit(self, node, scope):
        pass
    
    @visitor.when(ConstantStringNode)
    def visit(self, node, scope):
        pass
    
    @visitor.when(ConstantBoolNode)
    def visit(self, node, scope):
        pass

    def update_type(self, typex:Type):
        if isinstance(typex, SelfType):
            typex = self.current_type
        return typex

    def compare_types(self, old_type, new_type):
        if isinstance(old_type, ErrorType) or isinstance(new_type, ErrorType):
            return ErrorType()
        
        if isinstance(old_type, AutoType) and isinstance(new_type, AutoType):
            if len(old_type.type_set) == len(new_type.type_set) and len(old_type.type_set.intersection(new_type.type_set)) == len(new_type.type_set):
                return new_type
            print(f"Chaged ocurred while comparing {old_type.name} and {new_type.name}")
            print("old_type set:", ", ".join(typex.name for typex in old_type.type_set))
            print("new_type set:", ", ".join(typex.name for typex in new_type.type_set))
            print("old_type cond:", [[typex.name for typex in type_set] for type_set in old_type.conditions_list])
            print("new_type cond:", [[typex.name for typex in type_set] for type_set in new_type.conditions_list])
            self.types_updated = True
            if len(new_type.type_set) > 0:
                return new_type
            return ErrorType()
        
        if isinstance(old_type, AutoType) and not isinstance(new_type, AutoType):
            print(f"Chaged ocurred while comparing {old_type.name} and {new_type.name}")
            if new_type in old_type.type_set:
                if len(old_type.type_set) > 1:
                    self.types_updated = True
                return new_type
                
            self.types_updated = True
            return ErrorType()
        
        if old_type.name != new_type.name:
            return ErrorType()
        return new_type

    def AddError(self,  extra:str, prefixed = ""):
        current_type = f"In class \"{self.current_type.name}\", "
        current_loc = f"in method \"{self.current_method.name}\". " if self.current_method else ""  
        current_loc = f"in attribute \"{self.current_attrb.name}\". " if self.current_attrb else current_loc
        self.errors.append(current_type + current_loc + extra + " " + prefixed)