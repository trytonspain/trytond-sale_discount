# This file is part of sale_discount module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

from decimal import Decimal
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.modules.sale.sale import SaleReport
from trytond.config import CONFIG
DIGITS = int(CONFIG.get('unit_price_digits', 4))
DISCOUNT_DIGITS = int(CONFIG.get('discount_digits', 4))

__all__ = ['SaleLine', 'SaleReport']
__metaclass__ = PoolMeta

STATES = {
    'invisible': Eval('type') != 'line',
    'required': Eval('type') == 'line',
    }


class SaleLine:
    __name__ = 'sale.line'

    gross_unit_price = fields.Numeric('Gross Price', digits=(16, DIGITS),
        states=STATES)
    gross_unit_price_wo_round = fields.Numeric('Gross Price without rounding',
        digits=(16, DIGITS + DISCOUNT_DIGITS), readonly=True)
    discount = fields.Numeric('Discount', digits=(16, DISCOUNT_DIGITS),
        states=STATES)

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls.unit_price.states['readonly'] = True
        cls.unit_price.digits = (20, DIGITS + DISCOUNT_DIGITS)
        if 'discount' not in cls.product.on_change:
            cls.product.on_change.add('discount')
        if 'discount' not in cls.unit.on_change:
            cls.unit.on_change.add('discount')
        if 'discount' not in cls.amount.on_change_with:
            cls.amount.on_change_with.add('discount')
        if 'gross_unit_price' not in cls.amount.on_change_with:
            cls.amount.on_change_with.add('gross_unit_price')
        if 'discount' not in cls.quantity.on_change:
            cls.quantity.on_change.add('discount')

    @staticmethod
    def default_discount():
        return Decimal(0)

    def update_prices(self):
        unit_price = None
        gross_unit_price = gross_unit_price_wo_round = self.gross_unit_price
        if self.gross_unit_price is not None and self.discount is not None:
            unit_price = self.gross_unit_price * (1 - self.discount)
            digits = self.__class__.unit_price.digits[1]
            unit_price = unit_price.quantize(Decimal(str(10.0 ** -digits)))

            if self.discount != 1:
                gross_unit_price_wo_round = unit_price / (1 - self.discount)
            digits = self.__class__.gross_unit_price.digits[1]
            gross_unit_price = gross_unit_price_wo_round.quantize(
                Decimal(str(10.0 ** -digits)))
        return {
            'gross_unit_price': gross_unit_price,
            'gross_unit_price_wo_round': gross_unit_price_wo_round,
            'unit_price': unit_price,
            }

    @fields.depends('gross_unit_price', 'discount')
    def on_change_gross_unit_price(self):
        return self.update_prices()

    @fields.depends('gross_unit_price', 'discount')
    def on_change_discount(self):
        return self.update_prices()

    def on_change_product(self):
        res = super(SaleLine, self).on_change_product()
        if 'unit_price' in res:
            self.gross_unit_price = res['unit_price']
            self.discount = Decimal(0)
            res.update(self.update_prices())
        if 'discount' not in res:
            res['discount'] = Decimal(0)
        return res

    def on_change_quantity(self):
        res = super(SaleLine, self).on_change_quantity()
        if 'unit_price' in res:
            self.gross_unit_price = res['unit_price']
            res.update(self.update_prices())
        return res

    def get_invoice_line(self, invoice_type):
        lines = super(SaleLine, self).get_invoice_line(invoice_type)
        for line in lines:
            line.gross_unit_price = self.gross_unit_price
            line.discount = self.discount
        return lines

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if vals.get('type', 'line') != 'line':
                continue
            gross_unit_price = vals.get('unit_price', Decimal('0.0'))
            if 'discount' in vals and vals['discount'] != 1:
                gross_unit_price = gross_unit_price / (1 - vals['discount'])
                digits = cls.gross_unit_price.digits[1]
                gross_unit_price = gross_unit_price.quantize(
                    Decimal(str(10.0 ** -digits)))
            vals['gross_unit_price'] = gross_unit_price
            if 'discount' not in vals:
                vals['discount'] = Decimal(0)
        return super(SaleLine, cls).create(vlist)


class SaleReport(SaleReport):
    __name__ = 'sale.sale.discount'
