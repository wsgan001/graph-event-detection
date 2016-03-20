import random
import numpy as np
import networkx as nx
from interactions import InteractionsUtil as IU


def quota_upperbound(g,
                     r,
                     B,
                     cost_key='c'):
    """compute the maximum prize to collect given edge sum bound, B
    """
    min_costs = []
    for n in nx.descendants(g, r):
        min_costs.append(
            min([g[s][n][cost_key] for s, _ in g.in_edges(n)])
        )

    cost_total = 0
    cnt = 1  # root
    for cost in sorted(min_costs):
        if cost_total + cost > B:
            return cnt
        cnt += 1
        cost_total += cost
    return cnt


tree_density = (lambda prize_sum, cost_sum: float('inf')
                if cost_sum == 0 else
                prize_sum / float(cost_sum))
log_x_density = (lambda prize_sum, cost_sum:
                 np.log(prize_sum+1) * prize_sum / cost_sum)


def node_scores_from_tree(
        tree, r, prize_key='r', cost_key='c',
        score_func=log_x_density):
    """
    return the score of each node
    """
    assert nx.is_arborescence(tree)

    ret = {}

    def aux(n):
        if tree.out_degree(n) == 0:
            # leaf, ignore
            return tree.node[n][prize_key], 0
        else:
            prize_sum, cost_sum = 0, 0
            for c in tree.neighbors(n):
                prize, cost = aux(c)

                prize_sum += prize

                cost_sum += cost
                cost_sum += tree[n][c][cost_key]

            prize_sum += tree.node[n][prize_key]

            ret[n] = score_func(prize_sum, cost_sum)

            return prize_sum, cost_sum

    aux(r)

    return ret
            
    
class RootedTreeSampler(object):
    """Return a rooted tree at each iteration
    """
    def __init__(self, g, timespan_secs):
        self.g = g
        self.timespan_secs = timespan_secs
        # self.root2nodes = {r: set(dag.nodes())
        #                    for r, dag in self.root2dag.items()}

    def update(self, root, tree):
        pass
        
    def take(self):
        raise NotImplementedError

    def root_and_dag(self, r):
        return r, IU.get_rooted_subgraph_within_timespan(
            self.g, r, self.timespan_secs
        )


class UBSampler(RootedTreeSampler):
    def __init__(self, g, B, timespan_secs):
        super(UBSampler, self).__init__(g, timespan_secs)
        non_leaf_roots = (n for n in g.nodes_iter() if g.out_degree(n) > 0)

        self.nodes_sorted_by_upperbound = sorted(
            non_leaf_roots,
            key=lambda r: quota_upperbound(
                IU.get_rooted_subgraph_within_timespan(g, r, timespan_secs),
                r, B),
            reverse=True
        )

    def take(self):
        n = self.nodes_sorted_by_upperbound.pop(0)
        return self.root_and_dag(n)
    

class RandomSampler(RootedTreeSampler):
    def __init__(self, g, timespan_secs):
        self.nodes = set(g.nodes())
        super(RandomSampler, self).__init__(g, timespan_secs)

    def take(self):
        n = random.choice(list(self.nodes))
        self.nodes.remove(n)
        return self.root_and_dag(n)


class DeterministicSampler(RootedTreeSampler):
    def __init__(self, g, roots, timespan_secs):
        super(DeterministicSampler, self).__init__(g, timespan_secs)
        self.roots = roots

    def take(self):
        r = self.roots.pop(0)
        return self.root_and_dag(r)


class AdaptiveSampler(RootedTreeSampler):
    def __init__(self, g, B, timespan_secs, node_score_func=tree_density):
        super(AdaptiveSampler, self).__init__(g, timespan_secs)

        non_leaf_roots = (n for n in g.nodes_iter() if g.out_degree(n) > 0)

        self.node_score_func = node_score_func
        self.root2upperbound = {r: quota_upperbound(
            IU.get_rooted_subgraph_within_timespan(g, r, timespan_secs),
            r, B)
                                for r in non_leaf_roots
        }

        # updated at each iteration
        # nodes that are partially/fully computed
        # excluding leaves
        self.covered_nodes = set()

        # exclude leaves
        self.roots_to_explore = set([n for n in g.nodes_iter()
                                     if g.out_degree(n) > 0])
        self.n_nodes_to_cover = len(self.roots_to_explore)

        self.node2score = {}

    def update(self, root, tree):
        # handle empty tree
        if tree is None:
            self.covered_nodes.add(root)
            if root in self.roots_to_explore:
                self.roots_to_explore.remove(root)
            return

        if root in self.node2score:
            del self.node2score[root]

        # update the node scores
        scores = node_scores_from_tree(tree, root,
                                       score_func=self.node_score_func)
        for node, score in scores.items():
            if node != root:  # root'score won't be registered
                if node not in self.node2score:
                    self.node2score[node] = score
                else:
                    if self.node2score[node] < score:
                        self.node2score[node] = score

        nodes_covered_by_tree = set([n for n in tree.nodes_iter()
                                     if tree.out_degree(n) > 0
                                 ])
        # update roots_to_explore
        newly_covered_nodes = nodes_covered_by_tree - self.covered_nodes
        self.roots_to_explore -= set(newly_covered_nodes)

        # update covered_nodes
        self.covered_nodes |= newly_covered_nodes

    @property
    def explore_proba(self):
        return float(len(self.roots_to_explore)) / self.n_nodes_to_cover

    def random_action(self):
        rnd = random.random()
        if rnd <= self.explore_proba:
            return 'explore'
        else:
            return 'exploit'

    def take(self):
        if self.random_action() == 'explore' and len(self.roots_to_explore) > 0:
            # explore
            # sample by upper bound
            r = max(self.roots_to_explore,
                    key=lambda r: self.root2upperbound)
            return self.root_and_dag(r)
        else:
            # exploit
            # take the node with the highest score
            r = max(self.node2score,
                    key=lambda n: self.node2score[n])
            return self.root_and_dag(r)
