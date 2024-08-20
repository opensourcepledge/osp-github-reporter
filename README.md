# Open Source Pledge GitHub Reporter

(TODO: Detailed description.)

## Usage

1. [Create a GitHub personal access token (classic)](https://github.com/settings/tokens) with the permissions `read:org`
   and `read:user`. Note that this is a classic token, _not_ a fine-grained token.
2. Decide with user or organization you want to get reports for.
3. Run `report.py`: `./report.py --target myuser --token ghp_accesstokengoeshere`
