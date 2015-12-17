import codecs
import ujson as json


def load_items_by_line(path):
    with codecs.open(path, 'r', 'utf8') as f:
        items = set([l.strip()
                    for l in f])
    return items


def load_json_by_line(path):
    return map(json.loads, load_items_by_line(path))


def load_msgid2interaction_dict(path):
    interactions = load_json_by_line(path)
    return {i['message_id']: i
            for i in interactions}
