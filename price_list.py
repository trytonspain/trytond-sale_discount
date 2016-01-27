#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.config import config
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = ['PriceList', 'PriceListLine']

DISCOUNT_DIGITS = int(config.get('digits', 'discount_digits', 4))


class PriceList:
    __name__ = 'product.price_list'
    __metaclass__ = PoolMeta

    def compute_discount(self, party, product, unit_price, discount, quantity,
            uom, pattern=None):
        Uom = Pool().get('product.uom')

        if pattern is None:
            pattern = {}

        pattern = pattern.copy()
        pattern['product'] = product and product.id or None
        pattern['quantity'] = Uom.compute_qty(uom, quantity,
            product.default_uom, round=False) if product else quantity

        for line in self.lines:
            if line.match(pattern):
                with Transaction().set_context(
                        self._get_context_price_list_line(party, product,
                            unit_price, quantity, uom)):
                    return line.discount
        return discount


class PriceListLine:
    __name__ = 'product.price_list.line'
    __metaclass__ = PoolMeta
    discount = fields.Numeric('Discount', digits=(16, DISCOUNT_DIGITS))
