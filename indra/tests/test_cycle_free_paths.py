import networkx as nx
from indra.explanation import paths_graph as pg
from indra.explanation import cycle_free_paths as cfp

g1_uns = nx.DiGraph()
g1_uns.add_edges_from((('A', 'B'), ('B', 'C'), ('C', 'D')))

g2_uns = nx.DiGraph()
g2_uns.add_edges_from((('A', 'B'), ('B', 'A'), ('B', 'D'), ('A', 'D')))

g3_uns = nx.DiGraph()
g3_uns.add_edges_from((('A', 'B'), ('B', 'A'), ('B', 'C'),
                      ('C', 'D'), ('A', 'D')))

def draw(g, filename):
    ag = nx.nx_agraph.to_agraph(g)
    ag.draw(filename, prog='dot')


def test_prune():
    g = nx.DiGraph()
    g.add_edges_from((('S', 'A'), ('S', 'B'), ('A', 'S'), ('B', 'C'),
                      ('C', 'D'), ('D', 'T'), ('B', 'T')))
    length = 4
    (f_level, b_level) = pg.get_reachable_sets(g, 'S', 'T', max_depth=length)
    pg_raw = pg.paths_graph(g, 'S', 'T', length, f_level, b_level)
    pg_raw_edges = pg_raw.edges()
    nodes_to_prune = [(2, 'S')]
    # Prune the graph
    pg_pruned = cfp.prune(pg_raw, nodes_to_prune, (0, 'S'), (length, 'T'))
    # Make sure we didn't change the original graphs or node lists
    assert nodes_to_prune == [(2, 'S')]
    assert pg_raw.edges() == pg_raw_edges
    # The correctly pruned structure
    assert set(pg_pruned.edges()) == \
           set([((0, 'S'), (1, 'B')), ((1, 'B'), (2, 'C')),
                ((2, 'C'), (3, 'D')), ((3, 'D'), (4, 'T'))])


def test_pg_0():
    source = 'A'
    target = 'D'
    length = 3
    # We first run the pg_0 calculation on a simple graph with no cycles
    # involving the source or target
    (f_level, b_level) = pg.get_reachable_sets(g1_uns, source, target,
                                               max_depth=length)
    pg_raw = pg.paths_graph(g1_uns, source, target, length, f_level, b_level)
    (pg_0, tags) = cfp.PG_0(pg_raw, (0, source), (length, target))
    # Because no nodes are pruned, the initialized "cycle free" paths graph
    # will be the same as the path graph we started with
    assert pg_0 == pg_raw
    assert tags == {(0, 'A'): [], (1, 'B'): ['A'], (2, 'C'): ['A'],
                    (3, 'D'): ['A']}

    # The next graph contains a cycle passing through the source node, A,
    # and no acyclic paths
    (f_level, b_level) = pg.get_reachable_sets(g2_uns, source, target,
                                               max_depth=length)
    pg_raw = pg.paths_graph(g2_uns, source, target, length, f_level, b_level)
    (pg_0, tags) = cfp.PG_0(pg_raw, (0, source), (length, target))
    assert not pg_0
    assert not tags

    # The next graph contains a cycle passing through the source node, A,
    # with one acyclic path
    (f_level, b_level) = pg.get_reachable_sets(g3_uns, source, target,
                                               max_depth=length)
    pg_raw = pg.paths_graph(g3_uns, source, target, length, f_level, b_level)
    (pg_0, tags) = cfp.PG_0(pg_raw, (0, source), (length, target))
    assert set(pg_0.edges()) == set([((0, 'A'), (1, 'B')), ((1, 'B'), (2, 'C')),
                                     ((2, 'C'), (3, 'D'))])
    assert tags == {(0, 'A'): [], (1, 'B'): ['A'], (2, 'C'): ['A'],
                    (3, 'D'): ['A']}

    # This test stems from a randomly-generated network where no paths
    # were found--guarantees that the problem is NOT that pg_0 is empty
    g4_uns = nx.DiGraph()
    g4_uns.add_edges_from(((0, 1), (1, 0), (0, 2), (2, 0), (1, 2), (2, 1)))
    source, target, length = (0, 2, 2)
    (f_level, b_level) = pg.get_reachable_sets(g4_uns, source, target,
                                               max_depth=length)
    pg_raw = pg.paths_graph(g4_uns, source, target, length, f_level, b_level)
    (pg_0, tags) = cfp.PG_0(pg_raw, (0, source), (length, target))
    assert pg_0
    assert tags


def test_pg():
    # TODO: Flesh this out more with some examples defining typical return
    # values
    g4_uns = nx.DiGraph()
    g4_uns.add_edges_from(((0, 1), (1, 0), (0, 2), (2, 0), (1, 2), (2, 1)))
    source, target, length = (0, 2, 2)
    (f_level, b_level) = pg.get_reachable_sets(g4_uns, source, target,
                                               max_depth=length)
    pg_raw = pg.paths_graph(g4_uns, source, target, length, f_level, b_level)
    (pg_0, tags) = cfp.PG_0(pg_raw, (0, source), (length, target))
    dic_PG = cfp.PG((pg_0, tags), (0, source), (length, target), length)
    assert len(dic_PG) == length
    assert dic_PG[0][0]
    assert dic_PG[0][1]


def test_sampling():
    """Test sampling of problematic graph.

    The issue with this graph is that the operation on (1, 3) would prune out
    (3, 3) the one causing the cycle, except that it is retained because there
    is still a non-cyclic path through (3, 3) via (1, 1). However, in
    subsequent steps, pruning of downstream nodes (i.e., (2, 4)) actually
    eliminate any acyclic paths through (1, 3). As a result, there is a
    circumstance, when sampling the resulting graph, that one can end up
    sampling into (1, 3) but there are no permissible successors from (1, 3)
    based on the tags.

    The solution was to repeat the sampling process iteratively until
    convergence.
    """
    g = nx.DiGraph()
    g.add_edges_from([(0, 1), (0, 3), (0, 4), (0, 5), (1, 4), (2, 4), (2, 5),
                      (3, 0), (3, 2), (3, 4), (3, 5), (4, 2), (4, 3), (4, 5)])
    source, target, length = (0, 5, 5)
    (f_level, b_level) = pg.get_reachable_sets(g, source, target,
                                               max_depth=length)
    pg_raw = pg.paths_graph(g, source, target, length, f_level, b_level)
    src = (0, source)
    tgt = (length, target)
    pg_0 = cfp.PG_0(pg_raw, src, tgt)
    dic_PG = cfp.PG(pg_0, src, tgt, length)
    G_cf, T = dic_PG[length - 1]
    P = cfp.cf_sample_many_paths(src, tgt, G_cf, T, 1000)


if __name__ == '__main__':
    test_sampling()
