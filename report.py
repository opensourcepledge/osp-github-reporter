#!/usr/bin/env python3

import argparse
import os
import sys
from pprint import pprint

from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport


VIEWER_SPONSORSHIP_LOG = gql("""
query getViewerSponsorshipLog($target: String!, $after: String) {
    repositoryOwner(login: $target) {
        ... on Sponsorable {
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
Gets a log of all sponsorship events by the user or organization with login
`target`.
"""
def get_sponsorship_log(client, target):
    events = []

    after = None
    while True:
        page_results = client.execute(VIEWER_SPONSORSHIP_LOG,
            variable_values={'target': target, 'after': after})
        events.extend(page_results['repositoryOwner']['sponsorsActivities']['nodes'])
        after = page_results['repositoryOwner']['sponsorsActivities']['pageInfo']['endCursor']
        if not page_results['repositoryOwner']['sponsorsActivities']['pageInfo']['hasNextPage']:
            break

    return events


def main():
    parser = argparse.ArgumentParser("osp-github-reporter")
    parser.add_argument("--target",
        help="The user or organization to get the report for",
        type=str,
        required=True)
    parser.add_argument("--token",
        help="Your GitHub personal access token (classic)",
        type=str,
        required=True)
    args = parser.parse_args()

    client = get_gql_client(args.token)
    events = get_sponsorship_log(client, args.target)
    pprint(events)


if __name__ == '__main__':
    main()
