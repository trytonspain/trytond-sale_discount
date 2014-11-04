# This file is part of sale_discount module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.config import config
DIGITS = int(config.get('digits', 'unit_price_digits', 4))
DISCOUNT_DIGITS = int(config.get('digits', 'discount_digits', 4))

__all__ = ['Move']
__metaclass__ = PoolMeta


class Move:
    __name__ = 'stock.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls.unit_price.digits = (20, DIGITS + DISCOUNT_DIGITS)
