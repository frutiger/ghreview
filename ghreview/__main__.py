# ghreview.__main__

import datetime
import json
import sys
import textwrap

import humanize
import requests
import tabulate

def read(url, user, token, **kwargs):
    auth = requests.auth.HTTPBasicAuth(user, token)
    response = requests.get(url, params=kwargs, auth=auth)
    return response.json(), response.links

def read_resource(resource, root, user, token, **kwargs):
    return read(f'{root}/api/v3/{resource}', user, token, **kwargs)

REPO_INFO = {}
def get_repo_info(url, user, token, **config):
    if url not in REPO_INFO:
        REPO_INFO[url], _ = read(url, user, token)
    return REPO_INFO[url]

USER_INFO = {}
def get_user_info(url, user, token, **config):
    if url not in USER_INFO:
        USER_INFO[url], _ = read(url, user, token)
    return USER_INFO[url]

def collate(queries, **config):
    is_incomplete = False
    issues        = {}

    def process_response(response):
        if response['incomplete_results']:
            is_incomplete = True

        for item in response['items']:
            issues[item['id']] = item

    for query in queries:
        response, links = read_resource('search/issues', q=query, **config)
        process_response(response)
        while links and 'next' in links:
            response, links = read(links['next']['url'], **config)
            process_response(response)

    return is_incomplete, issues.values()

def main():
    with open('ghreview.json') as config:
        config = json.load(config)
    for name, queries in config['queries'].items():
        queries = [q.format(user=config['user']) for q in queries]
        config['queries'][name] = queries

    queries = config['queries'][list(config['queries'])[0]]
    if len(sys.argv) > 1:
        query = sys.argv[1]
        queries = config['queries'].get(query, queries)
    config['queries'] = queries

    is_incomplete, issues = collate(**config)

    issues_by_updated = {}
    for issue in issues:
        # TBD: deal with timezones
        updated_at = datetime.datetime.fromisoformat(issue['updated_at'][:-1])

        issues_by_updated[updated_at] = issue

    if is_incomplete:
        print('Search returned too many results.  Displaying a subset below.')

    table = []
    for updated_at in sorted(issues_by_updated, reverse=True):
        issue = issues_by_updated[updated_at]

        repo_info = get_repo_info(issue['repository_url'], **config)
        user_info = get_user_info(issue['user']['url'], **config)

        repo_name = f'{repo_info["owner"]["login"]}/{repo_info["name"]}'
        repo_name = textwrap.shorten(repo_name, 30, placeholder='...')

        issue_title = textwrap.shorten(issue['title'], 50, placeholder='...')

        table.append({
            'Repo':         repo_name,
            'Title':        issue_title,
            'Author':       user_info['name'],
            'Url':          issue['html_url'],
            'Last Updated': humanize.naturaltime(updated_at),
        })
    print(tabulate.tabulate(table, headers="keys", tablefmt="presto"))

if __name__ == '__main__':
    main()

