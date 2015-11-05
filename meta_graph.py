# Convert a list of interactions into a meta interaction graph

import re
import numpy as np
import ujson as json
import nltk
import gensim
import networkx as nt
from collections import defaultdict

from util import load_items_by_line

def convert_to_meta_graph(node_names, sources, targets, time_stamps):
    """
    sources: list of source node id for each interaction
    targets: list of target node ids for each interaction
    time_stamps: happening time of the interactions

    All four fields shall be sorted from earliest to lastest
    according to time_stamps
    """
    assert len(node_names) == len(sources) == len(targets) == len(time_stamps)
    g = nt.DiGraph()
    
    s2n = defaultdict(set)  # source to nodes mapping
    for n, s in zip(node_names, sources):
        s2n[s].add(n)
    
    for n1, s, ts in zip(node_names, sources, targets):
        # remove entries of n1 in s2n
        s2n[s].remove(n1)

        # add node, can be singleton
        g.add_node(n1)
        
        # add edges
        for n2 in s2n[s]:
            g.add_edge(n1, n2)
        for t in ts:
            for n2 in s2n[t]:
                g.add_edge(n1, n2)
    return g


class EnronUtil(object):
    stoplist = load_items_by_line('lemur-stopwords.txt')
    valid_token_regexp = re.compile('^[a-z]+$')

    @classmethod
    def get_meta_graph(cls, interactions):
        """
        Return the meta graph together with temporally sorted interactions
        """
        interactions = sorted(interactions, key=lambda r: r['datetime'])
        node_names = [i['message_id'] for i in interactions]
        sources = [i['sender_id'] for i in interactions]
        targets = [i['recipient_ids'] for i in interactions]
        time_stamps = [i['datetime'] for i in interactions]
        
        g = convert_to_meta_graph(node_names, sources,
                                  targets, time_stamps)
        for i in interactions:
            n = i['message_id']
            g.node[n]['body'] = i['body']
            g.node[n]['subject'] = i['subject']

        return g

    @classmethod
    def tokenize_document(cls, doc):
        return [
            word for word in nltk.word_tokenize(doc.lower())
            if (word not in cls.stoplist and
                cls.valid_token_regexp.match(word) and
                len(word) > 2)
        ]

    @classmethod
    def add_topics_to_graph(cls, g, lda_model, dictionary):
        for n in g.nodes():
            doc = u'{} {}'.format(g.node[n]['subject'], g.node[n]['body'])
            topic_dist = lda_model.get_document_topics(
                dictionary.doc2bow(cls.tokenize_document(doc))
            )
            g.node[n]['topics'] = np.asarray([v for _, v in topic_dist],
                                             dtype=np.float)
        return g


def main(json_path='enron.json'):
    interactions = json.load(open(json_path))
    g = EnronUtil.get_meta_graph(interactions)
    print(len(g.nodes()))
    print(len(g.edges()))

    lda_model = gensim.models.ldamodel.LdaModel.load('model-4-50.lda')
    dictionary = gensim.corpora.dictionary.Dictionary.load('dictionary.gsm')

    g = EnronUtil.add_topics_to_graph(g, lda_model, dictionary)
    import pdb; pdb.set_trace()
    

if __name__ == '__main__':
    main()
