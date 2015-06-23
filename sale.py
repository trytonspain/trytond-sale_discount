# This file is part of sale_discount module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.modules.sale.sale import SaleReport as OriginalSaleReport
from trytond.config import config
DIGITS = int(config.get('digits', 'unit_price_digits', 4))
DISCOUNT_DIGITS = int(config.get('digits', 'discount_digits', 4))

__all__ = ['SaleLine', 'SaleReport',
    'ApplySaleDiscountStart', 'ApplySaleDiscount']
__metaclass__ = PoolMeta

STATES = {
    'invisible': Eval('type') != 'line',
    'required': Eval('type') == 'line',
    }


class SaleLine:
    __name__ = 'sale.line'

    gross_unit_price = fields.Numeric('Gross Price', digits=(16, DIGITS),
        states=STATES, depends=['type'])
    gross_unit_price_wo_round = fields.Numeric('Gross Price without rounding',
        digits=(16, DIGITS + DISCOUNT_DIGITS), readonly=True)
    discount = fields.Numeric('Discount', digits=(16, DISCOUNT_DIGITS),
        states=STATES, depends=['type'])
    sale_discount = fields.Numeric('Sale Discount',
        digits=(16, DISCOUNT_DIGITS), readonly=True, states={
            'invisible': Eval('type') != 'line',
            }, depends=['type'])

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls.unit_price.states['readonly'] = True
        cls.unit_price.digits = (20, DIGITS + DISCOUNT_DIGITS)
        if 'discount' not in cls.unit.on_change:
            cls.unit.on_change.add('discount')
        if 'sale_discount' not in cls.unit.on_change:
            cls.unit.on_change.add('sale_discount')
        if 'discount' not in cls.amount.on_change_with:
            cls.amount.on_change_with.add('discount')
        if 'sale_discount' not in cls.amount.on_change_with:
            cls.amount.on_change_with.add('sale_discount')
        if 'gross_unit_price' not in cls.amount.on_change_with:
            cls.amount.on_change_with.add('gross_unit_price')

    @staticmethod
    def default_discount():
        return Decimal(0)

    def update_prices(self):
        unit_price = None
        gross_unit_price = gross_unit_price_wo_round = self.gross_unit_price
        if self.gross_unit_price is not None and (self.discount is not None
                or self.sale_discount is not None):
            unit_price = self.gross_unit_price
            if self.discount:
                unit_price *= (1 - self.discount)
            if self.sale_discount:
                unit_price *= (1 - self.sale_discount)

            if self.discount and self.sale_discount:
                discount = (self.discount + self.sale_discount
                    - self.discount * self.sale_discount)
                if discount != 1:
                    gross_unit_price_wo_round = (
                        unit_price / (1 - discount))
            elif self.discount and self.discount != 1:
                gross_unit_price_wo_round = (
                    unit_price / (1 - self.discount))
            elif self.sale_discount and self.sale_discount != 1:
                gross_unit_price_wo_round = (
                    unit_price / (1 - self.sale_discount))

            digits = self.__class__.unit_price.digits[1]
            unit_price = unit_price.quantize(Decimal(str(10.0 ** -digits)))

            digits = self.__class__.gross_unit_price.digits[1]
            gross_unit_price = gross_unit_price_wo_round.quantize(
                Decimal(str(10.0 ** -digits)))

        return {
            'gross_unit_price': gross_unit_price,
            'gross_unit_price_wo_round': gross_unit_price_wo_round,
            'unit_price': unit_price,
            }

    @fields.depends('gross_unit_price', 'discount', 'sale_discount')
    def on_change_gross_unit_price(self):
        return self.update_prices()

    @fields.depends('gross_unit_price', 'discount', 'sale_discount')
    def on_change_discount(self):
        return self.update_prices()

    @fields.depends('discount', 'sale_discount')
    def on_change_product(self):
        res = super(SaleLine, self).on_change_product()
        if 'unit_price' in res:
            self.gross_unit_price = res['unit_price']
            self.discount = Decimal(0)
            res.update(self.update_prices())
        if 'discount' not in res:
            res['discount'] = Decimal(0)
        return res

    @fields.depends('discount', 'sale_discount')
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
            line.invoice_discount = self.sale_discount
            line.discount = self.discount
        return lines

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if vals.get('type', 'line') != 'line':
                continue
            if vals.get('unit_price') is None:
                vals['gross_unit_price'] = Decimal(0)
                continue

            gross_unit_price = vals['unit_price']
            if vals.get('discount') not in (None, 1):
                gross_unit_price = gross_unit_price / (1 - vals['discount'])
            if vals.get('sale_discount') not in (None, 1):
                gross_unit_price = (gross_unit_price
                    / (1 - vals['sale_discount']))
            if gross_unit_price != vals['unit_price']:
                digits = cls.gross_unit_price.digits[1]
                gross_unit_price = gross_unit_price.quantize(
                    Decimal(str(10.0 ** -digits)))
            vals['gross_unit_price'] = gross_unit_price
            if 'discount' not in vals:
                vals['discount'] = Decimal(0)
        return super(SaleLine, cls).create(vlist)


class SaleReport(OriginalSaleReport):
    __name__ = 'sale.sale.discount'


class ApplySaleDiscountStart(ModelView):
    'Apply Sale Discount'
    __name__ = 'sale.apply_sale_discount.start'
    discount = fields.Numeric("Sale's Global Discount",
        digits=(16, DISCOUNT_DIGITS), required=True)


class ApplySaleDiscount(Wizard):
    'Apply Sale Discount'
    __name__ = 'sale.apply_sale_discount'
    start = StateView('sale.apply_sale_discount.start',
        'sale_discount.apply_sale_discount_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply_discount', 'tryton-ok', default=True),
            ])
    apply_discount = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ApplySaleDiscount, cls).__setup__()
        cls._error_messages.update({
                'invalid_sale_sate': (
                    'You cannot change the applied discount to sale "%s" '
                    'because it isn\'t in Draft state.'),
                })

    def default_start(self, fields):
        Sale = Pool().get('sale.sale')
        sale = Sale(Transaction().context['active_id'])
        if sale.state != 'draft':
            self.raise_user_error('invalid_sale_sate', (sale.rec_name,))
        return {}

    def transition_apply_discount(self):
        Sale = Pool().get('sale.sale')
        sale = Sale(Transaction().context['active_id'])
        for line in sale.lines:
            if line.type != 'line':
                continue
            line.sale_discount = self.start.discount
            prices = line.update_prices()
            line.gross_unit_price = prices['gross_unit_price']
            line.gross_unit_price_wo_round = (
                prices['gross_unit_price_wo_round'])
            line.unit_price = prices['unit_price']
            line.save()
        return 'end'
