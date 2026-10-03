from pymongo import UpdateOne
ops = [UpdateOne({'order_id': 'x'}, {'$set': {}}, upsert=True)]
orders_raw = 'orders_raw'; orders_validated = 'orders_validated'; orders_quarantine = 'orders_quarantine'
