#!/usr/bin/env python3

import argparse
import os
import sys
from pprint import pprint

from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport


VIEWER_SPONSORSHIP_LOG = gql("""
query getViewerSponsorshipLog($after: String) {
    viewer {
        login
        sponsorsActivities(first: 100, after: $after, period: ALL, includeAsSponsor: true) {
            nodes {
                action
                paymentSource
                previousSponsorsTier {
                    monthlyPriceInCents
                    isOneTime
                }
                sponsorsTier {
                    monthlyPriceInCents
                    isOneTime
                }
                timestamp
                sponsorable {
                    ... on User {
                        login
                    }
                    ... on Organization {
                        login
                    }
                }
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    }
}
""")


"""
Prints to stderr.
"""
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


"""
Gets a `gql.Client`.
"""
def get_gql_client(token):
    transport = AIOHTTPTransport(url="https://api.github.com/graphql",
        headers={'Authorization': f'bearer {token}'})
    return Client(transport=transport, fetch_schema_from_transport=True)


"""
Gets a log of all sponsorship events by the current user.
"""
def get_viewer_sponsorship_log(client):
    viewer_login = None
    events = []

    after = None
    while True:
        page_results = client.execute(VIEWER_SPONSORSHIP_LOG,
            variable_values={'after': after})
        viewer_login = page_results['viewer']['login']
        events.extend(page_results['viewer']['sponsorsActivities']['nodes'])
        after = page_results['viewer']['sponsorsActivities']['pageInfo']['endCursor']
        if not page_results['viewer']['sponsorsActivities']['pageInfo']['hasNextPage']:
            break

    return {
        'viewer_login': viewer_login,
        'events': events,
    }


def main():
    parser = argparse.ArgumentParser("osp-github-reporter")
    parser.add_argument("token",
        nargs=1,
        help="The organization to start the search from",
        type=str)
    args = parser.parse_args()
    token = args.token[0]

    client = get_gql_client(token)
    log = get_viewer_sponsorship_log(client)
    print(log['viewer_login'])
    pprint(log['events'])


if __name__ == '__main__':
    main()
