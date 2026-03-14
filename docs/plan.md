# Spier & McKay Scraper bot

## Introduction

The goal of this package is to provide a scraper that can identify in stock
items from https://www.spierandmackay.com/ that are in the right size and style.

Clearance items in particular are often out of stock in the combination of style
and size that I want, and the filtering options on the site are insufficient.

For instance, at the time of writing, this link only has stock in "Extra Slim"
size 35 or 36
https://www.spierandmackay.com/product/brown---chino---ry-3038-chn-01-ss22

The top level goal is to scrape the clearance
(https://www.spierandmackay.com/collection/clearance-rack) and odds & ends (for
example
https://www.spierandmackay.com/collection/odds--ends-trousers-from-4999!) parts
of the site and retrieve in stock status for the listed items. From the listed
items it should then filter by user supplied fits for given styles and retrieve
the subset that are available.

## Functional requirements

- Scrape the site, either just clearance and odds & ends or the full site if
  that's easier, but then taking note of items that are discounted as a filter
  criteria
- Able to apply filters based on desired fit and size combinations for the given
  article of clothing
- Notify the user of matches (ideally via discord webhook)
- Stretch goal, compare results to the previous day's findings, only return net
  new results (does not require longer history)
  - Note: This is a stretch goal, don't add complicated persistence or databases
    to accomplish it. An in-memory cache that will be lost during crashes is
    totally fine.

## Non Functional requirements

- Don't get my IP banned
- Accept fit and size parameters as an easy yml or similar config file
- Deploy as a container (ideally I'll self-host this on kubernetes)
- Build the dev environment and the container artifact using nix flakes
- Local testing on both mocks and live data available for rapid validation
- Build and publish pipelines in github actions (I'll add this folder to a repo
  later once the base functionality works)

## Proof of concept

To start, just search the clearance rack for pants that fit a contemporary 33
