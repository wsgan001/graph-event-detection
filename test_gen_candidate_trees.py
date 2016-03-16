import random
import unittest
import numpy
import networkx as nx
import cPickle as pkl

from datetime import timedelta
from nose.tools import assert_true, assert_equal, assert_almost_equal
from subprocess import check_output

from gen_candidate_trees import run
from scipy.spatial.distance import cosine

from .lst import lst_dag, dp_dag_general, make_variance_cost_func
from .baselines import greedy_grow_by_discounted_reward as greedy_grow, \
    random_grow
from .test_util import remove_tmp_data, make_path
from .budget_problem import binary_search_using_charikar
from .dag_util import get_roots


directed_params = {
    'interaction_json_path': make_path('test/data/enron-head-100.json'),
    'lda_model_path': make_path('test/data/test.lda'),
    'corpus_dict_path': make_path('test/data/test_dictionary.gsm'),
    'meta_graph_pkl_path_prefix': make_path('test/data/enron-head-100'),
}

# undirected_params = {
#     'interaction_json_path': make_path(
#         'test/data/undirected/interactions.json'
#     ),
#     'lda_model_path': make_path(
#         'test/data/undirected/lda_model-50-50.lda'
#     ),
#     'corpus_dict_path': make_path(
#         'test/data/undirected/dict.pkl'
#     ),
#     'meta_graph_pkl_path_prefix': make_path(
#         'test/data/undirected/meta-graph'
#     ),
#     'undirected': True
# }


lst = lambda g, r, U: lst_dag(
    g, r, U,
    edge_weight_decimal_point=2,
    debug=False
)

variance_method = lambda g, r, U: dp_dag_general(
    g, r, int(U*10),  # fixed point 1
    make_variance_cost_func(cosine,
                            'topics',
                            fixed_point=1,
                            debug=False),
    debug=False
)

quota_based_method = lambda g, r, U: binary_search_using_charikar(
    g, r, U, level=2
)

distance_weights_1 = {'topics': 1.0}
distance_weights_2 = {'topics': 0.2, 'bow': 0.8}
distance_weights_3 = {'topics': 0.5, 'bow': 0.5, 'hashtag_bow': 0.1}


class GenCandidateTreeTest(unittest.TestCase):
    def setUp(self):
        random.seed(1)
        numpy.random.seed(1)

        self.some_kws_of_run = {
            'cand_tree_number': None,
            'cand_tree_percent': 0.1,
            'meta_graph_kws': {
                'dist_func': cosine,
                'preprune_secs': timedelta(days=28),
                'distance_weights': {'topics': 1.0},
                'consider_recency': False,
                'alpha': 0.2,
                'tau': 0.8
            },
            'gen_tree_kws': {
                'timespan': timedelta(days=28),
                'U': 0.01,
                'dijkstra': False
            },
            'root_sampling_method': 'random'
        }

    def check(self, test_name, tree_gen_func, **more_args):
        result_pickle_prefix = make_path("test/data/tmp",
                                         "result-{}".format(test_name))
        kws = self.some_kws_of_run.copy()
        
        kws.update(directed_params)
        
        if more_args:
            kws.update(more_args)

        result_path, mg_path = run(
            tree_gen_func,
            calculate_graph=False,
            print_summary=False,
            result_pkl_path_prefix=result_pickle_prefix,
            **kws)

        trees = pkl.load(open(result_path))
        trees = filter(None, trees)  # remove Nones

        assert_true(len(trees) > 0)

        for t in trees:
            assert_true(len(t.edges()) > 0)

        return trees, nx.read_gpickle(mg_path)

    def test_if_sender_and_recipient_information_saved(self):
        trees, _ = self.check('greedy', greedy_grow)
        for t in trees:
            for n in t.nodes():
                assert_true('sender_id' in t.node[n])
                assert_true('recipient_ids' in t.node[n])
        
    def test_greedy_grow(self):
        self.check('greedy', greedy_grow)

    def test_random_grow(self):
        self.check('random', random_grow)

    def test_lst_dag(self):
        self.some_kws_of_run['should_binarize_dag'] = True
        self.check('lst', lst)

    def test_quota(self):
        self.check('quota', quota_based_method)

    def test_lst_dag_after_dijkstra(self):
        self.some_kws_of_run['should_binarize_dag'] = True
        trees, _ = self.check('lst', lst)

        self.some_kws_of_run['gen_tree_kws']['dijkstra'] = True
        trees_with_dij, _ = self.check('lst', lst)

        for t, t_dij in zip(trees, trees_with_dij):
            assert_true(sorted(t.edges()) != sorted(t_dij))

    def test_variance_method(self):
        # self.check('variance', variance_method)
        pass

    def test_distance_weight_using_hashtag_bow(self):
        self.some_kws_of_run['meta_graph_kws']['distance_weights'] = distance_weights_3
        self.check('greedy', greedy_grow)

    def test_with_roots(self):
        self.some_kws_of_run['roots'] = [54647]
        trees, _ = self.check('greedy', greedy_grow)
        assert_equal(1, len(trees))
        assert_equal(54647, get_roots(trees[0])[0])
    
    def test_with_recency(self):
        self.some_kws_of_run['meta_graph_kws']['consider_recency'] = True
        self.some_kws_of_run['meta_graph_kws']['tau'] = 0.4
        self.some_kws_of_run['meta_graph_kws']['alpha'] = 0.6
        self.some_kws_of_run['meta_graph_kws']['timestamp_converter'] = lambda s: 2 * s
        self.some_kws_of_run['meta_graph_kws']['distance_weights'] = {'topics': 1.0}
        _, mg = self.check('greey', greedy_grow)
        
        s, t = mg.edges_iter().next()
        time_diff = mg.node[t]['timestamp'] - mg.node[s]['timestamp']
        assert_almost_equal(
            cosine(mg.node[s]['topics'],
                   mg.node[t]['topics'])
            - 0.6 * (0.4 ** (2 * time_diff)),
            mg[s][t]['c']
        )

    def test_random_sampler(self):
        self.some_kws_of_run['root_sampling_method'] = 'random'
        self.check('greedy', greedy_grow)

    def test_upperbound_sampler(self):
        self.some_kws_of_run['root_sampling_method'] = 'upperbound'
        self.check('greedy', greedy_grow)

    def test_adaptive_sampler(self):
        self.some_kws_of_run['root_sampling_method'] = 'adaptive'
        self.check('greedy', greedy_grow)

    def tearDown(self):
        # remove_tmp_data('test/data/tmp/*')
        pass


class GenCandidateTreeCMDTest(unittest.TestCase):
    """test for commandline
    """
    def setUp(self):
        random.seed(123456)
        numpy.random.seed(123456)

        self.script_path = make_path("gen_candidate_trees.py")
        self.result_dir = make_path("test/data/tmp/result-")

        self.directed_params = directed_params

    def check(self, method="random", distance="cosine",
              sampling_method="random", extra="", undirected=False,
              distance_weights=distance_weights_2):
        more_params = self.directed_params

        cmd = """python {} \
        --method={method} \
        --dist={distance_func} \
        --cand_n_percent=0.05 \
        --root_sampling={sampling_method}\
        --result_prefix={result_dir} \
        --weeks=4 --U=2.0 \
        --lda_path={lda_model_path} \
        --interaction_path={interaction_json_path} \
        --corpus_dict_path={corpus_dict_path} \
        --meta_graph_path_prefix={meta_graph_pkl_path_prefix} \
        --weight_for_topics {weight_for_topics} \
        --weight_for_bow {weight_for_bow} \
        --weight_for_hashtag_bow {weight_for_hashtag_bow} \
        {extra}""".format(
            self.script_path,
            method=method,
            distance_func=distance,
            sampling_method=sampling_method,
            result_dir=self.result_dir,
            extra=extra,
            weight_for_topics=distance_weights.get('topics', 0),
            weight_for_bow=distance_weights.get('bow', 0),
            weight_for_hashtag_bow=distance_weights.get('hashtag_bow', 0),
            **more_params
        ).split()
        output = check_output(cmd)
        print(output)

        assert_true("traceback" not in output.lower())

        return output

    def test_random(self):
        self.check(method='random')

    def test_variance(self):
        # self.check(method='variance')
        pass

    def test_quota(self):
        self.check(method='quota',
                   extra='--charikar_level 2')

    def test_adaptive_sampling(self):
        output = self.check(sampling_method='adaptive')
        assert_true('adaptive' in output)

    def test_given_topics(self):
        self.directed_params = {
            'interaction_json_path': make_path(
                'test/data/given_topics/'
                'interactions--n_noisy_interactions_fraction=0.1.json'
            ),
            'meta_graph_pkl_path_prefix': make_path(
                'test/data/given_topics/meta-graph'
            ),
            'lda_model_path': None,
            'corpus_dict_path': None,
            'undirected': False,
        }

        self.check(undirected=False,
                   distance='cosine',
                   extra='--seconds=8 --given_topics',
                   distance_weights={'topics': 1.0})

    def test_cand_n(self):
        self.check(extra='--cand_n 7')

    def test_hashtag_bow(self):
        self.check(distance_weights=distance_weights_3)

    def test_with_event_param_pkl_path(self):
        path = make_path('test/data/tmp/event_param.pkl')
        pkl.dump([{'U': 1.0,
                   'preprune_secs': timedelta(weeks=4),
                   'roots': [54647]}],
                 open(path, 'w'))
        self.check('greedy',
                   extra='--event_param_pickle_path {}'.format(path)
        )

    def test_with_recency(self):
        self.check('greedy',
                   extra='--recency')
        
    def tearDown(self):
        remove_tmp_data('test/data/tmp')
    

class GenCandidateTreeGivenTopicsTest(GenCandidateTreeTest):
    """sharing some test with GenCandidateTreeTest
    """
    def setUp(self):
        random.seed(1)
        numpy.random.seed(1)

        distance_weights = distance_weights_1  # 'topics' only for given topics
        self.some_kws_of_run = {
            'interaction_json_path': make_path(
                'test/data/given_topics/interactions--n_noisy_interactions_fraction=0.1.json'
            ),
            'cand_tree_percent': 0.1,
            'meta_graph_pkl_path_prefix': make_path('test/data/given_topics/meta-graph'),
            'meta_graph_kws': {
                'dist_func': cosine,
                'preprune_secs': 8,
                'distance_weights': distance_weights,
                'consider_recency': False,
                'tau': 0.0,
                'alpha': 0.8
            },
            'gen_tree_kws': {
                'timespan': 8,
                'U': 2.0,
                'dijkstra': False
            },
            'given_topics': True,
        }

    def check(self, test_name, tree_gen_func, **more_args):
        result_pickle_prefix = make_path("test/data/tmp",
                                         "result-{}".format(test_name))

        kws = self.some_kws_of_run.copy()
        
        if more_args:
            kws.update(more_args)
            
        kws['root_sampling_method'] = 'random'
        result_pkl_path, meta_graph_pkl_path = run(tree_gen_func,
                                                   calculate_graph=False,
                                                   print_summary=False,
                                                   result_pkl_path_prefix=result_pickle_prefix,
                                                   **kws)

        trees = pkl.load(open(result_pkl_path))
        trees = filter(None, trees)

        assert_true(len(trees) > 0)
        for t in trees:
            assert_true(len(t.edges()) > 0)
        return trees, nx.read_gpickle(meta_graph_pkl_path)

    # overrides
    def test_variance_method(self):
        # self.check('variance', variance_method)
        pass

    def test_distance_weight_using_hashtag_bow(self):
        pass

    def test_with_roots(self):
        pass
        
    def tearDown(self):
        remove_tmp_data('test/data/tmp')
        
