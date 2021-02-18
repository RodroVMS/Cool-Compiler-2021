from cmp.pycompiler import Grammar, Item
from cmp.utils import ContainerSet
from cmp.tools.shift_reduce_parser import ShiftReduceParser

from cmp.tools.Old.grammar import compute_firsts, compute_local_firsts
from cmp.tools.Old.automata03 import State, multiline_formatter


def expand(item, firsts):
    next_symbol = item.NextSymbol
 
    if next_symbol is None or next_symbol.IsTerminal:
        return []
    
    lookaheads = ContainerSet()
    result = []
    for preview in item.Preview():
        lookaheads.update(compute_local_firsts(firsts, preview))
    
    assert not lookaheads.contains_epsilon, "lookaheads contains epsilon"
    result = []
    for i, production in enumerate(next_symbol.productions):
        result.append(Item(production, 0, lookaheads))
    return result

def compress(items):
    centers = {}

    for item in items:
        center = item.Center()
        try:
            lookaheads = centers[center]
        except KeyError:
            centers[center] = lookaheads = set()
        lookaheads.update(item.lookaheads)
    return { Item(x.production, x.pos, set(lookahead)) for x, lookahead in centers.items() }

def closure_lr1(items, firsts):
    closure = ContainerSet(*items)
    
    changed = True
    while changed:
        changed = False
        
        new_items = ContainerSet()
        for item in closure:
            new_items.extend(expand(item, firsts))
        
        changed = closure.update(new_items)
        
    return compress(closure)

def goto_lr1(items, symbol, firsts=None, just_kernel=False):
    assert just_kernel or firsts is not None, '`firsts` must be provided if `just_kernel=False`'
    #items = frozenset(item.NextItem for item in items if item.NextSymbol == symbol)
    xlist = []
    for item in items:
        if item.NextSymbol == symbol:
            nextItem = item.NextItem()
            xlist.append(nextItem)
    return frozenset(xlist) if just_kernel else closure_lr1(items, firsts)

def build_LR1_automaton(G):
    assert len(G.startSymbol.productions) == 1, 'Grammar must be augmented'
    
    firsts = compute_firsts(G)
    firsts[G.EOF] = ContainerSet(G.EOF)
    
    start_production = G.startSymbol.productions[0]
    start_item = Item(start_production, 0, lookaheads=(G.EOF,))
    start = frozenset([start_item])
    
    closure = closure_lr1(start, firsts)
    automaton = State(frozenset(closure), True)
    
    pending = [ start ]
    visited = { start: automaton }
    
    while pending:
        current = pending.pop()
        current_state = visited[current]
        
        closure = closure_lr1(current, firsts)
        for symbol in G.terminals + G.nonTerminals:
            # Your code here!!! (Get/Build `next_state`)
            goto = goto_lr1(closure, symbol, just_kernel = True)
            
            if not goto:
                continue
            try:
                next_state = visited[goto]
            except KeyError:
                closure2 = closure_lr1(goto, firsts)
                next_state = visited[goto] = State(frozenset(closure2),  True)
                pending.append(goto)
            
            current_state.add_transition(symbol.Name, next_state)
    
    automaton.set_formatter(multiline_formatter)
    return automaton

class LR1Parser(ShiftReduceParser):
    def _build_parsing_table(self):
        G = self.G.AugmentedGrammar(True)
        self.conflictType = dict()
        self.automaton = build_LR1_automaton(G)
        
        automaton = self.automaton
        for i, node in enumerate(automaton):
            if self.verbose: print(i, '\t', '\n\t '.join(str(x) for x in node.state), '\n')
            node.idx = i

        for node in automaton:
            idx = node.idx
            for item in node.state:
                if item.IsReduceItem:
                    production = item.production
                    if production.Left == G.startSymbol and G.EOF in item.lookaheads:
                        k = (idx, G.EOF)
                        self._register(self.action, k, (self.OK, None), self.conflictType)
                    else:
                        for look in item.lookaheads:
                            k = (idx, look)
                            self._register(self.action, k, (self.REDUCE, production), self.conflictType)
                else:
                    next_symbol = item.NextSymbol
                    next_sym_idx = node[next_symbol.Name][0].idx
                    k = (idx, next_symbol)
                    
                    if next_symbol.IsTerminal:
                        self._register(self.action, k, (self.SHIFT, next_sym_idx), self.conflictType)
                    else:
                        self._register(self.goto, k, next_sym_idx, self.conflictType)
