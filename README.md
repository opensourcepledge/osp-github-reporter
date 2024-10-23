# Open Source Pledge GitHub Reporter

This tool allows you to export all of your GitHub Sponsors payments in CSV format.

Note that this tool _cannot_ access your GitHub billing data. Therefore, your payments are reconstructed from the list
of users/organizations you have sponsored, and when you started sponsoring each one. This means it's possible for
inaccuracies to arise. [Let us know](mailto:vlad@vlad.website) if they do, and we'll fix them!

## Usage

1. [Create a GitHub personal access token (classic)](https://github.com/settings/tokens) with the permissions `read:org`
   and `read:user`. Note that this is a classic token, _not_ a fine-grained token.
2. Decide with user or organization you want to get reports for.
3. Run `report.py`: `./report.py --target myuser --token ghp_accesstokengoeshere`

## Caveats

Refunds are not documented in GitHub's API, so we weren't able to test those. Would you let us know if you run into any
problems with refunds? They should be listed as payments with negative amounts on the export.

Billing irregularities such as delayed credit card payments cannot be seen using the GitHub API. We can only see the
schedule of what _should_ have been paid. However, the total amounts should eventually add up despite any delayed
payments.

## Technical Notes

GitHub's `totalSponsorshipAmountAsSponsorInCents` is broken and should not be used. This is because, if, in a particular
period, you make two payments of $10, but one payment is declined, your `totalSponsorshipAmountAsSponsorInCents` will
show up as $20.

To reconstruct payments made, I've also had to reconstruct GitHub's billing scheduling algorithm. I think it works
something like this.

* If you're not being billed for any sponsorships, as soon as you start sponsorship A, the day of the month you started
  sponsorship A on is now the day of the month you will be globally billed on.
* If you then start sponsorship B, an immediate payment will be taken on the date your started the sponsorship on, and
  then subsequent payments for sponsorship B will be taken on the day of the month you are being globally billed on.
  This means that, if you start sponsorship A on 2020-01-05, and sponsorship B on 2020-02-01, you will be billed for
  sponsorship B both on 2020-02-01 _and_ 2020-02-05.
* If you cancel all sponsorships, the day of the month you will be billed on is reset. As soon as you then start a new
  sponsorship C, you will start being globally billed on whatever day of the month you started sponsorship C on.

So, you are billed (1) for each sponsorship when it starts, and (2) for _all_ sponsorships on whatever the day of the
month you started your _first_ sponsorship on after having 0 sponsorships.
