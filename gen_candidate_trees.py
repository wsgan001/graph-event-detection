import os
import ujson as json
import gensim
import scipy
import cPickle as pickle
import networkx as nx
from datetime import timedelta

from dag_util import unbinarize_dag, binarize_dag
from lst import lst_dag
from enron_graph import EnronUtil
from meta_graph_stat import MetaGraphStat
from experiment_util import sample_nodes

CURDIR = os.path.dirname(os.path.abspath(__file__))

TIMESPAN = timedelta(weeks=4).total_seconds()  # three month

DEBUG = True

CALCULATE_GRAPH = False

input_path = os.path.join(CURDIR, 'data/enron.json')

with open(input_path) as f:
    interactions = [json.loads(l) for l in f]
    
print('loading lda...')
lda_model = gensim.models.ldamodel.LdaModel.load(
    os.path.join(CURDIR, 'models/model-4-50.lda')
)
dictionary = gensim.corpora.dictionary.Dictionary.load(
    os.path.join(CURDIR, 'models/dictionary.pkl')
)

if CALCULATE_GRAPH:
    print('calculating meta_graph...')
    g = EnronUtil.get_topic_meta_graph(interactions,
                                       lda_model, dictionary,
                                       dist_func=scipy.stats.entropy,
                                       preprune_secs=TIMESPAN,
                                       debug=True)

    print('pickling...')
    nx.write_gpickle(EnronUtil.compactize_meta_graph(g, map_nodes=False),
                     'data/enron.pkl')

if not CALCULATE_GRAPH:
    print('loading pickle...')
    g = nx.read_gpickle('data/enron.pkl')


def get_summary(g):
    return MetaGraphStat(
        g, kws={
            'temporal_traffic': {'time_resolution': 'month'},
            'edge_costs': {'max_values': [1.0, 0.1]},
            'topics': False,
            'email_content': False
        }
    ).summary()

print(get_summary(g))

# roots = [u'233107.206',  # (30, datetime.datetime(2001, 2, 3, 12, 19))
#          u'253127.1180']

roots = sample_nodes(g, 500)

U = 0.5
results = []

for ni, r in enumerate(roots):
    if DEBUG:
        print('Nodes procssed {}'.format(ni))
        print('getting rooted subgraph within timespan')
    
    sub_g = EnronUtil.get_rooted_subgraph_within_timespan(
        g, r, TIMESPAN, debug=False
    )

    if len(sub_g.edges()) == 0:
        print("empty rooted sub graph")
        continue

    if DEBUG:
        print("sub_g summary: \n{}".format(
            get_summary(sub_g)
        ))

    if DEBUG:
        print('binarizing dag...')

    binary_sub_g = binarize_dag(sub_g,
                                EnronUtil.VERTEX_REWARD_KEY,
                                EnronUtil.EDGE_COST_KEY,
                                dummy_node_name_prefix="d_")

    if DEBUG:
        print('lst ing')

    tree = lst_dag(binary_sub_g, r, U,
                   edge_weight_decimal_point=2,
                   debug=False)

    tree = unbinarize_dag(tree, edge_weight_key=EnronUtil.EDGE_COST_KEY)
    if len(tree.edges()) == 0:
        print("empty tree")
        continue

    print('tree summary:\n{}'.format(get_summary(tree)))
    results.append(tree)

pickle.dump(results,
            open('tmp/results.pkl', 'w'),
            protocol=pickle.HIGHEST_PROTOCOL)


# def sample_nodes_by_partial_importance(g, nodes_sample_size=100,
#                                        sample_pool_size=1000):
#     nodes_pool = sorted(g.nodes(),
#                         key=lambda n: g.out_degree(n),
#                         reverse=True)[:sample_pool_size]
#     return nodes_pool[np.random.permutation(len(nodes_pool))[:nodes_sample_size]]        
