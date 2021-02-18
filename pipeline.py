from cmp.evaluation import evaluate_reverse_parse
from cmp.tools.LR1_Parser import LR1Parser
from format_visitor import FormatVisitor
from grammar import lexer
from inference_gatherer import InferenceGatherer
from type_collector_builder import TypeBuilder, TypeCollector
from type_inferencer import TypeInferencer
from type_linker import TypeLinker


class Pipeline():
    def __init__(self, G) -> None:
        self.parser = LR1Parser(G)
        self.tree = None

    def __call__(self, program):
        tokens = lexer(program)
        parse, operations, result = self.parser(tokens)
        if not result:
            return parse
        
        ast = evaluate_reverse_parse(parse, operations, tokens)
        formatter = FormatVisitor()
        self.tree = formatter.visit(ast)

        collector = TypeCollector()
        collector.visit(ast)
        context = collector.context

        builder = TypeBuilder(context)
        builder.visit(ast)

        gatherer = InferenceGatherer(context)
        scope = gatherer.visit(ast)

        change = True
        inferencer = TypeInferencer(context)
        while change:
            change = inferencer.visit(ast, scope)

        linker = TypeLinker(context)
        linker.visit(ast, scope)

        s = "Type Collector Errors:\n"
        s = self.format_errors(collector.errors, s)
        s += "Type Builder Errors:\n"
        s = self.format_errors(builder.errors, s)
        s += "Type Linker Errors:\n"
        s = self.format_errors(linker.errors, s)
        s += "Total Errors: " + str(len(collector.errors) + len(builder.errors) + len(linker.errors))
        
        for auto, typex in linker.inferenced:
            s += "Inferenced " + typex.name + " from " + auto + "\n"
        return s
    
    def format_errors(self, errors, s = ""):
        count = 1
        for error in errors:
            s += str(count) + ". " + error + "\n"
            count += 1
        return s
