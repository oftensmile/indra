from __future__ import absolute_import, print_function, unicode_literals
from builtins import dict, str
from copy import deepcopy
import json
import logging
import itertools
import collections
import numpy as np
from matplotlib.colors import LinearSegmentedColormap as colormap
from matplotlib.colors import rgb2hex, hex2color
from indra.statements import *
from indra.databases import hgnc_client
from indra.databases import context_client, get_identifiers_url
from indra.preassembler import Preassembler
from indra.tools.expand_families import Expander
from indra.preassembler.hierarchy_manager import hierarchies

expander = Expander(hierarchies)

# Python 2
try:
    basestring
# Python 3
except:
    basestring = str

logger = logging.getLogger('cyjs_assembler')


class CyJSAssembler(object):
    def __init__(self, stmts=None):
        if not stmts:
            self.statements = []
        else:
            self.statements = stmts
        self._edges = []
        self._nodes = []
        self._existing_nodes = {}
        self._id_counter = 0
        self._exp_colorscale = []
        self._mut_colorscale = []
        self._gene_names = []
        self._context = {}

    def add_statements(self, stmts):
        """Add INDRA Statements to the assembler's list of statements.

        Parameters
        ----------
        stmts : list[indra.statements.Statement]
            A list of :py:class:`indra.statements.Statement`
            to be added to the statement list of the assembler.
        """
        stmts = Preassembler.combine_duplicate_stmts(stmts)
        for stmt in stmts:
            self.statements.append(stmt)

    def make_model(self, *args, **kwargs):
        """Assemble a Cytoscape JS network from INDRA Statements.

        This method assembles a Cytoscape JS network from the set of INDRA
        Statements added to the assembler.

        Parameters
        ----------
        grouping : bool
            If True, the nodes with identical incoming and outgoing edges
            are grouped and the corresponding edges are merged.

        drop_virtual_edges : bool
            If True, the original edges which have been collected and made
            virtual are discarded. If these edges are discarded, they are
            not seen by the cytoscape.js layout algorithms.

        add_edge_weights : bool
            If True, give edges that connect group nodes a weight of their
            group size. All other edges get a weight of 1.

        Returns
        -------
        cyjs_str : str
            The json serialized Cytoscape JS model.
        """
        for stmt in self.statements:
            if isinstance(stmt, RegulateActivity):
                self._add_regulate_activity(stmt)
            elif isinstance(stmt, Inhibition):
                self._add_activation(stmt)
            elif isinstance(stmt, Complex):
                self._add_complex(stmt)
            elif isinstance(stmt, Modification):
                self._add_modification(stmt)
            else:
                logger.warning('Unhandled statement type: %s' %
                               stmt.__class__.__name__)
        if kwargs.get('grouping'):
            self._group_nodes()
            self._group_edges()
        if kwargs.get('drop_virtual_edges'):
            self._drop_virtual_edges()
        if kwargs.get('add_edge_weights'):
            self._add_edge_weights()
        return self.print_cyjs_graph()


    def get_gene_names(self):
        """Get gene names of all nodes and node members

        Parameters
        ----------
        """
        # Collect all gene names in network
        gene_names = []
        for node in self._nodes:
            members = node['data'].get('members')
            if members:
                gene_names += list(members.keys())
            else:
                if node['data']['name'].startswith('Group'):
                    continue
                gene_names.append(node['data']['name'])
        self._gene_names = gene_names

    def set_CCLE_context(self, cell_types):
        """Get context of all nodes and node members

        Parameters
        ----------
        """
        self.get_gene_names()
        gene_names = self._gene_names
        exp = {}
        mut = {}
        # context_client gives back a dict with genes as keys. prefer lines keys
        def transpose_context(context_dict):
            d = context_dict
            d_genes = [x for x in d]
            d_lines = [x for x in d[d_genes[0]]]
            transposed = {x:{y:d[y][x] for y in d_genes} for x in d_lines}
            return transposed
        # access the context service in chunks of cell types.
        # it will timeout if queried with larger chunks.
        while len(cell_types) > 0:
            cell_types_chunk = cell_types[:10]
            del cell_types[:10]
            exp_temp = context_client.get_protein_expression(gene_names, \
                                                             cell_types_chunk)
            exp_temp = transpose_context(exp_temp)
            for e in exp_temp:
                exp[e] = exp_temp[e]
            mut_temp = context_client.get_mutations(gene_names, \
                                                    cell_types_chunk)
            mut_temp = transpose_context(mut_temp)
            for m in mut_temp:
                mut[m] = mut_temp[m]
        # create bins for the exp values
        # because colorbrewer only does 3-9 bins and I don't feel like
        # reinventing color scheme theory, this will only bin 3-9 bins
        def bin_exp(expression_dict):
            d = expression_dict
            exp_values = []
            for line in d:
                for gene in d[line]:
                    val = d[line][gene]
                    if (val) != None:
                        exp_values.append(val)
            thr_dict = {}
            for n_bins in range(3,10):
                bin_thr = np.histogram(np.log10(exp_values), n_bins)[1][1:]
                thr_dict[n_bins] = bin_thr
            # this dict isn't yet binned, that happens in the loop
            binned_dict = {x:deepcopy(expression_dict) for x in (range(3,10))}
            for n_bins in binned_dict:
                for line in binned_dict[n_bins]:
                    for gene in binned_dict[n_bins][line]:
                        # last bin is reserved for None
                        if binned_dict[n_bins][line][gene] is None:
                            binned_dict[n_bins][line][gene] = n_bins
                        else:
                            val = np.log10(binned_dict[n_bins][line][gene])
                            for thr_idx, thr in enumerate(thr_dict[n_bins]):
                                if val <= thr:
                                    binned_dict[n_bins][line][gene] = thr_idx
                                    break
                        #import pdb; pdb.set_trace();
            return binned_dict
        binned_exp = bin_exp(exp)
        context = {'bin_expression' : binned_exp,
                   'mutation' : mut}
        self._context['CCLE'] = context

    def print_cyjs_graph(self):
        """Return the assembled Cytoscape JS network as a json string.

            Returns
            -------
            cyjs_str : str
            A json string representation of the Cytoscape JS network.
        """
        cyjs_dict = {'edges': self._edges, 'nodes': self._nodes}
        cyjs_str = json.dumps(cyjs_dict, indent=1, sort_keys=True)
        return cyjs_str

    def print_cyjs_context(self):
        """Return a list of node names and their respective context.

            Returns
            -------
            cyjs_str_context : str
            A json string of the context dictionary. e.g. -
            {'CCLE' : {'exp' : {'gene' : 'val'},
                       'mut' : {'gene' : 'val'}
                      }
            }
        """
        context = self._context
        context_str = json.dumps(context, indent=1, sort_keys=True)
        return context_str

    def save_json(self, fname='model'):
        """Save the assembled Cytoscape JS network in a json file.

        Parameters
        ----------
        file_name : Optional[str]
            The name of the file to save the Cytoscape JS network to.
            Default: model
        """
        cyjs_dict = {'edges': self._edges, 'nodes': self._nodes}
        model_dict = {'exp_colorscale': self._exp_colorscale,
                      'mut_colorscale': self._mut_colorscale,
                      'model_elements': cyjs_dict,
                      'context' : self._context}
        cyjs_str = self.print_cyjs_graph()
        # outputs the graph
        with open(fname + '.json', 'wt') as fh:
            fh.write(cyjs_str)
        # outputs the context of graph nodes
        context_str = self.print_cyjs_context()
        with open(fname + '_context' + '.json', 'wt') as fh:
            fh.write(context_str)

    def save_model(self, fname='model.js'):
        """Save the assembled Cytoscape JS network in a js file.

        Parameters
        ----------
        file_name : Optional[str]
            The name of the file to save the Cytoscape JS network to.
            Default: model.js
        """
        exp_colorscale_str = json.dumps(self._exp_colorscale)
        mut_colorscale_str = json.dumps(self._mut_colorscale)
        cyjs_dict = {'edges': self._edges, 'nodes': self._nodes}
        model_str = json.dumps(cyjs_dict, indent=1, sort_keys=True)
        model_dict = {'exp_colorscale_str': exp_colorscale_str,
                      'mut_colorscale_str': mut_colorscale_str,
                      'model_elements_str': model_str}
        s = ''
        s += 'var exp_colorscale = %s;\n' % model_dict['exp_colorscale_str']
        s += 'var mut_colorscale = %s;\n' % model_dict['mut_colorscale_str']
        s += 'var model_elements = %s;\n' % model_dict['model_elements_str']
        with open(fname, 'wt') as fh:
            fh.write(s)

    def _add_regulate_activity(self, stmt):
        edge_type, edge_polarity = _get_stmt_type(stmt)
        edge_id = self._get_new_id()
        source_id = self._add_node(stmt.subj, uuid=stmt.uuid)
        target_id = self._add_node(stmt.obj, uuid=stmt.uuid)
        edge = {'data': {'i': edge_type, 'id': edge_id,
                         'source': source_id, 'target': target_id,
                         'polarity': edge_polarity}}
        self._edges.append(edge)

    def _add_modification(self, stmt):
        edge_type, edge_polarity = _get_stmt_type(stmt)
        edge_id = self._get_new_id()
        source_id = self._add_node(stmt.enz, uuid=stmt.uuid)
        target_id = self._add_node(stmt.sub, uuid=stmt.uuid)
        edge = {'data': {'i': edge_type, 'id': edge_id,
                         'source': source_id, 'target': target_id,
                         'polarity': edge_polarity}}
        self._edges.append(edge)

    def _add_complex(self, stmt):
        edge_type, edge_polarity = _get_stmt_type(stmt)
        for m1, m2 in itertools.combinations(stmt.members, 2):
            m1_id = self._add_node(m1, uuid=stmt.uuid)
            m2_id = self._add_node(m2, uuid=stmt.uuid)

            edge_id = self._get_new_id()
            edge = {'data': {'i': edge_type, 'id': edge_id,
                             'source': m1_id, 'target': m2_id,
                             'polarity': edge_polarity}}
            self._edges.append(edge)

    def _add_node(self, agent, uuid=None):
        node_key = agent.name
        node_id = self._existing_nodes.get(node_key)
        # if the node already exists we do not want to add it again
        # we must however add its uuid
        if node_id is not None:
            #fetch the appropriate node
            n = [x for x in self._nodes if x['data']['id'] == node_id][0]
            uuid_list = n['data']['uuid_list']
            if uuid not in uuid_list:
                uuid_list.append(uuid)
            return node_id
        db_refs = _get_db_refs(agent)
        node_id = self._get_new_id()
        self._existing_nodes[node_key] = node_id
        node_name = agent.name
        node_name = node_name.replace('_', ' ')
        expanded_families = expander.get_children(agent, ns_filter='HGNC')
        members = {}
        for member in expanded_families:
            hgnc_symbol = member[1]
            hgnc_id = hgnc_client.get_hgnc_id(hgnc_symbol)
            if hgnc_id:
                up_id = hgnc_client.get_uniprot_id(hgnc_id)
                member_agent = Agent(hgnc_symbol,
                                     db_refs={'HGNC': hgnc_id,
                                              'UP': up_id})
                member_db_refs = _get_db_refs(member_agent)
            else:
                member_db_refs = {}
            members[member[1]] = {
                    'db_refs': member_db_refs
                    }
        node = {'data': {'id': node_id, 'name': node_name,
                         'db_refs': db_refs, 'parent': '',
                         'members': members, 'uuid_list': [uuid]}}
        self._nodes.append(node)
        return node_id



    def _get_new_id(self):
        ret = self._id_counter
        self._id_counter += 1
        return ret

    def _get_node_key(self, node_dict):
        s = tuple(sorted(node_dict['sources']))
        t = tuple(sorted(node_dict['targets']))
        return (s, t)

    def _get_node_groups(self):
        # First we construct a dictionary for each node's
        # source and target edges
        node_dict = {node['data']['id']: {'sources': [], 'targets': []}
                     for node in self._nodes}
        for edge in self._edges:
            # Add edge as a source for its target node
            edge_data = (edge['data']['i'], edge['data']['polarity'],
                         edge['data']['source'])
            node_dict[edge['data']['target']]['sources'].append(edge_data)
            # Add edge as target for its source node
            edge_data = (edge['data']['i'], edge['data']['polarity'],
                         edge['data']['target'])
            node_dict[edge['data']['source']]['targets'].append(edge_data)

        # Make a dictionary of nodes based on source/target as a key
        node_key_dict = collections.defaultdict(lambda: [])
        for node_id, node_d in node_dict.items():
            key = self._get_node_key(node_d)
            node_key_dict[key].append(node_id)
        # Constrain the groups to ones that have more than 1 member
        node_groups = [g for g in node_key_dict.values() if (len(g) > 1)]
        return node_groups

    def _group_edges(self):
        # Iterate over edges in a copied edge list
        edges_to_add = []
        for e in self._edges:
            # Check if edge source or target are contained in a parent
            # If source or target in parent edit edge
            # Nodes may only point within their container
            source = e['data']['source']
            target = e['data']['target']
            source_node = [x for x in self._nodes if
                           x['data']['id'] == source][0]
            target_node = [x for x in self._nodes if
                           x['data']['id'] == target][0]
            # If the source node is in a group, we change the source of this
            # edge to the group
            new_edge = None
            if source_node['data']['parent'] != '':
                new_edge = deepcopy(e)
                new_edge['data'].pop('id', None)
                new_edge['data']['source'] = source_node['data']['parent']
                e['data']['i'] = 'Virtual'
            # If the targete node is in a group, we change the target of this
            # edge to the group
            if target_node['data']['parent'] != '':
                if new_edge is None:
                    new_edge = deepcopy(e)
                    new_edge['data'].pop('id', None)
                new_edge['data']['target'] = target_node['data']['parent']
                e['data']['i'] = 'Virtual'
            if new_edge is not None:
                if new_edge not in edges_to_add:
                    edges_to_add.append(new_edge)

        # need to check if there are identical edges in edges to add
        # identical on everything but id
        for edge in edges_to_add:
            new_id = self._get_new_id()
            edge['data']['id'] = new_id
            self._edges.append(edge)

    def _group_nodes(self):
        node_groups = self._get_node_groups()
        for group in node_groups:
            # Make new group node
            new_group_node = {'data': {'id': (self._get_new_id()),
                                       'name': ('Group' + str(group)),
                                       'parent': ''}}
            # Point the node to its parent
            for node in self._nodes:
                if node['data']['id'] in group:
                    node['data']['parent'] = new_group_node['data']['id']
            self._nodes.append(new_group_node)

    def _drop_virtual_edges(self):
        self._edges = [x for x in self._edges if x['data']['i'] != 'Virtual']

    def _add_edge_weights(self):
        # make a list of group nodes
        group_node_ids = []
        for n in self._nodes:
            if n['data']['parent'] != '':
                group_node_ids.append(n['data']['parent'])
        group_node_ids = list(set(group_node_ids))
        # get sizes for each group
        group_node_sizes = {}
        for g in group_node_ids:
            group_members = [x for x in self._nodes
                             if x['data']['parent'] == g]
            group_size = len(group_members)
            group_node_sizes[g] = group_size
        # iterate over edges
        # if they point to/from group, weigh them acc to group size
        # nodes between two groups get assigned heaviest of two weights
        for e in self._edges:
            source = e['data']['source']
            target = e['data']['target']
            if (source in group_node_ids) and (target in group_node_ids):
                e['data']['weight'] = max(group_node_sizes[source],
                                          group_node_sizes[target])
            elif source in group_node_ids:
                e['data']['weight'] = group_node_sizes[source]
            elif target in group_node_ids:
                e['data']['weight'] = group_node_sizes[target]
        # once all group node edges have weights
        # give non-group node edges weights of 1
        for e in self._edges:
            if e['data'].get('weight') is None:
                e['data']['weight'] = 1

def _get_db_refs(agent):
    cyjs_db_refs = {}
    for db_name, db_ids in agent.db_refs.items():
        if db_name == 'TEXT':
            continue
        if isinstance(db_ids, int):
            db_id = str(db_ids)
        elif isinstance(db_ids, basestring):
            db_id = db_ids
        else:
            db_id = db_ids[0]
        url = get_identifiers_url(db_name, db_id)
        if not url:
            continue
        db_name_map = {
            'UP': 'UniProt', 'PUBCHEM': 'PubChem',
            'IP': 'InterPro', 'NXPFA': 'NextProtFamily',
            'PF': 'Pfam', 'CHEBI': 'ChEBI'}
        name = db_name_map.get(db_name)
        if not name:
            name = db_name
        cyjs_db_refs[name] = url
    return cyjs_db_refs


def _get_stmt_type(stmt):
    if isinstance(stmt, AddModification):
        edge_type = 'Modification'
        edge_polarity = 'positive'
    elif isinstance(stmt, RemoveModification):
        edge_type = 'Modification'
        edge_polarity = 'negative'
    elif isinstance(stmt, SelfModification):
        edge_type = 'SelfModification'
        edge_polarity = 'positive'
    elif isinstance(stmt, Complex):
        edge_type = 'Complex'
        edge_polarity = 'none'
    elif isinstance(stmt, Activation):
        edge_type = 'Activation'
        edge_polarity = 'positive'
    elif isinstance(stmt, Inhibition):
        edge_type = 'Inhibition'
        edge_polarity = 'negative'
    elif isinstance(stmt, RasGef):
        edge_type = 'RasGef'
        edge_polarity = 'positive'
    elif isinstance(stmt, RasGap):
        edge_type = 'RasGap'
        edge_polarity = 'negative'
    else:
        edge_type = stmt.__class__.__str__()
        edge_polarity = 'none'
    return edge_type, edge_polarity
