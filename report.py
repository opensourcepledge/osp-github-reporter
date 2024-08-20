#!/usr/bin/env python3

import argparse
import os
import sys
from pprint import pprint

import arrow
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport


TOTAL_SPONSORSHIP_AMOUNT_QUERY = gql("""
query getTotalSponsorshipAmount($target: String!, $until: DateTime) {
    repositoryOwner(login: $target) {
        ... on Sponsorable {
            totalSponsorshipAmountAsSponsorInCents(until: $until)
        }
    }
}
""")

SPONSORSHIP_LOG_QUERY = gql("""
query getSponsorshipLog($target: String!, $after: String) {
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
Gets the total sponsorship amount in US cents that `target` has donated,
`since` a given datetime.
"""
def get_total_sponsorship_amount(client, target, until):
    eprint(f"get_total_sponsorship_amount(_, {target}, {until})")
    result = client.execute(TOTAL_SPONSORSHIP_AMOUNT_QUERY,
        variable_values={'target': target, 'until': until})
    return result['repositoryOwner']['totalSponsorshipAmountAsSponsorInCents']


"""
Gets a log of all sponsorship events by the user or organization with login
`target`.
"""
def get_sponsorship_log(client, target):
    eprint(f"get_sponsorship_log(_, {target})")
    events = []

    after = None
    while True:
        page_results = client.execute(SPONSORSHIP_LOG_QUERY,
            variable_values={'target': target, 'after': after})
        events.extend(page_results['repositoryOwner']['sponsorsActivities']['nodes'])
        after = page_results['repositoryOwner']['sponsorsActivities']['pageInfo']['endCursor']
        if not page_results['repositoryOwner']['sponsorsActivities']['pageInfo']['hasNextPage']:
            break

    return events


"""
Takes a list of sponsorship events and returns a list of months into which the
sponsorship amounts are discretized.
"""
def discretize_events(events):
    # TODO
    return []


"""
Gets the total sponsorship amount in US cents that `target` has donated,
from a given `start_date` to a given `end_date`, grouped by month.
"""
def get_monthly_sponsorship_amounts(client, target, start_date, end_date):
    # NOTE: GitHub supports a `since` field and an `until` field for total
    # amounts, but not both at the same time! So we need to only use `until`
    # and do some subtraction for each period using a running total.
    eprint(f"get_total_sponsorship_amounts_for_date_range(_, {target}, {start_date}, {end_date})")
    month_totals = []
    month_start_date = start_date
    month_end_date = month_start_date.shift(months=+1)
    total_so_far = get_total_sponsorship_amount(client, target,
        month_start_date.isoformat())
    while month_start_date < end_date:
        total_to_month_end = get_total_sponsorship_amount(client, target,
            month_end_date.isoformat())
        month_total = total_to_month_end - total_so_far
        total_so_far = total_to_month_end
        month_totals.append((month_start_date, month_total))
        month_start_date = month_start_date.shift(months=+1)
        month_end_date = month_start_date.shift(months=+1)
    return month_totals


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

    # events = get_sponsorship_log(client, args.target)
    # disc_events = discretize_events(events)
    # pprint(disc_events)

    START_DATE = arrow.get('2021-01')
    END_DATE = arrow.get()

    month_totals = get_monthly_sponsorship_amounts(client, args.target, START_DATE, END_DATE)
    pprint(month_totals)


if __name__ == '__main__':
    main()
