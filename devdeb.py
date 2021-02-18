from type_logger import TypeLogger
from utils import global_upper_graph, set_global_upper
from cmp.evaluation import evaluate_reverse_parse
from cmp.tools.LR1_Parser import LR1Parser
from format_visitor import FormatVisitor
from grammar import G, lexer, pprint_tokens
from type_checker import TypeChecker
from type_collector_builder import TypeBuilder, TypeCollector
from inference_gatherer import InferenceGatherer
from type_inferencer import TypeInferencer
from type_linker import TypeLinker
from type_finisher import TypeFinisher

def format_errors(errors, s = ""):
    count = 1
    for error in errors:
        s += str(count) + ". " + error + "\n"
        count += 1
    return s

def run_pipeline(G, program):
    print("Executing Program")
    #print(program)
    tokens = lexer(program)
    print("Tokens")
    pprint_tokens(tokens)
    
    parser = LR1Parser(G)
    parse, operations, result = parser(tokens)
    if not result:
        print(parse)
        return

    ast = evaluate_reverse_parse(parse, operations, tokens)
    formatter = FormatVisitor()
    tree = formatter.visit(ast)
    print(tree)
    
    collector = TypeCollector()
    collector.visit(ast)
    context = collector.context
    print("Context\n", context)
    
    builder = TypeBuilder(context)
    builder.visit(ast)
    print("Context\n", context)

    gatherer = InferenceGatherer(context)
    scope = gatherer.visit(ast)
    print("Begining of Inferencer -----------------------------------")
    change = True
    inferencer = TypeInferencer(context)
    while change:
        change = inferencer.visit(ast, scope)
        if inferencer.errors:
            break
        print(f"change: {change} ---------------------------------------")
        #input()
    
    #ok_till_now = set_global_upper(gatherer.inference_graph)
    #print("set_global_upper:", ok_till_now)
    #if ok_till_now:
    #    print("Nodes in graph and uppers:\n", [[graph.name, graph.upper_global.name] for graph in gatherer.inference_graph])
    #    globals_graph = global_upper_graph(gatherer.inference_graph)
    #else:
    #    globals_graph = dict()
    #checker = TypeChecker(context)
    #scope = checker.visit(ast)

    linker = TypeLinker(context, gatherer.inference_graph)
    for _ in range(2):
        linker.visit(ast, scope)
        if linker.errors:
            break
    
    finisher = TypeFinisher(context)
    finisher.visit(ast, scope)

    logger = TypeLogger(context)
    types = logger.visit(ast, scope)
    print(types)

    s = "Type Collector Errors:\n"
    s = format_errors(collector.errors, s)
    s += "Type Builder Errors:\n"
    s = format_errors(builder.errors, s)
    s += "Inference Gatherer Errors:\n"
    s = format_errors(gatherer.errors, s)
    s += "Type Inferencer Errors:\n"
    s = format_errors(inferencer.errors, s)
    s += "Type Linker Errors:\n"
    s = format_errors(linker.errors, s)
    s += "Total Errors: " + str(len(collector.errors) + len(builder.errors) + len(gatherer.errors) + len(inferencer.errors) + len(linker.errors))
    print(s)
    

#filename = r"./tests_scripts/attribute2.cl"
#filename = r"./cool_scripts_auto/08b_auto_point.cl"
#filename = r"./cool_scripts_auto/09_auto_ack.cl"
filename = r"./cool_scripts_auto/11_auto_jp.cl"
#filename = r"./cool_scripts/life.cl"
print("Loading " + filename)
file1 = open(filename, "r")
program = file1.read()
file1.close()


run_pipeline(G, program)

# todo: Verificar errores en el set conditions de los autotypes
# todo: Verificar cuando se trabaja con inferencia en los call node.
# todo: Que expresen los errores el gatherere, inferencer y linker
# todo: ubicar set_dict y set_intersection en lugares correctos
# todo: Annadir IsVoidDeclaration a todos los visitors
# todo: Modificar la gramatica para mayor expresividad