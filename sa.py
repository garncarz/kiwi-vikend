#!/usr/bin/env python3

import json
from grab import Grab
from lxml import etree

src = 'Ostrava'
dest = 'Brno'
date = '20160924'


session = Grab()
session.go('https://www.studentagency.cz')

resp = session.go(
    'https://www.studentagency.cz/data/wc/ybus-form/destinations-cs.json'
)
dest_resp = json.loads(resp.body.decode('utf-8'))

cities = []
for country in dest_resp['destinations']:
    cities.extend(country['cities'])

def get_destination_id(name):
    return next(filter(lambda d: d['name'] == name, cities))['id']

url = (
    'https://jizdenky.regiojet.cz/Booking'
    '/from/%(src)s/to/%(dest)s'
    '/tarif/REGULAR'
    '/departure/%(departure)s/retdep/%(retdep)s/return/false'
    % {'src': get_destination_id(src),
       'dest': get_destination_id(dest),
       'departure': date,
       'retdep': date,
      }
)
resp = session.go(url)
resp = session.go('%s%s' %
    (url,
     '?0-1.IBehaviorListener.0-mainPanel-routesPanel',
    )
)

out = open('out.html', 'wb')
out.write(resp.body)

tree = etree.fromstring(resp.body.decode('utf-8'), parser=etree.HTMLParser())

results = []
for result_xml in tree.xpath('//div[contains(@class, "routeSummary")]'):
    val = lambda column: result_xml.xpath(
                            './div[contains(@class, "%s")]/text()' % column
                         )[0]
    result = {
        'departure': val('col_depart'),
        'arrival': val('col_arival'),
        'free_seats': val('col_space'),
        # 'price': val('col_price_no_basket_image'),
    }
    results.append(result)
