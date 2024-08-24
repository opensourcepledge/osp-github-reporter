#!/usr/bin/env python3

# © 2024 Vlad-Stefan Harbuz <vlad@vladh.net>
#
# SPDX-License-Identifier: Apache-2.0

from collections import defaultdict
from dataclasses import dataclass
from pprint import pprint
import argparse
import os
import sys

from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
import arrow


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
query getSponsorshipLog($target: String!, $after: String, $since: DateTime) {
    repositoryOwner(login: $target) {
        ... on Sponsorable {
            sponsorsActivities(first: 100, after: $after, since: $since, period: ALL, includeAsSponsor: true) {
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


@dataclass
class Payment:
    date: str
    login: str
    amount_in_cents: int


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


"""
Gets a log of all sponsorship events by the user or organization with login
`target`.
"""
def get_sponsorship_log(client, target, start_date):
    eprint(f"get_sponsorship_log(_, {target}, {start_date})")
    events = []

    after = None
    while True:
        page_results = client.execute(SPONSORSHIP_LOG_QUERY,
            variable_values={'target': target, 'after': after, 'since': start_date.isoformat()})
        events.extend(page_results['repositoryOwner']['sponsorsActivities']['nodes'])
        after = page_results['repositoryOwner']['sponsorsActivities']['pageInfo']['endCursor']
        if not page_results['repositoryOwner']['sponsorsActivities']['pageInfo']['hasNextPage']:
            break

    return events


"""
Groups events into a dict by the YYYY-MM-DD of their timestamp.
"""
def make_day_to_events_map(events):
    day_to_events_map = defaultdict(list)
    for event in events:
        timestamp = arrow.get(event['timestamp'])
        formatted_day = timestamp.format('YYYY-MM-DD')
        day_to_events_map[formatted_day].append(event)
    return day_to_events_map


"""
Given a list of events, reconstructs what payments to sponsorables the target
user _would have_ made, based on a reconstructed version of GitHub's payment
scheduling.
"""
def reconstruct_payments(events, start_date, end_date):
    payments = []
    payment_monthday = None
    payment_login_to_amount_map = {}
    day_to_events_map = make_day_to_events_map(events)

    def remove_sponsorship(login):
        nonlocal payment_monthday
        del payment_login_to_amount_map[login]
        if len(payment_login_to_amount_map) == 0:
            payment_monthday = None

    curr_date = start_date
    while curr_date <= end_date:
        formatted_day = curr_date.format('YYYY-MM-DD')
        monthday = curr_date.day
        todays_events = day_to_events_map[formatted_day]

        for event in todays_events:
            login = event['sponsorable']['login']
            match event['action']:
                case 'CANCELLED_SPONSORSHIP':
                    remove_sponsorship(login)
                case 'PENDING_CHANGE':
                    # We don't do anything here because presumably the pending
                    # change will create its own event at the time it is
                    # scheduled for.
                    # TODO: Confirm this.
                    pass
                case 'SPONSOR_MATCH_DISABLED':
                    # We're ignoring this because I haven't found any
                    # information on what sponsor matching means or how it is
                    # used. Could be the “GitHub Sponsors Matching Fund”, which
                    # doesn't exist anymore.
                    pass
                case 'TIER_CHANGE':
                    monthly_price_in_cents = event['sponsorsTier']['monthlyPriceInCents']
                    is_one_time = event['sponsorsTier']['isOneTime']
                    if is_one_time:
                        # NOTE: Here, we're assuming that a tier change _into_
                        # a one-time tier is effectively a payment followed by
                        # a cancellation of the sponsorship.
                        remove_sponsorship(login)
                        payments.append(Payment(
                            date=formatted_day,
                            login=login,
                            amount_in_cents=monthly_price_in_cents,
                        ))
                    else:
                        # NOTE: Here, we're assuming that, on tier change, the
                        # next payment will be taken on the usual date, _not_
                        # on the date of the tier change. We're assuming that
                        # nothing but the _amount_ changes on tier change.
                        payment_login_to_amount_map[login] = monthly_price_in_cents
                case 'REFUND':
                    # NOTE: This isn't tested because the exact behaviour is
                    # undocumented by GitHub, but we're assuming that the
                    # refund amount is a positive amount in
                    # `monthly_price_in_cents`.
                    monthly_price_in_cents = event['sponsorsTier']['monthlyPriceInCents']
                    payments.append(Payment(
                        date=formatted_day,
                        login=login,
                        amount_in_cents=(0 - monthly_price_in_cents),
                    ))

        if monthday == payment_monthday:
            for login, monthly_price_in_cents in payment_login_to_amount_map.items():
                payments.append(Payment(
                    date=formatted_day,
                    login=login,
                    amount_in_cents=monthly_price_in_cents,
                ))

        for event in todays_events:
            login = event['sponsorable']['login']
            match event['action']:
                case 'NEW_SPONSORSHIP':
                    monthly_price_in_cents = event['sponsorsTier']['monthlyPriceInCents']
                    is_one_time = event['sponsorsTier']['isOneTime']
                    payments.append(Payment(
                        date=formatted_day,
                        login=login,
                        amount_in_cents=monthly_price_in_cents,
                    ))
                    if not is_one_time:
                        if payment_monthday is None:
                            payment_monthday = monthday
                        payment_login_to_amount_map[login] = monthly_price_in_cents

        curr_date = curr_date.shift(days=+1)

    return payments


"""
Print a list of payments as a CSV file.
"""
def print_payments_csv(payments):
    print('Date,Sponsorable,Amount in US Cents')
    for payment in payments:
        print(f'{payment.date},{payment.login},{payment.amount_in_cents}')


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

    START_DATE = arrow.get('2021-08')
    END_DATE = arrow.get()

    events = get_sponsorship_log(client, args.target, START_DATE)
    payments = reconstruct_payments(events, START_DATE, END_DATE)
    print_payments_csv(payments)


if __name__ == '__main__':
    main()
