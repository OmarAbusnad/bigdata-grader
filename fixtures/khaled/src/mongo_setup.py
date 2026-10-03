def setup(col):
    col.create_index('order_id', unique=True)
