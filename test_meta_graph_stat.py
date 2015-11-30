import os
import unittest
import gensim
import ujson as json
import numpy as np
from datetime import datetime

from nose.tools import assert_equal, assert_true
from .enron_graph import EnronUtil
from .meta_graph_stat import MetaGraphStat

CURDIR = os.path.dirname(os.path.abspath(__file__))


class MetaGraphStatTest(unittest.TestCase):
    def setUp(self):
        self.lda_model = gensim.models.ldamodel.LdaModel.load(
            os.path.join(CURDIR,
                         'models/model-4-50.lda')
        )
        self.dictionary = gensim.corpora.dictionary.Dictionary.load(
            os.path.join(CURDIR,
                         'models/dictionary.pkl')
        )
        self.interactions = json.load(
            open(os.path.join(CURDIR, 'test/data/enron_test.json'))
        )

        self.g = EnronUtil.get_meta_graph(self.interactions)
        
        # some pseudo cost
        for s, t in self.g.edges():
            self.g[s][t]['c'] = 1

        self.s = MetaGraphStat(self.g,
                               kws={
                                   'temporal_traffic': {
                                       'time_resolution': 'hour'
                                   },
                                   'topics': {
                                       'interactions': self.interactions,
                                       'dictionary': self.dictionary,
                                       'lda': self.lda_model,
                                       'top_k': 5
                                   },
                                   'email_content': {
                                       'interactions': self.interactions
                                   }
                               })

    def test_time_span(self):
        # time zone issue might occur
        expected = {
            'start_time': datetime(2001, 5, 11, 16, 26, 16),
            'end_time': datetime(2001, 5, 11, 16, 26, 20)
        }
        assert_equal(expected, self.s.time_span())
        
    def test_basic_structure_stats(self):
        expected = {
            '#nodes': 7,
            '#singleton': 0,
            '#edges': 10,
            'in_degree': {
                'min': 0,
                'max': 4,
                'average': 1.4285714285714286,
                'median': 1.0
            },
            'out_degree': {
                'min': 0,
                'max': 4,
                'average': 1.4285714285714286,
                'median': 1.0,
            }
        }
        assert_equal(expected,
                     self.s.basic_structure_stats())

    def test_edge_costs(self):
        actual = self.s.edge_costs(max_values=[2, 3])
        for key in ['histogram(<=2)', 'histogram(<=3)']:
            for i in xrange(2):
                np.testing.assert_array_almost_equal(
                    actual['histogram(all)'][i],
                    actual[key][i]
                )
        
    def test_temporal_traffic(self):
        expected = {
            'email_count_hist': [
                ((2001, 5, 11, 16, 26, 16), 3),
                ((2001, 5, 11, 16, 26, 17), 1),
                ((2001, 5, 11, 16, 26, 18), 1),
                ((2001, 5, 11, 16, 26, 19), 1),
                ((2001, 5, 11, 16, 26, 20), 1),
            ]}
        assert_equal(expected,
                     self.s.temporal_traffic(time_resolution='second'))
    
    def test_temporal_traffic_using_hour(self):
        expected = {
            'email_count_hist': [
                ((2001, 5, 11, 16), 7)
            ]}
        assert_equal(expected,
                     self.s.temporal_traffic(time_resolution='hour'))

    def test_topics(self):
        actual = self.s.topics(self.interactions,
                               self.dictionary,
                               self.lda_model,
                               5)
        assert_equal(
            (4, ),
            actual['topic_dist'].shape
        )
        assert_true('davis' in
                    actual['topic_terms'])
        assert_true('utilities' in
                    actual['topic_terms'])
        
    def test_email_content(self):
        actual = self.s.email_content(self.interactions, 1)
        assert_equal(actual['subjects(top1)'], ['s1'])

    def test_summary(self):
        s = self.s.summary()
        assert_true(isinstance(s, basestring))
        assert_true('email_count_hist' in s)
        assert_true('topic_dist' in s)
        assert_true('topic_terms' in s)
        assert_true('subjects(top' in s)
        
    def test_disable_method(self):
        s = MetaGraphStat(self.g,
                          kws={
                              'temporal_traffic': False,
                              'topics': {
                                  'interactions': self.interactions,
                                  'dictionary': self.dictionary,
                                  'lda': self.lda_model,
                                  'top_k': 5
                              },
                              'email_content': {
                                  'interactions': self.interactions
                              }
                          })

        summary = s.summary()
        assert_true(isinstance(summary, basestring))
        assert_true('email_count_hist' not in summary)
        assert_true('topic_dist' in summary)
        assert_true('topic_terms' in summary)
        assert_true('subjects(top' in summary)
