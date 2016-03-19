import itertools
import pandas as pd
from langdetect import detect


def remove_mentions_and_urls(df):
    def aux(r):
        body = r['body']
        mentions = map(lambda m: '@' + m, r['mentions'])

        for s in itertools.chain(mentions, r['urls']):
            body = body.replace(s.lower(), '')
        return body

    df['body'] = df['body'].map(lambda s: s.lower())
    df['body'] = df[['body', 'mentions', 'urls']].apply(
        aux,
        axis=1
    )

    return df


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dataset', required=True)

    args = parser.parse_args()
    
    df = pd.read_json('data/{}/interactions.json'.format(args.dataset))
    df = remove_mentions_and_urls(df)
    df = df[df['body'].map(len) > 10]  # filter short body
    df = df[df['body'].map(detect) == 'en']  # non english
    df.to_json('data/{}/interactions.json'.format(args.dataset),
               orient='records')

if __name__ == '__main__':
    main()
