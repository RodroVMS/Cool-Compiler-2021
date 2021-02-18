import os

import streamlit as st

from cmp.evaluation import evaluate_reverse_parse
from cmp.tools.LR1_Parser import LR1Parser
from format_visitor import FormatVisitor
from grammar import G, lexer, pprint_tokens
from inference_gatherer import InferenceGatherer
from type_collector_builder import TypeBuilder, TypeCollector
from type_finisher import TypeFinisher
from type_inferencer import TypeInferencer
from type_linker import TypeLinker
from type_logger import TypeLogger


def file_selector(folder_path="."):
    filenames = os.listdir(folder_path)
    filenames.sort()
    selected_filename = st.selectbox("Select a file", filenames)
    return os.path.join(folder_path, selected_filename), selected_filename

def format_errors(errors, s = ""):
    count = 1
    for error in errors:
        s += str(count) + ". " + error + "\n"
        count += 1
    return s

st.title("Cool Compiler")

sb = st.selectbox("Choose where the file is going to be loaded or written:", ["Import File", "Raw Input"],)
import_file = True if sb == "Import File" else False

st.sidebar.title("Options")
showProgram = st.sidebar.checkbox("Show Program", False)
showTokens = st.sidebar.checkbox("Show Tokenization", False)
showParsing = st.sidebar.checkbox("Show Parsing")
showAST = st.sidebar.checkbox("Show AST")
showTypesCollected = st.sidebar.checkbox("Show Types Collected")
showTypesBuilded = st.sidebar.checkbox("Show Types Builded")
showTypesComputed = st.sidebar.checkbox("Show Types Computed", True)
showProgramResult = st.sidebar.checkbox("Show Result", True)

local_name = ""

# todo: Testear lo que dijo el profesor.
# todo: Ver los assign en las clases fuera de Inference Gatherer
# todo: Actualizar el Readme

if import_file:
    st.write("Introduce File's FOLDER Location")
    ti = st.text_input(r"Introduce Folder's Adress (Default: ./cool_scripts_auto)")
    ti = "./cool_scripts_auto" if ti == "" else ti
    
    filename, local_name = file_selector(ti)
    st.text("You selected: " + filename)

    file1 = open(filename, "r")
    program = file1.read()
    file1.close()
else:
    program = st.text_area("Write Program:")

###---------------RUN PIPELINE-----------------###
if st.button("Submit"):
    st.write("Executing Program", local_name)
    
    def run_pipeline(program):
        if showProgram:
            st.text(program)
    
        tokens = lexer(program)
        if showTokens:
            st.write("Tokenizing")
            st.text(pprint_tokens(tokens))

        parser = LR1Parser(G)
        parse, operations, success = parser(tokens)
        if not success:
            st.text(parse)
            return
        if showParsing:
            st.write("Parsing")
            st.text("\n".join(repr(x) for x in parse))
        
        ast = evaluate_reverse_parse(parse, operations, tokens)
        formatter = FormatVisitor()
        tree = formatter.visit(ast)
        if showAST:
            st.write("Building AST")
            st.text(tree)
        s = ""
        collector = TypeCollector()
        collector.visit(ast)
        context = collector.context
        if not collector.errors:
            st.success("Collecting Types")
        else: 
            st.error("Collecting Types")
            s = "Type Collector Errors:\n"
            s = format_errors(collector.errors, s)
        if showTypesCollected:
            st.write("Context:")
            st.text(context)

        builder = TypeBuilder(context)
        builder.visit(ast)
        if not builder.errors:
            st.success("Building Types")
        else:
            st.error("Building Types")
            s += "Type Builder Errors:\n"
            s = format_errors(builder.errors, s)
        if showTypesBuilded:
            st.write("Context")
            st.text(context)

        gatherer = InferenceGatherer(context)
        scope = gatherer.visit(ast)

        inferencer = TypeInferencer(context)
        change = True
        count = 1
        while change:
            change = inferencer.visit(ast, scope)
            st.write(f"Running Type Inferencer({count})")
            count += 1
            if inferencer.errors:
                break
        
        if not inferencer.errors and not gatherer.errors:
            st.success("Inferencing Types")
        else:
            st.error("Inferencing Types")
            if gatherer.errors:
                s += "Inference Gatherer Errors:\n"
                s = format_errors(gatherer.errors, s)
            if inferencer.errors:
                s += "Type Inferencer Errors:\n"
                s = format_errors(inferencer.errors, s)
        
        linker = TypeLinker(context, gatherer.inference_graph)
        for _ in range(2):
            linker.visit(ast, scope)
            if linker.errors:
                break
        
        if not linker.errors:
            st.success("Linking Types")
        else:
            st.error("Linking Types")
            s += "Type Linker Errors:\n"
            s = format_errors(linker.errors, s)
        
        finisher = TypeFinisher(context)
        finisher.visit(ast, scope)

        if showTypesComputed:
            st.write("Computed Nodes Types")
            logger = TypeLogger(context)
            types = logger.visit(ast, scope)
            st.text(types)
        
        if showProgramResult:
            st.write("Result")
            s += "Total Errors: " + str(len(collector.errors) + len(builder.errors) + len(gatherer.errors) + len(inferencer.errors) + len(linker.errors))
            st.text(s)
    
    run_pipeline(program)
